from datetime import datetime, timezone
from pathlib import Path

import app.worker as worker
from app.parser import SensorReading


def _reading(station_code):
    return SensorReading(
        station_code=station_code,
        time=datetime(2026, 9, 1, tzinfo=timezone.utc),
        temperature=30.0,
        humidity=70.0,
        wind_speed=1.0,
        pm25=10.0,
    )


def test_process_once_keeps_successful_file_and_does_not_process_it_again(monkeypatch, tmp_path):
    incoming = tmp_path / "data"
    incoming.mkdir()
    archive = tmp_path / "archive"
    error = tmp_path / "error"
    source = incoming / "sensor_001" / "reading.csv"
    source.parent.mkdir()
    source.write_text("sensor_id,timestamp\nsensor_001,2026-09-01T00:00:00+00:00\n", encoding="utf-8")
    calls = []

    monkeypatch.setattr(worker, "FTP_INCOMING_DIR", incoming)
    monkeypatch.setattr(worker, "FTP_ARCHIVE_DIR", archive)
    monkeypatch.setattr(worker, "FTP_ERROR_DIR", error)
    monkeypatch.setattr(worker, "ARCHIVE_PROCESSED_FILES", False)
    monkeypatch.setattr(worker, "bulk_upsert_readings", lambda _url, readings: calls.append(readings) or 1)
    monkeypatch.setattr(worker, "parse_sensor_file", lambda path: [Path(path).name])
    worker.PROCESSED_FILE_SIGNATURES.clear()

    worker.process_once()
    worker.process_once()

    assert source.exists()
    assert not archive.exists()
    assert len(calls) == 1


def test_process_once_maps_folder_to_configured_station(monkeypatch, tmp_path):
    incoming = tmp_path / "data"
    source = incoming / "sensor_001" / "reading.csv"
    source.parent.mkdir(parents=True)
    source.write_text("unused", encoding="utf-8")
    calls = []

    monkeypatch.setattr(worker, "FTP_INCOMING_DIR", incoming)
    monkeypatch.setattr(worker, "FTP_ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(worker, "FTP_ERROR_DIR", tmp_path / "error")
    (tmp_path / "error").mkdir()
    monkeypatch.setattr(worker, "ARCHIVE_PROCESSED_FILES", False)
    monkeypatch.setattr(worker, "FTP_SERVER_ID", 7)
    monkeypatch.setattr(worker, "fetch_folder_station_codes", lambda: {"/data/sensor_001": "station-renamed"})
    monkeypatch.setattr(worker, "parse_sensor_file", lambda path: [_reading("sensor_001")])
    monkeypatch.setattr(worker, "bulk_upsert_readings", lambda _url, readings: calls.append(readings) or 1)
    worker.PROCESSED_FILE_SIGNATURES.clear()

    worker.process_once()

    assert calls[0][0].station_code == "station-renamed"


def test_process_once_rejects_folder_without_station_assignment(monkeypatch, tmp_path):
    incoming = tmp_path / "data"
    source = incoming / "sensor_001" / "reading.csv"
    source.parent.mkdir(parents=True)
    source.write_text("unused", encoding="utf-8")
    calls = []

    monkeypatch.setattr(worker, "FTP_INCOMING_DIR", incoming)
    monkeypatch.setattr(worker, "FTP_ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(worker, "FTP_ERROR_DIR", tmp_path / "error")
    (tmp_path / "error").mkdir()
    monkeypatch.setattr(worker, "ARCHIVE_PROCESSED_FILES", False)
    monkeypatch.setattr(worker, "FTP_SERVER_ID", 7)
    monkeypatch.setattr(worker, "fetch_folder_station_codes", lambda: {})
    monkeypatch.setattr(worker, "parse_sensor_file", lambda path: [_reading("sensor_001")])
    monkeypatch.setattr(worker, "bulk_upsert_readings", lambda _url, readings: calls.append(readings) or 1)
    worker.PROCESSED_FILE_SIGNATURES.clear()

    worker.process_once()

    assert calls == []
    assert (tmp_path / "error" / "reading.csv").exists()
