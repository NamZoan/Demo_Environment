from app.ftp_poller import is_supported_data_file
import inspect
import app.ftp_poller as ftp_poller


def test_is_supported_data_file_accepts_sensor_csv_under_data_root():
    assert is_supported_data_file("/data/sensor_001/sensor_001_20260905_103000.csv") is True


def test_is_supported_data_file_rejects_archive_and_non_data_files():
    assert is_supported_data_file("/archive/sensor_001/file.csv") is False
    assert is_supported_data_file("/data/sensor_001/readme.txt") is False


def test_worker_resolves_ftp_servers_through_station_assignments():
    source = inspect.getsource(ftp_poller._fetch_station_ftp_configs)

    assert "FROM station_ftp_assignments a" in source
    assert "JOIN ftp_servers f ON f.id = a.ftp_server_id" in source
