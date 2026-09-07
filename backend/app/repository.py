import json
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Any

from app.ftp_browser import normalize_ftp_path


STALE_AFTER = timedelta(minutes=30)
MAX_INTERACTIVE_POINTS_DEFAULT = 1000
MIN_INTERACTIVE_POINTS = 100
MAX_INTERACTIVE_POINTS = 5000
MAX_INTERACTIVE_RANGE = timedelta(days=365 * 5)
RBAC_ROLES = {"super_admin", "manager", "viewer"}
SENSOR_METRIC_COLUMNS = {
    "temperature": "temperature",
    "humidity": "humidity",
    "wind_speed": "wind_speed",
    "pm25": "pm25",
}
RESOLUTION_DURATIONS = {
    "1m": timedelta(minutes=1),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


async def ensure_runtime_schema(connection) -> None:
    await connection.execute(
        """
        ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
        ALTER TABLE latest_station_readings ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
        CREATE TABLE IF NOT EXISTS station_ftp_configs (
            station_id BIGINT PRIMARY KEY REFERENCES stations(id) ON DELETE CASCADE,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 21 CHECK (port BETWEEN 1 AND 65535),
            username TEXT NOT NULL,
            password_encrypted BYTEA NOT NULL,
            root_path TEXT NOT NULL DEFAULT '/data',
            timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 120),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS ftp_files (
            id BIGSERIAL PRIMARY KEY,
            station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
            remote_path TEXT NOT NULL,
            name TEXT NOT NULL,
            entry_type TEXT NOT NULL CHECK (entry_type IN ('file', 'folder')),
            size_bytes BIGINT,
            modified_at TEXT,
            status TEXT NOT NULL DEFAULT 'discovered',
            error TEXT,
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (station_id, remote_path)
        );
        CREATE TABLE IF NOT EXISTS ftp_servers (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 21 CHECK (port BETWEEN 1 AND 65535),
            username TEXT NOT NULL,
            password_encrypted BYTEA NOT NULL,
            root_path TEXT NOT NULL DEFAULT '/data',
            timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 120),
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            legacy_station_id BIGINT UNIQUE REFERENCES stations(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS station_ftp_assignments (
            station_id BIGINT PRIMARY KEY REFERENCES stations(id) ON DELETE CASCADE,
            ftp_server_id BIGINT NOT NULL REFERENCES ftp_servers(id) ON DELETE CASCADE,
            root_path TEXT NOT NULL DEFAULT '/data',
            assigned_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_station_ftp_assignments_server ON station_ftp_assignments (ftp_server_id);
        INSERT INTO ftp_servers (name, host, port, username, password_encrypted, root_path, timeout_seconds, legacy_station_id)
        SELECT COALESCE(s.code, 'FTP station ' || c.station_id::text), c.host, c.port, c.username,
               c.password_encrypted, c.root_path, c.timeout_seconds, c.station_id
        FROM station_ftp_configs c
        LEFT JOIN stations s ON s.id = c.station_id
        ON CONFLICT (legacy_station_id) DO NOTHING;
        INSERT INTO station_ftp_assignments (station_id, ftp_server_id, root_path)
        SELECT c.station_id, f.id, c.root_path
        FROM station_ftp_configs c
        JOIN ftp_servers f ON f.legacy_station_id = c.station_id
        ON CONFLICT (station_id) DO NOTHING;
        CREATE INDEX IF NOT EXISTS idx_ftp_files_station_seen ON ftp_files (station_id, last_seen_at DESC);
        """
    )


def metric_column(metric: str) -> str:
    try:
        return SENSOR_METRIC_COLUMNS[metric]
    except KeyError as exc:
        raise ValueError("Unsupported metric") from exc


def can_manage_users(user: dict) -> bool:
    return "super_admin" in set(user.get("roles", []))


def normalize_user_role(role: str) -> str:
    if role not in RBAC_ROLES:
        raise ValueError(f"Unsupported role: {role}")
    return role


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user["username"],
        "full_name": user.get("full_name"),
        "role": user.get("role", "viewer"),
        "roles": list(user.get("roles", [])),
        "status": user.get("status", "active"),
        "region_ids": list(user.get("region_ids", [])),
    }


def require_user_management(user: dict) -> None:
    if not can_manage_users(user):
        raise PermissionError("Only super admins can manage users")


def normalize_ftp_catalog_row(row: dict) -> dict:
    result = dict(row)
    if isinstance(result.get("stations"), str):
        result["stations"] = json.loads(result["stations"])
    return result


