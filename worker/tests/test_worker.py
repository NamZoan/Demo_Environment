from pathlib import Path

import app.worker as worker


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
