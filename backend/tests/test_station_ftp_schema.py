from pathlib import Path


def test_schema_contains_independent_ftp_catalog_and_station_assignment():
    schema = Path("db/init/001_schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS ftp_servers" in schema
    assert "CREATE TABLE IF NOT EXISTS station_ftp_assignments" in schema
    assert "ftp_server_id BIGINT NOT NULL REFERENCES ftp_servers(id)" in schema
    assert "INSERT INTO ftp_servers" in schema
    assert "INSERT INTO station_ftp_assignments" in schema
