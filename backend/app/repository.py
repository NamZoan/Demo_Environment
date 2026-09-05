import json
from datetime import datetime, timedelta, timezone
from typing import Any


STALE_AFTER = timedelta(minutes=30)
WARNING_LIMITS = {"pm25": 35.0, "temperature": 38.0, "humidity": 85.0}
CRITICAL_LIMITS = {"pm25": 150.0, "temperature": 42.0, "humidity": 95.0}


async def ensure_runtime_schema(connection) -> None:
    await connection.execute(
        """
        ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
        ALTER TABLE latest_station_readings ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
        """
    )


def resolution_source(resolution: str) -> tuple[str, str]:
    sources = {
        "1m": ("sensor_data", "time"),
        "1h": ("sensor_data_hourly", "bucket"),
        "1d": ("sensor_data_daily", "bucket"),
    }
    try:
        return sources[resolution]
    except KeyError as exc:
        raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d") from exc


def authentication_query() -> str:
    return """
        SELECT id, username, full_name, role
        FROM users
        WHERE username = $1
          AND password_hash = crypt($2, password_hash)
          AND status = 'active'
        LIMIT 1
    """


async def authenticate_user(connection, username: str, password: str) -> dict | None:
    row = await connection.fetchrow(authentication_query(), username, password)
    if row is None:
        return None
    user = dict(row)
    context = await fetch_user_context(connection, user["id"])
    user["roles"] = context["roles"]
    user["region_ids"] = context["region_ids"]
    return user


async def fetch_user_context(connection, user_id: int) -> dict[str, Any]:
    row = await connection.fetchrow(
        """
        SELECT
            COALESCE(array_agg(DISTINCT r.code) FILTER (WHERE r.code IS NOT NULL), ARRAY[]::text[]) AS roles,
            COALESCE(array_agg(DISTINCT ur.region_id) FILTER (WHERE ur.region_id IS NOT NULL), ARRAY[]::bigint[]) AS region_ids
        FROM users u
        LEFT JOIN user_roles uro ON uro.user_id = u.id
        LEFT JOIN roles r ON r.id = uro.role_id
        LEFT JOIN user_regions ur ON ur.user_id = u.id
        WHERE u.id = $1
        GROUP BY u.id
        """,
        user_id,
    )
    if row is None:
        return {"roles": ["viewer"], "region_ids": []}
    roles = list(row["roles"]) or ["viewer"]
    return {"roles": roles, "region_ids": list(row["region_ids"])}


async def fetch_stations(connection) -> list[dict]:
    rows = await connection.fetch(
        """
        SELECT id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        FROM stations
        ORDER BY code
        """
    )
    return [_station_row(row) for row in rows]


async def fetch_stations_for_user(connection, user: dict) -> list[dict]:
    if "super_admin" in user.get("roles", []):
        return await fetch_stations(connection)
    rows = await connection.fetch(
        """
        SELECT id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        FROM stations
        WHERE region_id = ANY($1::bigint[])
        ORDER BY code
        """,
        user.get("region_ids", []),
    )
    return [_station_row(row) for row in rows]


async def fetch_station_by_id(connection, station_id: int) -> dict | None:
    row = await connection.fetchrow(
        """
        SELECT id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        FROM stations
        WHERE id = $1
        """,
        station_id,
    )
    return _station_row(row) if row else None


async def create_station(connection, payload: dict, user: dict) -> dict:
    if not can_modify_station(user, payload.get("region_id")):
        raise PermissionError("User cannot create stations in this region")
    row = await connection.fetchrow(
        """
        INSERT INTO stations (code, name, latitude, longitude, address, status, metadata, region_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
        RETURNING id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        """,
        payload["code"],
        payload["name"],
        payload.get("latitude"),
        payload.get("longitude"),
        payload.get("address"),
        payload.get("status", "active"),
        json.dumps(payload.get("metadata", {})),
        payload.get("region_id"),
    )
    station = _station_row(row)
    await insert_audit_log(connection, user["id"], "station.create", "station", station["id"], None, station)
    return station


async def update_station(connection, station_id: int, payload: dict, user: dict) -> dict | None:
    existing = await fetch_station_by_id(connection, station_id)
    if existing is None:
        return None
    target_region_id = payload.get("region_id", existing.get("region_id"))
    if not can_modify_station(user, existing.get("region_id")) or not can_modify_station(user, target_region_id):
        raise PermissionError("User cannot update this station")

    merged = {**existing, **{key: value for key, value in payload.items() if value is not None}}
    row = await connection.fetchrow(
        """
        UPDATE stations
        SET code = $2,
            name = $3,
            latitude = $4,
            longitude = $5,
            address = $6,
            status = $7,
            metadata = $8::jsonb,
            region_id = $9,
            updated_at = now()
        WHERE id = $1
        RETURNING id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        """,
        station_id,
        merged["code"],
        merged["name"],
        merged.get("latitude"),
        merged.get("longitude"),
        merged.get("address"),
        merged.get("status", "active"),
        json.dumps(merged.get("metadata", {})),
        merged.get("region_id"),
    )
    station = _station_row(row)
    await insert_audit_log(connection, user["id"], "station.update", "station", station_id, existing, station)
    return station


