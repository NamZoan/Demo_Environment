from __future__ import annotations

import logging
import os
import tempfile
import time
from ftplib import FTP, error_perm
from pathlib import Path

from app.db import bulk_upsert_readings
from app.parser import parse_sensor_file


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
    with _connect() as ftp:
        for remote_path in _walk_files(ftp, FTP_ROOT_DIR):
            if remote_path in processed_paths or not is_supported_data_file(remote_path):
                continue
            try:
                inserted = _process_remote_file(ftp, remote_path)
                processed_paths.add(remote_path)
                processed_count += 1
                logger.info("Processed %s with %s rows", remote_path, inserted)
            except Exception:
                logger.exception("Failed to process FTP file %s", remote_path)
    return processed_count


def _connect() -> FTP:
    ftp = FTP()
    ftp.connect(FTP_HOST, FTP_PORT, timeout=FTP_TIMEOUT_SECONDS)
    ftp.login(FTP_USER, FTP_PASSWORD)
    ftp.set_pasv(True)
    return ftp


def _walk_files(ftp: FTP, root: str) -> list[str]:
    paths: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        for item in _list_dir(ftp, current):
            if item["type"] == "folder":
                stack.append(item["path"])
            else:
                paths.append(item["path"])
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
        entries.append({"path": child_path, "type": "folder" if facts.get("type") == "dir" else "file"})
    return entries


def _list_dir_with_nlst(ftp: FTP, path: str) -> list[dict[str, str]]:
    entries = []
    for child_path in ftp.nlst(path):
        if child_path.rstrip("/").endswith(("/.", "/..")):
            continue
        entries.append({"path": child_path, "type": "folder" if _is_directory(ftp, child_path) else "file"})
    return entries


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
        with local_path.open("wb") as file:
            ftp.retrbinary(f"RETR {remote_path}", file.write)
        readings = parse_sensor_file(local_path)
        return bulk_upsert_readings(DATABASE_URL, readings)


if __name__ == "__main__":
    main()
