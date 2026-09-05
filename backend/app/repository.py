import json
from datetime import datetime


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
    return dict(row)


async def fetch_stations(connection) -> list[dict]:
    rows = await connection.fetch(
        """
        SELECT id, code, name, latitude, longitude, address, status, metadata
        FROM stations
        ORDER BY code
        """
    )
    return [_station_row(row) for row in rows]


async def fetch_station_data(
    connection,
    station_id: int,
    start_time: datetime,
    end_time: datetime,
    resolution: str,
) -> list[dict]:
    table, bucket_column = resolution_source(resolution)
    samples_expression = "samples" if resolution != "1m" else "NULL::bigint AS samples"
    rows = await connection.fetch(
        f"""
        SELECT
            {bucket_column} AS time,
            temperature,
            humidity,
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


def _station_row(row) -> dict:
    item = dict(row)
    if isinstance(item.get("metadata"), str):
        item["metadata"] = json.loads(item["metadata"])
    return item