async def delete_station(connection, station_id: int, user: dict) -> bool:
    existing = await fetch_station_by_id(connection, station_id)
    if existing is None:
        return False
    if not can_modify_station(user, existing.get("region_id")):
        raise PermissionError("User cannot delete this station")
    result = await connection.execute("DELETE FROM stations WHERE id = $1", station_id)
    await insert_audit_log(connection, user["id"], "station.delete", "station", station_id, existing, None)
    return result.endswith("1")


async def fetch_station_data(
    connection,
    station_id: int,
    start_time: datetime,
    end_time: datetime,
    resolution: str,
) -> list[dict]:
    table, bucket_column = resolution_source(resolution)
    samples_expression = "samples" if resolution != "1m" else "NULL::bigint AS samples"
    wind_speed_expression = "wind_speed" if resolution == "1m" else "NULL::double precision AS wind_speed"
    rows = await connection.fetch(
        f"""
        SELECT
            {bucket_column} AS time,
            temperature,
            humidity,
            {wind_speed_expression},
            pm25,
            {samples_expression}
        FROM {table}
        WHERE station_id = $1
          AND {bucket_column} >= $2
          AND {bucket_column} <= $3
        ORDER BY {bucket_column}
        """,
        station_id,
        start_time,
        end_time,
    )
    return [dict(row) for row in rows]


async def fetch_live_stations(connection, user: dict) -> list[dict]:
    region_filter = ""
    args: list[Any] = []
    if "super_admin" not in user.get("roles", []):
        region_filter = "WHERE s.region_id = ANY($1::bigint[])"
        args.append(user.get("region_ids", []))
    rows = await connection.fetch(
        f"""
        SELECT
            s.id,
            s.code,
            s.name,
            s.latitude,
            s.longitude,
            s.address,
            s.status AS station_status,
            s.metadata,
            s.region_id,
            s.last_seen_at,
            l.time,
            l.temperature,
            l.humidity,
            l.wind_speed,
            l.pm25
        FROM stations s
        LEFT JOIN latest_station_readings l ON l.station_id = s.id
        {region_filter}
        ORDER BY s.code
        """,
        *args,
    )
    now = datetime.now(timezone.utc)
    return [_live_station_row(row, now) for row in rows]


async def fetch_overview(connection, user: dict) -> dict:
    live = await fetch_live_stations(connection, user)
    counts = {"total": len(live), "online": 0, "warning": 0, "critical": 0, "offline": 0}
    for station in live:
        counts[station["live_status"]] += 1
    return counts


async def insert_audit_log(
    connection,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    before_data: dict | None,
    after_data: dict | None,
) -> None:
    await connection.execute(
        """
        INSERT INTO audit_logs (user_id, action, entity_type, entity_id, before_data, after_data)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb)
        """,
        user_id,
        action,
        entity_type,
        entity_id,
        json.dumps(before_data) if before_data is not None else None,
        json.dumps(after_data) if after_data is not None else None,
    )


def can_modify_station(user: dict, station_region_id: int | None) -> bool:
    roles = set(user.get("roles", []))
    if "super_admin" in roles:
        return True
    if "manager" not in roles:
        return False
    return station_region_id in set(user.get("region_ids", []))


def classify_station_status(
    *,
    pm25: float | None,
    temperature: float | None,
    humidity: float | None,
    last_seen_at: datetime | None,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    if last_seen_at is None:
        return "offline"
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    if now - last_seen_at > STALE_AFTER:
        return "offline"

    values = {"pm25": pm25, "temperature": temperature, "humidity": humidity}
    if any(value is not None and value >= CRITICAL_LIMITS[metric] for metric, value in values.items()):
        return "critical"
    if any(value is not None and value >= WARNING_LIMITS[metric] for metric, value in values.items()):
        return "warning"
    return "online"


def _station_row(row) -> dict:
    item = dict(row)
    if isinstance(item.get("metadata"), str):
        item["metadata"] = json.loads(item["metadata"])
    return item


def _live_station_row(row, now: datetime) -> dict:
    item = _station_row(row)
    item["status"] = item.pop("station_status")
    item["live_status"] = classify_station_status(
        pm25=item.get("pm25"),
        temperature=item.get("temperature"),
        humidity=item.get("humidity"),
        last_seen_at=item.get("last_seen_at") or item.get("time"),
        now=now,
    )
    return item
