import pytest

from app.ftp_browser import normalize_ftp_path


def test_normalize_ftp_path_allows_sensor_data_folder():
    assert normalize_ftp_path("/data/sensor_001") == "/data/sensor_001"


def test_normalize_ftp_path_rejects_path_traversal():
    with pytest.raises(ValueError, match="FTP path must stay under /data"):
        normalize_ftp_path("/data/../etc")


def test_normalize_ftp_path_defaults_to_data_root():
    assert normalize_ftp_path("") == "/data"
