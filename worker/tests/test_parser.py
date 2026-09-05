import json

from app.parser import parse_sensor_file


def test_parse_csv_sensor_file(tmp_path):
    file_path = tmp_path / "station.csv"
    file_path.write_text(
        "station_code,time,temperature,humidity,pm25\n"
        "HN001,2026-09-05T00:01:00Z,30.5,70.2,18.4\n",
        encoding="utf-8",
    )

    readings = parse_sensor_file(file_path)

    assert len(readings) == 1
    assert readings[0].station_code == "HN001"
    assert readings[0].temperature == 30.5
    assert readings[0].humidity == 70.2
    assert readings[0].pm25 == 18.4


def test_parse_iot_simulator_csv_sensor_file(tmp_path):
    file_path = tmp_path / "sensor_001_20260905_080000.csv"
    file_path.write_text(
        "sensor_id,timestamp,temperature,humidity,wind_speed,pm25\n"
        "sensor_001,2026-09-05T08:00:00+00:00,31.2,68.5,12.4,42.8\n",
        encoding="utf-8",
    )

    readings = parse_sensor_file(file_path)

    assert len(readings) == 1
    assert readings[0].station_code == "sensor_001"
    assert readings[0].time.isoformat().startswith("2026-09-05T08:00:00")
    assert readings[0].temperature == 31.2
    assert readings[0].humidity == 68.5
    assert readings[0].wind_speed == 12.4
    assert readings[0].pm25 == 42.8


def test_parse_json_sensor_file(tmp_path):
    file_path = tmp_path / "station.json"
    file_path.write_text(
        json.dumps(
            [
                {
                    "station_code": "HN001",
                    "time": "2026-09-05T00:01:00Z",
                    "temperature": 30.5,
                    "humidity": 70.2,
                    "pm25": 18.4,
                }
            ]
        ),
        encoding="utf-8",
    )

    readings = parse_sensor_file(file_path)

    assert len(readings) == 1
    assert readings[0].station_code == "HN001"
    assert readings[0].time.isoformat().startswith("2026-09-05T00:01:00")
