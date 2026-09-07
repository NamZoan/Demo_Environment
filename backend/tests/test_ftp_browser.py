import pytest

from app.ftp_browser import normalize_ftp_csv_file_path, normalize_ftp_path, normalize_ftp_preview_file_path


def test_normalize_ftp_path_allows_sensor_data_folder():
    assert normalize_ftp_path("/data/sensor_001") == "/data/sensor_001"


def test_normalize_ftp_path_rejects_path_traversal():
    with pytest.raises(ValueError, match="FTP path must stay under /data"):
        normalize_ftp_path("/data/../etc")


def test_normalize_ftp_path_defaults_to_data_root():
    assert normalize_ftp_path("") == "/data"


def test_normalize_ftp_csv_file_path_allows_csv_under_data_root():
    path = "/data/sensor_001/sensor_001_20260905_103000.csv"

    assert normalize_ftp_csv_file_path(path) == path


def test_normalize_ftp_csv_file_path_rejects_non_csv_file():
    with pytest.raises(ValueError, match="Only CSV files can be previewed"):
        normalize_ftp_csv_file_path("/data/sensor_001/readme.txt")


@pytest.mark.parametrize("filename", ["readme.txt", "payload.json", "worker.log"])
def test_normalize_ftp_preview_file_path_allows_text_files(filename):
    assert normalize_ftp_preview_file_path(f"/data/sensor_001/{filename}").endswith(filename)


def test_normalize_ftp_preview_file_path_rejects_binary_files():
    with pytest.raises(ValueError, match="Only text files can be previewed"):
        normalize_ftp_preview_file_path("/data/sensor_001/archive.zip")
