import csv
import random
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from simulator import build_csv_content, build_local_filename, build_sensor_ids, generate_sensor_reading, remote_sensor_dir


def test_generate_sensor_reading_uses_expected_ranges_and_iso_timestamp():
    sampled_at = datetime(2026, 9, 5, 10, 30, 0, tzinfo=timezone.utc)

    reading = generate_sensor_reading("sensor_001", sampled_at, random.Random(7))

    assert reading["sensor_id"] == "sensor_001"
    assert reading["timestamp"] == "2026-09-05T10:30:00+00:00"
    assert 15.0 <= reading["temperature"] <= 45.0
    assert 30.0 <= reading["humidity"] <= 95.0
    assert 0.0 <= reading["wind_speed"] <= 50.0
    assert 5.0 <= reading["pm25"] <= 150.0


def test_build_csv_content_writes_required_columns_in_order():
    reading = {
        "sensor_id": "sensor_042",
        "timestamp": "2026-09-05T10:30:00+00:00",
        "temperature": 31.2,
        "humidity": 72.5,
        "wind_speed": 12.4,
        "pm25": 34.8,
    }

    content = build_csv_content(reading)

    rows = list(csv.reader(StringIO(content)))
    assert rows[0] == ["sensor_id", "timestamp", "temperature", "humidity", "wind_speed", "pm25"]
    assert rows[1] == ["sensor_042", "2026-09-05T10:30:00+00:00", "31.2", "72.5", "12.4", "34.8"]


def test_build_local_filename_contains_sensor_id_and_utc_timestamp():
    sampled_at = datetime(2026, 9, 5, 10, 30, 0, tzinfo=timezone.utc)

    filename = build_local_filename("sensor_005", sampled_at)

    assert filename == "sensor_005_20260905_103000.csv"


def test_remote_sensor_dir_uses_sensor_specific_data_directory():
    assert remote_sensor_dir("/data", "sensor_100") == "/data/sensor_100"


def test_build_sensor_ids_supports_unique_ranges_per_ftp():
    assert build_sensor_ids(3, 2) == ["sensor_003", "sensor_004"]