def aqi_level(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 50:
        return "good"
    if value <= 100:
        return "moderate"
    if value <= 150:
        return "unhealthy_sensitive"
    return "unhealthy"


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


def station_data_source(resolution: str) -> tuple[str, str]:
    if resolution == "1m":
        return (
            """
            SELECT
                time,
                temperature,
                humidity,
                wind_speed,
                pm25,
                NULL::bigint AS samples,
                NULL::bigint AS valid_hours
            FROM sensor_data
            WHERE station_id = $1
              AND time >= $2
              AND time <= $3
            ORDER BY time
            """,
            "time",
        )
    if resolution == "1h":
        return (
            """
            SELECT
                bucket,
                temperature,
                humidity,
                wind_speed,
                pm25,
                samples,
                NULL::bigint AS valid_hours
            FROM sensor_data_hourly
            WHERE station_id = $1
              AND bucket >= $2
              AND bucket <= $3
            ORDER BY bucket
            """,
            "bucket",
        )
    if resolution == "1d":
        return (
            """
            SELECT
                bucket,
                temperature,
                humidity,
                wind_speed,
                pm25,
                samples,
                valid_hours
            FROM sensor_data_daily
            WHERE station_id = $1
              AND bucket >= $2
              AND bucket <= $3
            ORDER BY bucket
            """,
            "bucket",
        )
    raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d")


def estimated_candidate_points(start_time: datetime, end_time: datetime, resolution: str) -> int:
    duration = RESOLUTION_DURATIONS[resolution]
    return int((end_time - start_time).total_seconds() // duration.total_seconds()) + 1


def downsample_interval_seconds(candidate_points: int, max_points: int, resolution: str) -> int:
    multiplier = ceil(candidate_points / max_points)
    return int(multiplier * RESOLUTION_DURATIONS[resolution].total_seconds())


def station_downsample_source(resolution: str) -> tuple[str, str]:
    table, bucket_column = resolution_source(resolution)
    metric_expressions = {
        "1m": {
            "temperature": "avg(temperature) AS temperature",
            "humidity": "avg(humidity) AS humidity",
            "wind_speed": "avg(wind_speed) AS wind_speed",
            "pm25": "avg(pm25) AS pm25",
        },
        "1h": {
            "temperature": "sum(temperature * samples) / nullif(sum(samples), 0) AS temperature",
            "humidity": "sum(humidity * samples) / nullif(sum(samples), 0) AS humidity",
            "wind_speed": "sum(wind_speed * samples) / nullif(sum(samples), 0) AS wind_speed",
            "pm25": "sum(pm25 * samples) / nullif(sum(samples), 0) AS pm25",
        },
        "1d": {
            "temperature": "sum(temperature * samples) / nullif(sum(samples), 0) AS temperature",
            "humidity": "sum(humidity * samples) / nullif(sum(samples), 0) AS humidity",
            "wind_speed": "sum(wind_speed * samples) / nullif(sum(samples), 0) AS wind_speed",
            "pm25": "sum(pm25 * samples) / nullif(sum(samples), 0) AS pm25",
        },
    }
    sample_expressions = {
        "1m": ("count(*)::bigint AS samples", "NULL::bigint AS valid_hours"),
        "1h": ("sum(samples)::bigint AS samples", "NULL::bigint AS valid_hours"),
        "1d": ("sum(samples)::bigint AS samples", "sum(valid_hours)::bigint AS valid_hours"),
    }
    try:
        metrics = metric_expressions[resolution]
        samples_expression, valid_hours_expression = sample_expressions[resolution]
    except KeyError as exc:
        raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d") from exc
    return (
        f"""
        SELECT
            to_timestamp(
                (floor((extract(epoch from {bucket_column}) - extract(epoch from $2::timestamptz)) / $4) * $4)
                + extract(epoch from $2::timestamptz)
            ) AS bucket,
            {metrics["temperature"]},
            {metrics["humidity"]},
            {metrics["wind_speed"]},
            {metrics["pm25"]},
            {samples_expression},
            {valid_hours_expression}
        FROM {table}
        WHERE station_id = $1
          AND {bucket_column} >= $2
          AND {bucket_column} <= $3
        GROUP BY bucket
        ORDER BY bucket
        """,
        "bucket",
    )


def validate_interactive_query_range(start_time: datetime, end_time: datetime, max_points: int) -> None:
    if start_time >= end_time:
        raise ValueError("start_time must be before end_time")
    if max_points < MIN_INTERACTIVE_POINTS or max_points > MAX_INTERACTIVE_POINTS:
        raise ValueError("max_points must be between 100 and 5000")
    if end_time - start_time > MAX_INTERACTIVE_RANGE:
        raise ValueError("Interactive time range must not exceed 5 years")


def choose_effective_resolution(requested_resolution: str, start_time: datetime, end_time: datetime) -> tuple[str, str | None]:
    span = end_time - start_time
    if requested_resolution in {"1m", "1h"} and span > timedelta(days=90):
        return "1d", f"Switched from {requested_resolution} to 1d because the selected range is longer than 90 days."
    if requested_resolution == "1m" and span > timedelta(hours=48):
        return "1h", "Switched from 1m to 1h because the selected range is longer than 48 hours."
    if requested_resolution in RESOLUTION_DURATIONS:
        return requested_resolution, None
    raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d")


def query_meta(
    requested_resolution: str,
    effective_resolution: str,
    max_points: int,
    returned_points: int,
    downsampled: bool,
    resolution_note: str | None,
) -> dict:
    return {
        "requested_resolution": requested_resolution,
        "effective_resolution": effective_resolution,
        "max_points": max_points,
        "returned_points": returned_points,
        "downsampled": downsampled,
        "resolution_note": resolution_note,
    }


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
            u.status,
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
        return {"status": "inactive", "roles": ["viewer"], "region_ids": []}
    roles = list(row["roles"]) or ["viewer"]
    return {"status": row["status"], "roles": roles, "region_ids": list(row["region_ids"])}


async def fetch_rbac_options(connection) -> dict:
    roles = await connection.fetch("SELECT code, name, description FROM roles ORDER BY id")
    regions = await connection.fetch("SELECT id, code, name FROM regions ORDER BY code")
    return {"roles": [dict(row) for row in roles], "regions": [dict(row) for row in regions]}


async def fetch_managed_users(connection) -> list[dict]:
    rows = await connection.fetch(
        """
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.role,
            u.status,
            COALESCE(array_agg(DISTINCT r.code) FILTER (WHERE r.code IS NOT NULL), ARRAY[]::text[]) AS roles,
            COALESCE(array_agg(DISTINCT ur.region_id) FILTER (WHERE ur.region_id IS NOT NULL), ARRAY[]::bigint[]) AS region_ids
        FROM users u
        LEFT JOIN user_roles uro ON uro.user_id = u.id
        LEFT JOIN roles r ON r.id = uro.role_id
        LEFT JOIN user_regions ur ON ur.user_id = u.id
        GROUP BY u.id
        ORDER BY u.username
        """
    )
    return [public_user(dict(row)) for row in rows]


async def fetch_managed_user(connection, user_id: int) -> dict | None:
    users = await connection.fetch(
        """
        SELECT
            u.id,
            u.username,
            u.full_name,
            u.role,
            u.status,
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
    return public_user(dict(users[0])) if users else None


async def validate_region_ids(connection, region_ids: list[int]) -> None:
    region_ids = sorted(set(region_ids))
    if not region_ids:
        return
    count = await connection.fetchval("SELECT count(*) FROM regions WHERE id = ANY($1::bigint[])", region_ids)
    if count != len(region_ids):
        raise ValueError("One or more regions do not exist")


async def ensure_not_last_super_admin(connection, user_id: int, target_role: str, target_status: str) -> None:
    if target_role == "super_admin" and target_status == "active":
        return
    current_roles = await connection.fetchval(
        """
        SELECT EXISTS(
            SELECT 1 FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            JOIN users u ON u.id = ur.user_id
            WHERE ur.user_id = $1 AND r.code = 'super_admin' AND u.status = 'active'
        )
        """,
        user_id,
    )
    if not current_roles:
        return
    count = await connection.fetchval(
        """
        SELECT count(*)
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.status = 'active' AND r.code = 'super_admin'
        """
    )
    if count <= 1:
        raise ValueError("Cannot remove the last active super admin")


async def create_managed_user(connection, payload: dict) -> dict:
    role = normalize_user_role(payload["role"])
    region_ids = sorted(set(payload.get("region_ids", [])))
    await validate_region_ids(connection, region_ids)
    row = await connection.fetchrow(
        """
        INSERT INTO users (username, password_hash, full_name, role, status)
        VALUES ($1, crypt($2, gen_salt('bf')), $3, $4, 'active')
        RETURNING id
        """,
        payload["username"],
        payload["password"],
        payload.get("full_name", ""),
        role,
    )
    user_id = row["id"]
    await connection.execute(
        """
        INSERT INTO user_roles (user_id, role_id)
        SELECT $1, id FROM roles WHERE code = $2
        """,
        user_id,
        role,
    )
    if region_ids:
        await connection.executemany(
            "INSERT INTO user_regions (user_id, region_id) VALUES ($1, $2)",
            [(user_id, region_id) for region_id in region_ids],
        )
    return await fetch_managed_user(connection, user_id)


async def update_managed_user(connection, user_id: int, payload: dict) -> dict | None:
    role = normalize_user_role(payload["role"])
    region_ids = sorted(set(payload.get("region_ids", [])))
    await validate_region_ids(connection, region_ids)
    existing = await fetch_managed_user(connection, user_id)
    if existing is None:
        return None
    await ensure_not_last_super_admin(connection, user_id, role, payload["status"])
    if payload.get("password"):
        await connection.execute(
            """
            UPDATE users
            SET full_name = $2, role = $3, status = $4, password_hash = crypt($5, gen_salt('bf')), updated_at = now()
            WHERE id = $1
            """,
            user_id,
            payload.get("full_name", ""),
            role,
            payload["status"],
            payload["password"],
        )
    else:
        await connection.execute(
            """
            UPDATE users SET full_name = $2, role = $3, status = $4, updated_at = now()
            WHERE id = $1
            """,
            user_id,
            payload.get("full_name", ""),
            role,
            payload["status"],
        )
    await connection.execute("DELETE FROM user_roles WHERE user_id = $1", user_id)
    await connection.execute(
        "INSERT INTO user_roles (user_id, role_id) SELECT $1, id FROM roles WHERE code = $2",
        user_id,
        role,
    )
    await connection.execute("DELETE FROM user_regions WHERE user_id = $1", user_id)
    if region_ids:
        await connection.executemany(
            "INSERT INTO user_regions (user_id, region_id) VALUES ($1, $2)",
            [(user_id, region_id) for region_id in region_ids],
        )
    return await fetch_managed_user(connection, user_id)


async def disable_managed_user(connection, user_id: int, actor_id: int) -> bool:
    if user_id == actor_id:
        raise PermissionError("You cannot disable your own account")
    existing = await fetch_managed_user(connection, user_id)
    if existing is None:
        return False
    await ensure_not_last_super_admin(connection, user_id, existing["role"], "inactive")
    result = await connection.execute("UPDATE users SET status = 'inactive', updated_at = now() WHERE id = $1", user_id)
    return result.endswith("1")


async def fetch_stations(connection) -> list[dict]:
    rows = await connection.fetch(
        """
        SELECT id, code, name, latitude, longitude, address, status, metadata, region_id, last_seen_at
        FROM stations
        ORDER BY code
        """
    )
    return [_station_row(row) for row in rows]


def qcvn_config_row(row) -> dict:
    return {
        "id": row["id"],
        "station_id": row["station_id"],
        "station_code": row["station_code"],
        "station_name": row["station_name"],
        "metric": row["metric"],
        "warning_min": row["warning_min"],
        "warning_max": row["warning_max"],
        "critical_min": row["critical_min"],
        "critical_max": row["critical_max"],
        "enabled": row["enabled"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


async def fetch_qcvn_configs(connection, user: dict) -> list[dict]:
    args: list[Any] = []
    region_filter = ""
    if "super_admin" not in user.get("roles", []):
        region_filter = "AND s.region_id = ANY($1::bigint[])"
        args.append(user.get("region_ids", []))
    rows = await connection.fetch(
        f"""
        SELECT
            ac.id,
            ac.station_id,
            s.code AS station_code,
            s.name AS station_name,
            ac.metric,
            ac.warning_min,
            ac.warning_max,
            ac.critical_min,
            ac.critical_max,
            ac.enabled,
            ac.created_at,
            ac.updated_at
        FROM alert_configs ac
        JOIN stations s ON s.id = ac.station_id
        WHERE ac.station_id IS NOT NULL
        {region_filter}
        ORDER BY s.code, ac.metric
        """,
        *args,
    )
    return [qcvn_config_row(row) for row in rows]


async def fetch_qcvn_config(connection, config_id: int) -> dict | None:
    row = await connection.fetchrow(
        """
        SELECT
            ac.id,
            ac.station_id,
            s.code AS station_code,
            s.name AS station_name,
            ac.metric,
            ac.warning_min,
            ac.warning_max,
            ac.critical_min,
            ac.critical_max,
            ac.enabled,
            ac.created_at,
            ac.updated_at
        FROM alert_configs ac
        JOIN stations s ON s.id = ac.station_id
        WHERE ac.id = $1 AND ac.station_id IS NOT NULL
        """,
        config_id,
    )
    return qcvn_config_row(row) if row else None


async def qcvn_station_region_id(connection, station_id: int) -> int | None:
    row = await connection.fetchrow("SELECT region_id FROM stations WHERE id = $1", station_id)
    if row is None:
        raise LookupError("Station not found")
    return row["region_id"]


def require_qcvn_station_access(user: dict, region_id: int | None) -> None:
    if not can_modify_station(user, region_id):
        raise PermissionError("You do not have permission to manage QCVN for this station")


async def create_qcvn_config(connection, payload: dict, user: dict) -> dict:
    station_id = payload["station_id"]
    region_id = await qcvn_station_region_id(connection, station_id)
    require_qcvn_station_access(user, region_id)
    existing = await connection.fetchval(
        "SELECT id FROM alert_configs WHERE station_id = $1 AND metric = $2",
        station_id,
        payload["metric"],
    )
    if existing is not None:
        raise ValueError("QCVN configuration already exists for this station and metric")
    row = await connection.fetchrow(
        """
        INSERT INTO alert_configs (
            station_id, metric, warning_min, warning_max,
            critical_min, critical_max, enabled, created_by
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id
        """,
        station_id,
        payload["metric"],
        payload.get("warning_min"),
        payload.get("warning_max"),
        payload.get("critical_min"),
        payload.get("critical_max"),
        payload.get("enabled", True),
        user.get("id"),
    )
    return await fetch_qcvn_config(connection, row["id"])


async def update_qcvn_config(connection, config_id: int, payload: dict, user: dict) -> dict | None:
    existing = await fetch_qcvn_config(connection, config_id)
    if existing is None:
        return None
    current_region_id = await qcvn_station_region_id(connection, existing["station_id"])
    require_qcvn_station_access(user, current_region_id)
    target_region_id = await qcvn_station_region_id(connection, payload["station_id"])
    require_qcvn_station_access(user, target_region_id)
    duplicate = await connection.fetchval(
        """
        SELECT id FROM alert_configs
        WHERE station_id = $1 AND metric = $2 AND id <> $3
        """,
        payload["station_id"],
        payload["metric"],
        config_id,
    )
    if duplicate is not None:
        raise ValueError("QCVN configuration already exists for this station and metric")
    await connection.execute(
        """
        UPDATE alert_configs
        SET station_id = $2,
            metric = $3,
            warning_min = $4,
            warning_max = $5,
            critical_min = $6,
            critical_max = $7,
            enabled = $8,
            updated_at = now()
        WHERE id = $1
        """,
        config_id,
        payload["station_id"],
        payload["metric"],
        payload.get("warning_min"),
        payload.get("warning_max"),
        payload.get("critical_min"),
        payload.get("critical_max"),
        payload.get("enabled", True),
    )
    return await fetch_qcvn_config(connection, config_id)


async def delete_qcvn_config(connection, config_id: int, user: dict) -> bool:
    existing = await fetch_qcvn_config(connection, config_id)
    if existing is None:
        return False
    region_id = await qcvn_station_region_id(connection, existing["station_id"])
    require_qcvn_station_access(user, region_id)
    result = await connection.execute("DELETE FROM alert_configs WHERE id = $1", config_id)
    return result.endswith("1")


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


async def create_station(connection, payload: dict, user: dict, encryption_key: str) -> dict:
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
    if payload.get("ftp_config"):
        await save_station_ftp_config(connection, station["id"], payload["ftp_config"], encryption_key)
    await insert_audit_log(connection, user["id"], "station.create", "station", station["id"], None, station)
    return station


async def update_station(connection, station_id: int, payload: dict, user: dict, encryption_key: str) -> dict | None:
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
    if payload.get("ftp_config"):
        await save_station_ftp_config(connection, station_id, payload["ftp_config"], encryption_key)
    await insert_audit_log(connection, user["id"], "station.update", "station", station_id, existing, station)
    return station


async def save_station_ftp_config(connection, station_id: int, ftp_config: dict, encryption_key: str) -> None:
    existing = await connection.fetchrow(
        "SELECT ftp_server_id FROM station_ftp_assignments WHERE station_id = $1",
        station_id,
    )
    root_path = normalize_ftp_path(ftp_config.get("root_path", "/data"))
    if existing:
        await connection.execute(
            """
            UPDATE ftp_servers
            SET name = COALESCE($2, name), host = $3, port = $4, username = $5,
                password_encrypted = pgp_sym_encrypt($6, $7), root_path = $8,
                timeout_seconds = $9, updated_at = now()
            WHERE id = $1
            """,
            existing["ftp_server_id"],
            ftp_config.get("name"),
            ftp_config["host"],
            ftp_config.get("port", 21),
            ftp_config["user"],
            ftp_config["password"],
            encryption_key,
            root_path,
            ftp_config.get("timeout_seconds", 5),
        )
        await connection.execute(
            "UPDATE station_ftp_assignments SET root_path = $2 WHERE station_id = $1",
            station_id,
            root_path,
        )
        return
    row = await connection.fetchrow(
        """
        INSERT INTO ftp_servers (name, host, port, username, password_encrypted, root_path, timeout_seconds)
        VALUES ($1, $2, $3, $4, pgp_sym_encrypt($5, $6), $7, $8)
        RETURNING id
        """,
        ftp_config.get("name", f"FTP station {station_id}"),
        ftp_config["host"],
        ftp_config.get("port", 21),
        ftp_config["user"],
        ftp_config["password"],
        encryption_key,
        root_path,
        ftp_config.get("timeout_seconds", 5),
    )
    await connection.execute(
        "INSERT INTO station_ftp_assignments (station_id, ftp_server_id, root_path) VALUES ($1, $2, $3)",
        station_id,
        row["id"],
        root_path,
    )


async def fetch_station_ftp_config(connection, station_id: int, encryption_key: str) -> dict | None:
    row = await connection.fetchrow(
        """
        SELECT f.host, f.port, f.username AS user,
               pgp_sym_decrypt(f.password_encrypted, $2) AS password,
               a.root_path, f.timeout_seconds
        FROM station_ftp_assignments a
        JOIN ftp_servers f ON f.id = a.ftp_server_id
        WHERE a.station_id = $1 AND f.status = 'active'
        """,
        station_id,
        encryption_key,
    )
    return dict(row) if row else None


async def fetch_ftp_connection_settings(connection, ftp_id: int, user: dict, encryption_key: str) -> dict | None:
    if await fetch_ftp_server(connection, ftp_id, user) is None:
        return None
    row = await connection.fetchrow(
        """
        SELECT f.host, f.port, f.username AS user,
               pgp_sym_decrypt(f.password_encrypted, $2) AS password,
               f.root_path, f.timeout_seconds
        FROM ftp_servers f
        WHERE f.id = $1 AND f.status = 'active'
        """,
        ftp_id,
        encryption_key,
    )
    return dict(row) if row else None


async def fetch_ftp_configs(connection, user: dict) -> list[dict]:
    region_filter = "" if "super_admin" in user.get("roles", []) else "WHERE EXISTS (SELECT 1 FROM station_ftp_assignments xa JOIN stations xs ON xs.id = xa.station_id WHERE xa.ftp_server_id = f.id AND xs.region_id = ANY($1::bigint[]))"
    args = [] if not region_filter else [user.get("region_ids", [])]
    rows = await connection.fetch(
        f"""
        SELECT f.id, f.name, f.host, f.port, f.username AS user, f.root_path,
               f.timeout_seconds, f.status,
               COALESCE(array_agg(DISTINCT a.station_id) FILTER (WHERE a.station_id IS NOT NULL), ARRAY[]::bigint[]) AS station_ids,
               COALESCE(jsonb_agg(DISTINCT jsonb_build_object('id', s.id, 'code', s.code, 'name', s.name)) FILTER (WHERE s.id IS NOT NULL), '[]'::jsonb) AS stations
        FROM ftp_servers f
        LEFT JOIN station_ftp_assignments a ON a.ftp_server_id = f.id
        LEFT JOIN stations s ON s.id = a.station_id
        {region_filter}
        GROUP BY f.id
        ORDER BY f.name
        """,
        *args,
    )
    return [normalize_ftp_catalog_row(dict(row)) for row in rows]


async def create_ftp_server(connection, payload: dict, user: dict, encryption_key: str) -> dict:
    station_ids = sorted(set(payload.get("station_ids", [])))
    await validate_ftp_station_assignments(connection, station_ids, user)
    row = await connection.fetchrow(
        """
        INSERT INTO ftp_servers (name, host, port, username, password_encrypted, root_path, timeout_seconds)
        VALUES ($1, $2, $3, $4, pgp_sym_encrypt($5, $6), $7, $8)
        RETURNING id
        """,
        payload["name"],
        payload["host"],
        payload.get("port", 21),
        payload["user"],
        payload["password"],
        encryption_key,
        normalize_ftp_path(payload.get("root_path", "/data")),
        payload.get("timeout_seconds", 5),
    )
    await replace_ftp_station_assignments(connection, row["id"], station_ids, payload.get("root_path", "/data"))
    return await fetch_ftp_server(connection, row["id"], user)


async def fetch_ftp_server(connection, ftp_id: int, user: dict) -> dict | None:
    configs = await fetch_ftp_configs(connection, {"roles": ["super_admin"], "region_ids": []})
    config = next((item for item in configs if item["id"] == ftp_id), None)
    if config is None or "super_admin" in user.get("roles", []):
        return config
    visible = await fetch_ftp_configs(connection, user)
    return next((item for item in visible if item["id"] == ftp_id), None)


async def validate_ftp_station_assignments(connection, station_ids: list[int], user: dict) -> None:
    if not station_ids:
        return
    rows = await connection.fetch("SELECT id, region_id FROM stations WHERE id = ANY($1::bigint[])", station_ids)
    if len(rows) != len(station_ids):
        raise ValueError("One or more stations do not exist")
    if any(not can_modify_station(user, row["region_id"]) for row in rows):
        raise PermissionError("User cannot assign FTP to one or more stations")


async def replace_ftp_station_assignments(connection, ftp_id: int, station_ids: list[int], root_path: str) -> None:
    await connection.execute("DELETE FROM station_ftp_assignments WHERE ftp_server_id = $1", ftp_id)
    if station_ids:
        await connection.executemany(
            "INSERT INTO station_ftp_assignments (station_id, ftp_server_id, root_path) VALUES ($1, $2, $3) ON CONFLICT (station_id) DO UPDATE SET ftp_server_id = EXCLUDED.ftp_server_id, root_path = EXCLUDED.root_path",
            [(station_id, ftp_id, normalize_ftp_path(root_path)) for station_id in station_ids],
        )


async def update_ftp_server(connection, ftp_id: int, payload: dict, user: dict, encryption_key: str) -> dict | None:
    existing = await fetch_ftp_server(connection, ftp_id, {"roles": ["super_admin"], "region_ids": []})
    if existing is None:
        return None
    station_ids = sorted(set(payload.get("station_ids", [])))
    await validate_ftp_station_assignments(connection, station_ids, user)
    password = payload.get("password")
    if password:
        await connection.execute(
            """
            UPDATE ftp_servers SET name = $2, host = $3, port = $4, username = $5,
                password_encrypted = pgp_sym_encrypt($6, $7), root_path = $8,
                timeout_seconds = $9, updated_at = now() WHERE id = $1
            """,
            ftp_id, payload["name"], payload["host"], payload.get("port", 21), payload["user"], password,
            encryption_key, normalize_ftp_path(payload.get("root_path", "/data")), payload.get("timeout_seconds", 5),
        )
    else:
        await connection.execute(
            """
            UPDATE ftp_servers SET name = $2, host = $3, port = $4, username = $5,
                root_path = $6, timeout_seconds = $7, updated_at = now() WHERE id = $1
            """,
            ftp_id, payload["name"], payload["host"], payload.get("port", 21), payload["user"],
            normalize_ftp_path(payload.get("root_path", "/data")), payload.get("timeout_seconds", 5),
        )
    await replace_ftp_station_assignments(connection, ftp_id, station_ids, payload.get("root_path", "/data"))
    return await fetch_ftp_server(connection, ftp_id, user)


async def delete_ftp_server(connection, ftp_id: int, user: dict) -> bool:
    existing = await fetch_ftp_server(connection, ftp_id, user)
    if existing is None:
        return False
    result = await connection.execute("DELETE FROM ftp_servers WHERE id = $1", ftp_id)
    return result.endswith("1")


async def delete_station_ftp_config(connection, station_id: int, user: dict) -> bool:
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_modify_station(user, station_region_id):
        raise PermissionError("User cannot modify this station FTP configuration")
    result = await connection.execute("DELETE FROM station_ftp_assignments WHERE station_id = $1", station_id)
    return result.endswith("1")


async def fetch_ftp_file_index(connection, station_id: int, user: dict) -> list[dict]:
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_read_station(user, station_region_id):
        raise PermissionError("Station is outside assigned regions")
    rows = await connection.fetch(
        """
        SELECT name, remote_path AS path, entry_type AS type, size_bytes AS size, modified_at AS modified
        FROM ftp_files
        WHERE station_id = $1
          AND last_seen_at >= now() - interval '24 hours'
        ORDER BY (entry_type = 'folder') DESC, name
        """,
        station_id,
    )
    return [dict(row) for row in rows]


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
    user: dict,
    max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT,
) -> dict:
    validate_interactive_query_range(start_time, end_time, max_points)
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_read_station(user, station_region_id):
        raise PermissionError("Station is outside assigned regions")

    effective_resolution, resolution_note = choose_effective_resolution(resolution, start_time, end_time)
    candidate_points = estimated_candidate_points(start_time, end_time, effective_resolution)
    downsampled = candidate_points > max_points
    if downsampled:
        query, bucket_column = station_downsample_source(effective_resolution)
        interval_seconds = downsample_interval_seconds(candidate_points, max_points, effective_resolution)
        rows = await connection.fetch(query, station_id, start_time, end_time, interval_seconds)
        resolution_note = f"Returned {max_points} representative points from {candidate_points} available points."
    else:
        query, bucket_column = station_data_source(effective_resolution)
        rows = await connection.fetch(query, station_id, start_time, end_time)
    points = [{**dict(row), "time": row[bucket_column]} for row in rows]
    return {
        "meta": query_meta(resolution, effective_resolution, max_points, len(points), downsampled, resolution_note),
        "points": points,
    }


async def fetch_analytics_series(
    connection,
    station_ids: list[int],
    metric: str,
    start_time: datetime,
    end_time: datetime,
    resolution: str,
    user: dict,
    max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT,
) -> dict:
    validate_interactive_query_range(start_time, end_time, max_points)
    for station_id in station_ids:
        station_region_id = await resolve_station_region_id(connection, station_id)
        if not can_read_station(user, station_region_id):
            raise PermissionError("Station is outside assigned regions")
    column = metric_column(metric)
    effective_resolution, resolution_note = choose_effective_resolution(resolution, start_time, end_time)
    table, bucket_column = resolution_source(effective_resolution)
    candidate_points = estimated_candidate_points(start_time, end_time, effective_resolution)
    downsampled = candidate_points > max_points
    if downsampled:
        interval_seconds = downsample_interval_seconds(candidate_points, max_points, effective_resolution)
        value_expression = analytics_average_expression(f"data.{column}", effective_resolution, "value", sample_column="data.samples")
        rows = await connection.fetch(
            f"""
            SELECT
                to_timestamp(
                    (floor((extract(epoch from data.{bucket_column}) - extract(epoch from $2::timestamptz)) / $4) * $4)
                    + extract(epoch from $2::timestamptz)
                ) AS time,
                s.id AS station_id,
                s.code AS station_code,
                s.name AS station_name,
                {value_expression}
            FROM {table} data
            JOIN stations s ON s.id = data.station_id
            WHERE data.station_id = ANY($1::bigint[])
              AND data.{bucket_column} >= $2
              AND data.{bucket_column} <= $3
            GROUP BY time, s.id, s.code, s.name
            ORDER BY time, s.code
            """,
            station_ids,
            start_time,
            end_time,
            interval_seconds,
        )
    else:
        rows = await connection.fetch(
            f"""
            SELECT
                data.{bucket_column} AS time,
                s.id AS station_id,
                s.code AS station_code,
                s.name AS station_name,
                data.{column} AS value
            FROM {table} data
            JOIN stations s ON s.id = data.station_id
            WHERE data.station_id = ANY($1::bigint[])
              AND data.{bucket_column} >= $2
              AND data.{bucket_column} <= $3
            ORDER BY data.{bucket_column}, s.code
            """,
            station_ids,
            start_time,
            end_time,
        )
    points = [
        {
            **dict(row),
            "metric": metric,
            "aqi_level": aqi_level(row["value"]) if metric == "pm25" else None,
        }
        for row in rows
    ]
    return {
        "meta": query_meta(resolution, effective_resolution, max_points, len(points), downsampled, resolution_note),
        "points": points,
    }


async def fetch_analytics_heatmap(
    connection,
    station_id: int,
    metric: str,
    start_time: datetime,
    end_time: datetime,
    user: dict,
) -> list[dict]:
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_read_station(user, station_region_id):
        raise PermissionError("Station is outside assigned regions")
    column = metric_column(metric)
    rows = await connection.fetch(
        f"""
        SELECT
            to_char(time_bucket('1 day', time), 'YYYY-MM-DD') AS day,
            EXTRACT(hour FROM time)::int AS hour,
            avg({column}) AS value
        FROM sensor_data
        WHERE station_id = $1
          AND time >= $2
          AND time <= $3
        GROUP BY day, hour
        ORDER BY day, hour
        """,
        station_id,
        start_time,
        end_time,
    )
    return [
        {
            **dict(row),
            "level": aqi_level(row["value"]) if metric == "pm25" else None,
        }
        for row in rows
    ]


async def fetch_analytics_scatter(
    connection,
    station_id: int,
    x_metric: str,
    y_metric: str,
    start_time: datetime,
    end_time: datetime,
    resolution: str,
    user: dict,
    max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT,
) -> dict:
    validate_interactive_query_range(start_time, end_time, max_points)
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_read_station(user, station_region_id):
        raise PermissionError("Station is outside assigned regions")
    x_column = metric_column(x_metric)
    y_column = metric_column(y_metric)
    effective_resolution, resolution_note = choose_effective_resolution(resolution, start_time, end_time)
    table, bucket_column = resolution_source(effective_resolution)
    candidate_points = estimated_candidate_points(start_time, end_time, effective_resolution)
    downsampled = candidate_points > max_points
    if downsampled:
        interval_seconds = downsample_interval_seconds(candidate_points, max_points, effective_resolution)
        x_expression = analytics_average_expression(x_column, effective_resolution, "x")
        y_expression = analytics_average_expression(y_column, effective_resolution, "y")
        rows = await connection.fetch(
            f"""
            SELECT
                to_timestamp(
                    (floor((extract(epoch from {bucket_column}) - extract(epoch from $2::timestamptz)) / $4) * $4)
                    + extract(epoch from $2::timestamptz)
                ) AS time,
                station_id,
                {x_expression},
                {y_expression}
            FROM {table}
            WHERE station_id = $1
              AND {bucket_column} >= $2
              AND {bucket_column} <= $3
              AND {x_column} IS NOT NULL
              AND {y_column} IS NOT NULL
            GROUP BY time, station_id
            ORDER BY time
            """,
            station_id,
            start_time,
            end_time,
            interval_seconds,
        )
    else:
        rows = await connection.fetch(
            f"""
            SELECT
                {bucket_column} AS time,
                station_id,
                {x_column} AS x,
                {y_column} AS y
            FROM {table}
            WHERE station_id = $1
              AND {bucket_column} >= $2
              AND {bucket_column} <= $3
              AND {x_column} IS NOT NULL
              AND {y_column} IS NOT NULL
            ORDER BY {bucket_column}
            """,
            station_id,
            start_time,
            end_time,
        )
    points = [dict(row) for row in rows]
    return {
        "meta": query_meta(resolution, effective_resolution, max_points, len(points), downsampled, resolution_note),
        "points": points,
    }


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
    thresholds = await fetch_live_station_qcvn_thresholds(connection, rows)
    return [_live_station_row(row, now, thresholds.get(row["id"], {})) for row in rows]


async def fetch_live_station_qcvn_thresholds(connection, station_rows) -> dict[int, dict[str, dict[str, float | None]]]:
    station_ids = [row["id"] for row in station_rows]
    if not station_ids:
        return {}

    config_rows = await connection.fetch(
        """
        SELECT station_id, region_id, metric, warning_min, warning_max, critical_min, critical_max
        FROM alert_configs
        WHERE enabled = TRUE
          AND metric = ANY($1::text[])
          AND station_id = ANY($2::bigint[])
        """,
        list(SENSOR_METRIC_COLUMNS.keys()),
        station_ids,
    )
    by_station: dict[int, dict[str, dict[str, float | None]]] = {}
    for row in config_rows:
        threshold = qcvn_threshold_row(row)
        if row["station_id"] is not None:
            by_station.setdefault(row["station_id"], {})[row["metric"]] = threshold

    thresholds: dict[int, dict[str, dict[str, float | None]]] = {}
    for row in station_rows:
        thresholds[row["id"]] = by_station.get(row["id"], {})
    return thresholds


def qcvn_threshold_row(row) -> dict[str, float | None]:
    return {
        "warning_min": row["warning_min"],
        "warning_max": row["warning_max"],
        "critical_min": row["critical_min"],
        "critical_max": row["critical_max"],
    }


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


def can_read_station(user: dict, station_region_id: int | None) -> bool:
    if "super_admin" in user.get("roles", []):
        return True
    return station_region_id in set(user.get("region_ids", []))


def analytics_average_expression(column: str, resolution: str, alias: str, sample_column: str = "samples") -> str:
    if resolution == "1m":
        return f"avg({column}) AS {alias}"
    if resolution in {"1h", "1d"}:
        return f"sum({column} * {sample_column}) / nullif(sum({sample_column}), 0) AS {alias}"
    raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d")


async def resolve_station_region_id(connection, station_id: int) -> int | None:
    row = await connection.fetchrow(
        """
        SELECT region_id FROM stations
        WHERE id = $1
        """,
        station_id,
    )
    if row is None:
        raise LookupError("Station not found")
    return row["region_id"]


def classify_station_status(
    *,
    pm25: float | None,
    temperature: float | None,
    humidity: float | None,
    last_seen_at: datetime | None,
    wind_speed: float | None = None,
    now: datetime | None = None,
    thresholds: dict[str, dict[str, float | None]] | None = None,
) -> str:
    now = now or datetime.now(timezone.utc)
    if last_seen_at is None:
        return "offline"
    if last_seen_at.tzinfo is None:
        last_seen_at = last_seen_at.replace(tzinfo=timezone.utc)
    if now - last_seen_at > STALE_AFTER:
        return "offline"

    values = {"pm25": pm25, "temperature": temperature, "humidity": humidity, "wind_speed": wind_speed}
    thresholds = thresholds or {}
    if any(is_threshold_breach(value, thresholds.get(metric), "critical") for metric, value in values.items()):
        return "critical"
    if any(is_threshold_breach(value, thresholds.get(metric), "warning") for metric, value in values.items()):
        return "warning"
    return "online"


def is_threshold_breach(value: float | None, threshold: dict[str, float | None] | None, level: str) -> bool:
    if value is None or threshold is None:
        return False
    min_value = threshold.get(f"{level}_min")
    max_value = threshold.get(f"{level}_max")
    return (min_value is not None and value <= min_value) or (max_value is not None and value >= max_value)


def _station_row(row) -> dict:
    item = dict(row)
    if isinstance(item.get("metadata"), str):
        item["metadata"] = json.loads(item["metadata"])
    return item


def _live_station_row(row, now: datetime, thresholds: dict[str, dict[str, float | None]]) -> dict:
    item = _station_row(row)
    item["status"] = item.pop("station_status")
    item["qcvn_thresholds"] = thresholds
    item["live_status"] = classify_station_status(
        pm25=item.get("pm25"),
        temperature=item.get("temperature"),
        humidity=item.get("humidity"),
        wind_speed=item.get("wind_speed"),
        last_seen_at=item.get("last_seen_at") or item.get("time"),
        now=now,
        thresholds=thresholds,
    )
    return item
