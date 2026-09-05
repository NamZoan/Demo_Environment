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
                    pm25 DOUBLE PRECISION
                ) ON COMMIT DROP
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
                            _copy_value(reading.pm25),
                        ]
                    )
                    + "\n"
                )
            buffer.seek(0)
            with cursor.copy(
                "COPY tmp_sensor_data (station_code, time, temperature, humidity, pm25) FROM STDIN"
            ) as copy:
                copy.write(buffer.read())

            cursor.execute(
                """
                INSERT INTO sensor_data (station_id, time, temperature, humidity, pm25)
                SELECT s.id, t.time, t.temperature, t.humidity, t.pm25
                FROM tmp_sensor_data t
                JOIN stations s ON s.code = t.station_code
                ON CONFLICT (station_id, time) DO UPDATE SET
                    temperature = EXCLUDED.temperature,
                    humidity = EXCLUDED.humidity,
                    pm25 = EXCLUDED.pm25,
                    received_at = now()
                """
            )
            return cursor.rowcount


def _copy_value(value: float | None) -> str:
    return "\\N" if value is None else str(value)

