from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

from app.db import bulk_upsert_readings
from app.parser import parse_sensor_file


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://monitor:monitor@localhost:5432/environment")
FTP_INCOMING_DIR = Path(os.getenv("FTP_INCOMING_DIR", "/ftp/data"))
FTP_ARCHIVE_DIR = Path(os.getenv("FTP_ARCHIVE_DIR", "/ftp/archive"))
FTP_ERROR_DIR = Path(os.getenv("FTP_ERROR_DIR", "/ftp/error"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "5"))


def main() -> None:
    FTP_INCOMING_DIR.mkdir(parents=True, exist_ok=True)
    FTP_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    FTP_ERROR_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("FTP worker started. Watching %s", FTP_INCOMING_DIR)
    while True:
        process_once()
        time.sleep(POLL_SECONDS)


def process_once() -> None:
    for path in sorted(FTP_INCOMING_DIR.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".csv", ".json"}:
            continue
        destination_dir = FTP_ARCHIVE_DIR
        try:
            readings = parse_sensor_file(path)
            inserted = bulk_upsert_readings(DATABASE_URL, readings)
            logger.info("Processed %s with %s rows", path.name, inserted)
        except Exception:
            destination_dir = FTP_ERROR_DIR
            logger.exception("Failed to process %s", path)
        finally:
            target = destination_dir / path.name
            if target.exists():
                target = destination_dir / f"{path.stem}-{int(time.time())}{path.suffix}"
            shutil.move(str(path), str(target))


if __name__ == "__main__":
    main()
