from __future__ import annotations

from io import StringIO

import psycopg

from app.parser import SensorReading


def bulk_upsert_readings(database_url: str, readings: list[SensorReading]) -> int:
    if not readings:
        return 0

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TEMP TABLE tmp_sensor_data (
                    station_code TEXT NOT NULL,
                    time TIMESTAMPTZ NOT NULL,
                    temperature DOUBLE PRECISION,
                    humidity DOUBLE PRECISION,
                    wind_speed DOUBLE PRECISION,
                    pm25 DOUBLE PRECISION
                ) ON COMMIT DROP
                """
            )
            cursor.execute(
                """
                ALTER TABLE sensor_data ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
                ALTER TABLE latest_station_readings ADD COLUMN IF NOT EXISTS wind_speed DOUBLE PRECISION;
                """
            )
            buffer = StringIO()
            for reading in readings:
                buffer.write(
                    "\t".join(
                        [
                            reading.station_code,
                            reading.time.isoformat(),
                            _copy_value(reading.temperature),
                            _copy_value(reading.humidity),
                            _copy_value(reading.wind_speed),
                            _copy_value(reading.pm25),
                        ]
                    )
                    + "\n"
                )
            buffer.seek(0)
            with cursor.copy(
                "COPY tmp_sensor_data (station_code, time, temperature, humidity, wind_speed, pm25) FROM STDIN"
            ) as copy:
                copy.write(buffer.read())

            cursor.execute(
                """
                INSERT INTO stations (code, name, status, metadata)
                SELECT DISTINCT
                    t.station_code,
                    'IoT Sensor ' || upper(replace(t.station_code, '_', ' ')),
                    'active',
                    jsonb_build_object('type', 'Không khí xung quanh', 'source', 'iot-simulator')
                FROM tmp_sensor_data t
                ON CONFLICT (code) DO NOTHING
                """
            )

            cursor.execute(
                """
                INSERT INTO sensor_data (station_id, time, temperature, humidity, wind_speed, pm25)
                SELECT s.id, t.time, t.temperature, t.humidity, t.wind_speed, t.pm25
                FROM tmp_sensor_data t
                JOIN stations s ON s.code = t.station_code
                ON CONFLICT (station_id, time) DO UPDATE SET
                    temperature = EXCLUDED.temperature,
                    humidity = EXCLUDED.humidity,
                    wind_speed = EXCLUDED.wind_speed,
                    pm25 = EXCLUDED.pm25,
                    received_at = now()
                """
            )
            inserted = cursor.rowcount

            cursor.execute(
                """
                INSERT INTO latest_station_readings (station_id, time, temperature, humidity, wind_speed, pm25, status)
                SELECT DISTINCT ON (s.id)
                    s.id,
                    t.time,
                    t.temperature,
                    t.humidity,
                    t.wind_speed,
                    t.pm25,
                    'online'
                FROM tmp_sensor_data t
                JOIN stations s ON s.code = t.station_code
                ORDER BY s.id, t.time DESC
                ON CONFLICT (station_id) DO UPDATE SET
                    time = EXCLUDED.time,
                    temperature = EXCLUDED.temperature,
                    humidity = EXCLUDED.humidity,
                    wind_speed = EXCLUDED.wind_speed,
                    pm25 = EXCLUDED.pm25,
                    status = EXCLUDED.status,
                    updated_at = now()
                WHERE latest_station_readings.time <= EXCLUDED.time
                """
            )

            cursor.execute(
                """
                UPDATE stations s
                SET last_seen_at = latest.time,
                    updated_at = now()
                FROM (
                    SELECT s2.id AS station_id, max(t.time) AS time
                    FROM tmp_sensor_data t
                    JOIN stations s2 ON s2.code = t.station_code
                    GROUP BY s2.id
                ) latest
                WHERE s.id = latest.station_id
                  AND (s.last_seen_at IS NULL OR s.last_seen_at <= latest.time)
                """
            )
            return inserted


def upsert_ftp_file_index(database_url: str, rows: list[dict]) -> None:
    if not rows:
        return
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO ftp_files
                    (station_id, remote_path, name, entry_type, size_bytes, modified_at, last_seen_at, updated_at)
                VALUES (%(station_id)s, %(remote_path)s, %(name)s, %(entry_type)s, %(size_bytes)s, %(modified_at)s, now(), now())
                ON CONFLICT (station_id, remote_path) DO UPDATE SET
                    name = EXCLUDED.name,
                    entry_type = EXCLUDED.entry_type,
                    size_bytes = EXCLUDED.size_bytes,
                    modified_at = EXCLUDED.modified_at,
                    last_seen_at = now(),
                    updated_at = now()
                """,
                rows,
            )
            station_id = rows[0]["station_id"]
            cursor.execute(
                "DELETE FROM ftp_files WHERE station_id = %s AND last_seen_at < now() - interval '24 hours'",
                (station_id,),
            )


def _copy_value(value: float | None) -> str:
    return "\\N" if value is None else str(value)
