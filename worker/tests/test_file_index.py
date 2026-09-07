from app.ftp_index import build_file_index_rows


def test_build_file_index_rows_normalizes_discovered_files():
    rows = build_file_index_rows(
        station_id=7,
        entries=[
            {"path": "/data/env-007/a.csv", "type": "file", "size": 128, "modified": "20260907110000"},
            {"path": "/data/env-007/archive", "type": "folder", "size": None, "modified": None},
        ],
    )

    assert rows == [
        {
            "station_id": 7,
            "remote_path": "/data/env-007/a.csv",
            "name": "a.csv",
            "entry_type": "file",
            "size_bytes": 128,
            "modified_at": "20260907110000",
        },
        {
            "station_id": 7,
            "remote_path": "/data/env-007/archive",
            "name": "archive",
            "entry_type": "folder",
            "size_bytes": None,
            "modified_at": None,
        },
    ]


def test_build_file_index_rows_deduplicates_remote_paths():
    rows = build_file_index_rows(
        station_id=7,
        entries=[
            {"path": "/data/env-007/a.csv", "type": "file", "size": 1, "modified": None},
            {"path": "/data/env-007/a.csv", "type": "file", "size": 2, "modified": None},
        ],
    )

    assert len(rows) == 1
    assert rows[0]["size_bytes"] == 1
