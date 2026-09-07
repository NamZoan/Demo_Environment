from pathlib import Path


def test_schema_contains_station_ftp_file_index():
    schema = Path("db/init/001_schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS ftp_files" in schema
    assert "station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE" in schema
    assert "UNIQUE (station_id, remote_path)" in schema
