from __future__ import annotations

import logging
import os
import posixpath
import random
import shutil
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

import psycopg

from app.db import bulk_upsert_readings
from app.parser import parse_sensor_file
from app.retry import retry_call


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://monitor:monitor@localhost:5432/environment")
FTP_INCOMING_DIR = Path(os.getenv("FTP_INCOMING_DIR", "/ftp/data"))
FTP_ARCHIVE_DIR = Path(os.getenv("FTP_ARCHIVE_DIR", "/ftp/archive"))
FTP_ERROR_DIR = Path(os.getenv("FTP_ERROR_DIR", "/ftp/error"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))
ARCHIVE_PROCESSED_FILES = os.getenv("ARCHIVE_PROCESSED_FILES", "true").lower() == "true"
FTP_SERVER_ID = int(os.getenv("FTP_SERVER_ID", "0"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_INITIAL_DELAY_SECONDS = float(os.getenv("RETRY_INITIAL_DELAY_SECONDS", "1"))
RETRY_MAX_DELAY_SECONDS = float(os.getenv("RETRY_MAX_DELAY_SECONDS", "30"))
PROCESSED_FILE_SIGNATURES: set[tuple[str, int, int]] = set()


class UnassignedFolderError(ValueError):
    """The file must wait until its FTP folder is assigned to a station."""


def main() -> None:
    FTP_INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    FTP_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FTP_ERROR_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("FTP worker started. Watching %s", FTP_INCOMING_DIR)
    run_forever()


def run_forever(*, sleep: Callable[[float], None] = time.sleep) -> None:
    while True:
        run_cycle()
        sleep(POLL_SECONDS)


def run_cycle() -> None:
    try:
        process_once()
    except Exception:
        logger.exception("Worker cycle failed")


def process_once() -> None:
    folder_station_codes = retry_call(
        fetch_folder_station_codes,
        attempts=RETRY_ATTEMPTS,
        initial_delay=RETRY_INITIAL_DELAY_SECONDS,
        max_delay=RETRY_MAX_DELAY_SECONDS,
        sleep=time.sleep,
        random_value=random.random,
    )
    for path in sorted(FTP_INCOMING_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".json"}:
            continue
        stat = path.stat()
        signature = (str(path), stat.st_mtime_ns, stat.st_size)
        if not ARCHIVE_PROCESSED_FILES and signature in PROCESSED_FILE_SIGNATURES:
            continue
        destination_dir = FTP_ARCHIVE_DIR
        try:
            station_code = station_code_for_path(path, folder_station_codes)
        except UnassignedFolderError:
            logger.info("Waiting for station assignment before processing %s", path)
            continue
        try:
            readings = parse_sensor_file(path)
            if station_code:
                readings = [replace(reading, station_code=station_code) for reading in readings]
            inserted = bulk_upsert_readings(DATABASE_URL, readings)
            logger.info("Processed %s with %s rows", path.name, inserted)
            if not ARCHIVE_PROCESSED_FILES:
                PROCESSED_FILE_SIGNATURES.add(signature)
                continue
        except Exception:
            destination_dir = FTP_ERROR_DIR
            logger.exception("Failed to process %s", path)
        finally:
            if ARCHIVE_PROCESSED_FILES or destination_dir == FTP_ERROR_DIR:
                target = destination_dir / path.name
                if target.exists():
                    target = destination_dir / f"{path.stem}-{int(time.time())}{path.suffix}"
                shutil.move(str(path), str(target))


def fetch_folder_station_codes() -> dict[str, str]:
    if not FTP_SERVER_ID:
        return {}
    with psycopg.connect(DATABASE_URL) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.root_path, s.code
                FROM station_ftp_assignments a
                JOIN stations s ON s.id = a.station_id
                WHERE a.ftp_server_id = %s AND a.root_path <> '/data'
                """,
                (FTP_SERVER_ID,),
            )
            return {root_path: station_code for root_path, station_code in cursor.fetchall()}


def station_code_for_path(path: Path, folder_station_codes: dict[str, str]) -> str | None:
    if not FTP_SERVER_ID and not folder_station_codes:
        return None
    relative = path.relative_to(FTP_INCOMING_DIR)
    folder_path = posixpath.join("/data", relative.parent.as_posix())
    matches = [
        (assigned_folder, station_code)
        for assigned_folder, station_code in folder_station_codes.items()
        if folder_path == assigned_folder or folder_path.startswith(f"{assigned_folder}/")
    ]
    if not matches:
        raise UnassignedFolderError(f"FTP folder is not assigned to a station: {folder_path}")
    return max(matches, key=lambda item: len(item[0]))[1]


if __name__ == "__main__":
    main()
