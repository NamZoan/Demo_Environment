from app.ftp_poller import is_supported_data_file
import inspect
import app.ftp_poller as ftp_poller


class _FakeFtp:
    def __init__(self, files):
        self.files = files

    def __enter__(self):
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        return False

    def mlsd(self, _path):
        return [
            (entry["path"].removeprefix("/data/"), {"type": "file", "size": str(entry["size"]), "modify": entry["modified"]})
            for entry in self.files
        ]

    def retrbinary(self, _command, _callback):
        return None


class _DownloadFtp:
    def __init__(self, failures=0):
        self.failures = failures
        self.attempts = 0

    def retrbinary(self, _command, callback):
        self.attempts += 1
        if self.attempts <= self.failures:
            raise ConnectionError("FTP unavailable")
        callback(
            b"station_code,time,temperature,humidity,pm25\n"
            b"HN001,2026-09-05T00:01:00Z,30.5,70.2,18.4\n"
        )


def test_is_supported_data_file_accepts_sensor_csv_under_data_root():
    assert is_supported_data_file("/data/sensor_001/sensor_001_20260905_103000.csv") is True


def test_is_supported_data_file_rejects_archive_and_non_data_files():
    assert is_supported_data_file("/archive/sensor_001/file.csv") is False
    assert is_supported_data_file("/data/sensor_001/readme.txt") is False


def test_worker_resolves_ftp_servers_through_station_assignments():
    source = inspect.getsource(ftp_poller._fetch_station_ftp_configs)

    assert "FROM station_ftp_assignments a" in source
    assert "JOIN ftp_servers f ON f.id = a.ftp_server_id" in source


def test_process_once_retries_ftp_connection_until_file_is_processed(monkeypatch):
    attempts = []
    index_calls = []
    processed_paths = set()
    ftp = _FakeFtp(files=[{"path": "/data/sensor_001/reading.csv", "type": "file", "size": 1, "modified": None}])

    def connect(_config):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("FTP unavailable")
        return ftp

    monkeypatch.setattr(ftp_poller, "_fetch_station_ftp_configs", lambda: [{"station_id": 7, "host": "ftp", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1}])
    monkeypatch.setattr(ftp_poller, "_connect", connect)
    monkeypatch.setattr(ftp_poller, "upsert_ftp_file_index", lambda _url, rows: index_calls.append(rows))
    monkeypatch.setattr(ftp_poller, "_process_remote_file", lambda _ftp, _path: 1)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller.process_once(processed_paths) == 1
    assert len(attempts) == 2
    assert len(index_calls) == 1
    assert processed_paths == {"7:/data/sensor_001/reading.csv"}


def test_process_once_continues_to_next_ftp_config_after_exhausted_retries(monkeypatch):
    processed_paths = set()
    index_calls = []
    configs = [
        {"station_id": 1, "host": "bad", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1},
        {"station_id": 2, "host": "good", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1},
    ]
    good_ftp = _FakeFtp(files=[{"path": "/data/sensor_002/reading.csv", "type": "file", "size": 1, "modified": None}])

    monkeypatch.setattr(ftp_poller, "_fetch_station_ftp_configs", lambda: configs)
    monkeypatch.setattr(ftp_poller, "_connect", lambda config: (_ for _ in ()).throw(ConnectionError("bad")) if config["station_id"] == 1 else good_ftp)
    monkeypatch.setattr(ftp_poller, "upsert_ftp_file_index", lambda _url, rows: index_calls.append(rows))
    monkeypatch.setattr(ftp_poller, "_process_remote_file", lambda _ftp, _path: 1)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller.process_once(processed_paths) == 1
    assert len(index_calls) == 1
    assert processed_paths == {"2:/data/sensor_002/reading.csv"}


def test_process_remote_file_retries_download_before_parsing_and_upsert(monkeypatch):
    ftp = _DownloadFtp(failures=1)
    upsert_calls = []

    monkeypatch.setattr(ftp_poller, "bulk_upsert_readings", lambda _url, readings: upsert_calls.append(readings) or 1)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller._process_remote_file(ftp, "/data/sensor_001/reading.csv") == 1
    assert ftp.attempts == 2
    assert len(upsert_calls) == 1


def test_process_remote_file_retries_reading_persistence(monkeypatch):
    ftp = _DownloadFtp()
    upsert_attempts = []

    def upsert(_url, _readings):
        upsert_attempts.append(1)
        if len(upsert_attempts) == 1:
            raise ConnectionError("database unavailable")
        return 1

    monkeypatch.setattr(ftp_poller, "bulk_upsert_readings", upsert)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller._process_remote_file(ftp, "/data/sensor_001/reading.csv") == 1
    assert ftp.attempts == 1
    assert len(upsert_attempts) == 2


def test_process_once_leaves_path_unprocessed_when_persistence_retries_exhaust(monkeypatch):
    processed_paths = set()
    ftp = _DownloadFtp()
    upsert_attempts = []
    config = {"station_id": 7, "host": "ftp", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1}

    def upsert(_url, _readings):
        upsert_attempts.append(1)
        raise ConnectionError("database unavailable")

    monkeypatch.setattr(ftp_poller, "_fetch_station_ftp_configs", lambda: [config])
    monkeypatch.setattr(ftp_poller, "_connect", lambda _config: _FakeFtp(files=[{"path": "/data/sensor_001/reading.csv", "type": "file", "size": 1, "modified": None}]))
    monkeypatch.setattr(ftp_poller, "upsert_ftp_file_index", lambda _url, _rows: None)
    monkeypatch.setattr(ftp_poller, "_download_remote_file", lambda _ftp, _path, local_path: local_path.write_bytes(b"station_code,time,temperature,humidity,pm25\nHN001,2026-09-05T00:01:00Z,30.5,70.2,18.4\n"))
    monkeypatch.setattr(ftp_poller, "bulk_upsert_readings", upsert)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller.process_once(processed_paths) == 0
    assert len(upsert_attempts) == 2
    assert processed_paths == set()
