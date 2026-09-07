from __future__ import annotations

import logging
import os
import random
import tempfile
import time
from ftplib import FTP, error_perm
from pathlib import Path

from app.db import bulk_upsert_readings, upsert_ftp_file_index
from app.ftp_index import build_file_index_rows
from app.parser import parse_sensor_file
from app.retry import retry_call


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://monitor:monitor@localhost:5432/environment")
FTP_HOST = os.getenv("FTP_HOST", "127.0.0.1")
FTP_PORT = int(os.getenv("FTP_PORT", "21"))
FTP_USER = os.getenv("FTP_USER", "station")
FTP_PASSWORD = os.getenv("FTP_PASSWORD", "stationpass")
FTP_ROOT_DIR = os.getenv("FTP_ROOT_DIR", "/data")
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
FTP_TIMEOUT_SECONDS = int(os.getenv("FTP_TIMEOUT_SECONDS", "10"))
FTP_CREDENTIALS_KEY = os.getenv("FTP_CREDENTIALS_KEY", "development-only-change-me")
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_INITIAL_DELAY_SECONDS = float(os.getenv("RETRY_INITIAL_DELAY_SECONDS", "1"))
RETRY_MAX_DELAY_SECONDS = float(os.getenv("RETRY_MAX_DELAY_SECONDS", "30"))
RETRY_SLEEP = time.sleep


def is_supported_data_file(path: str) -> bool:
    normalized = path.lower()
    return normalized.startswith("/data/") and normalized.endswith((".csv", ".json"))


def main() -> None:
    processed_paths: set[str] = set()
    logger.info("FTP protocol poller started. Watching %s on %s:%s", FTP_ROOT_DIR, FTP_HOST, FTP_PORT)
    while True:
        try:
            processed = process_once(processed_paths)
            if processed:
                logger.info("Processed %s new FTP files", processed)
        except Exception:
            logger.exception("FTP poll cycle failed")
        time.sleep(POLL_SECONDS)


def process_once(processed_paths: set[str]) -> int:
    processed_count = 0
    configs = _retry(_fetch_station_ftp_configs)
    if not configs:
        configs = [{"station_id": None, "host": FTP_HOST, "port": FTP_PORT, "user": FTP_USER, "password": FTP_PASSWORD, "root_path": FTP_ROOT_DIR, "timeout_seconds": FTP_TIMEOUT_SECONDS}]
    for config in configs:
        try:
            with _retry(lambda: _connect(config)) as ftp:
                entries = _walk_files(ftp, config["root_path"])
                if config["station_id"] is not None:
                    try:
                        _retry(lambda: upsert_ftp_file_index(DATABASE_URL, build_file_index_rows(config["station_id"], entries)))
                    except Exception:
                        logger.exception("Failed to index station %s FTP server %s", config["station_id"], config["host"])
                for entry in entries:
                    remote_path = entry["path"]
                    processed_key = f'{config["station_id"]}:{remote_path}'
                    if processed_key in processed_paths or not is_supported_data_file(remote_path):
                        continue
                    try:
                        inserted = _process_remote_file(ftp, remote_path)
                        processed_paths.add(processed_key)
                        processed_count += 1
                        logger.info("Processed station %s file %s with %s rows", config["station_id"] or "legacy", remote_path, inserted)
                    except Exception:
                        logger.exception("Failed to process station %s FTP file %s", config["station_id"], remote_path)
        except Exception:
            logger.exception("Failed to process station %s FTP server %s", config["station_id"], config["host"])
    return processed_count


def _retry(operation):
    return retry_call(
        operation,
        attempts=RETRY_ATTEMPTS,
        initial_delay=RETRY_INITIAL_DELAY_SECONDS,
        max_delay=RETRY_MAX_DELAY_SECONDS,
        sleep=RETRY_SLEEP,
        random_value=random.random,
    )


def _connect(config: dict) -> FTP:
    ftp = FTP()
    ftp.connect(config["host"], config["port"], timeout=config["timeout_seconds"])
    ftp.login(config["user"], config["password"])
    ftp.set_pasv(True)
    return ftp


def _fetch_station_ftp_configs() -> list[dict]:
    import psycopg

    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.station_id, f.host, f.port, f.username AS user,
                       pgp_sym_decrypt(f.password_encrypted, %s) AS password,
                       a.root_path, f.timeout_seconds
                FROM station_ftp_assignments a
                JOIN ftp_servers f ON f.id = a.ftp_server_id
                WHERE f.status = 'active'
                ORDER BY a.station_id
                """,
                (FTP_CREDENTIALS_KEY,),
            )
            return [dict(zip(("station_id", "host", "port", "user", "password", "root_path", "timeout_seconds"), row)) for row in cursor.fetchall()]


def _walk_files(ftp: FTP, root: str) -> list[dict]:
    paths: list[dict] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for item in _list_dir(ftp, current):
            if item["type"] == "folder":
                stack.append(item["path"])
            else:
                paths.append(item)
    return sorted(paths)


def _list_dir(ftp: FTP, path: str) -> list[dict[str, str]]:
    try:
        return _list_dir_with_mlsd(ftp, path)
    except Exception:
        return _list_dir_with_nlst(ftp, path)


def _list_dir_with_mlsd(ftp: FTP, path: str) -> list[dict[str, str]]:
    entries = []
    for name, facts in ftp.mlsd(path):
        if name in {".", ".."}:
            continue
        child_path = f"{path.rstrip('/')}/{name}"
        entries.append({"path": child_path, "type": "folder" if facts.get("type") == "dir" else "file", "size": _optional_int(facts.get("size")), "modified": facts.get("modify")})
    return entries


def _list_dir_with_nlst(ftp: FTP, path: str) -> list[dict[str, str]]:
    entries = []
    for child_path in ftp.nlst(path):
        if child_path.rstrip("/").endswith(("/.", "/..")):
            continue
        entries.append({"path": child_path, "type": "folder" if _is_directory(ftp, child_path) else "file", "size": None, "modified": None})
    return entries


def _optional_int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _is_directory(ftp: FTP, path: str) -> bool:
    current = ftp.pwd()
    try:
        ftp.cwd(path)
        return True
    except error_perm:
        return False
    finally:
        ftp.cwd(current)


def _process_remote_file(ftp: FTP, remote_path: str) -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / Path(remote_path).name
        _retry(lambda: _download_remote_file(ftp, remote_path, local_path))
        readings = parse_sensor_file(local_path)
        return _retry(lambda: bulk_upsert_readings(DATABASE_URL, readings))


def _download_remote_file(ftp: FTP, remote_path: str, local_path: Path) -> None:
    with local_path.open("wb") as file:
        ftp.retrbinary(f"RETR {remote_path}", file.write)


if __name__ == "__main__":
    main()
