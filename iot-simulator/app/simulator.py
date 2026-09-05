from __future__ import annotations

import asyncio
import csv
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from ftplib import FTP
from io import StringIO
from pathlib import Path


CSV_COLUMNS = ["sensor_id", "timestamp", "temperature", "humidity", "wind_speed", "pm25"]


@dataclass(frozen=True)
class Settings:
    sensor_count: int = int(os.getenv("SENSOR_COUNT", "100"))
    interval_seconds: int = int(os.getenv("INTERVAL_SECONDS", "60"))
    ftp_host: str = os.getenv("FTP_HOST", "ftp-server")
    ftp_port: int = int(os.getenv("FTP_PORT", "21"))
    ftp_user: str = os.getenv("FTP_USER", "station")
    ftp_password: str = os.getenv("FTP_PASSWORD", "stationpass")
    remote_base_dir: str = os.getenv("REMOTE_BASE_DIR", "/data")
    local_outbox_dir: Path = Path(os.getenv("LOCAL_OUTBOX_DIR", "/tmp/iot-outbox"))
    upload_retries: int = int(os.getenv("UPLOAD_RETRIES", "3"))
    retry_backoff_seconds: float = float(os.getenv("RETRY_BACKOFF_SECONDS", "3"))
    ftp_passive_mode: bool = os.getenv("FTP_PASSIVE_MODE", "true").lower() == "true"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def generate_sensor_reading(
    sensor_id: str,
    sampled_at: datetime | None = None,
    rng: random.Random | None = None,
) -> dict[str, str | float]:
    sampled_at = sampled_at or datetime.now(timezone.utc)
    rng = rng or random.Random()
    hour = sampled_at.hour + sampled_at.minute / 60
    daylight_wave = max(0, -1 * ((hour - 14) ** 2) / 36 + 1)

    temperature = clamp(rng.gauss(22 + daylight_wave * 13, 4), 15.0, 45.0)
    humidity = clamp(rng.gauss(76 - daylight_wave * 18, 12), 30.0, 95.0)
    wind_speed = clamp(rng.expovariate(1 / 12), 0.0, 50.0)
    pm25 = clamp(rng.lognormvariate(3.2, 0.55), 5.0, 150.0)

    return {
        "sensor_id": sensor_id,
        "timestamp": sampled_at.isoformat(),
        "temperature": round(temperature, 1),
        "humidity": round(humidity, 1),
        "wind_speed": round(wind_speed, 1),
        "pm25": round(pm25, 1),
    }


def build_csv_content(reading: dict[str, str | float]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerow(reading)
    return output.getvalue()


def build_local_filename(sensor_id: str, sampled_at: datetime) -> str:
    return f"{sensor_id}_{sampled_at.strftime('%Y%m%d_%H%M%S')}.csv"


def remote_sensor_dir(remote_base_dir: str, sensor_id: str) -> str:
    return f"{remote_base_dir.rstrip('/')}/{sensor_id}"


def write_local_csv(outbox_dir: Path, sensor_id: str, sampled_at: datetime, content: str) -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    path = outbox_dir / build_local_filename(sensor_id, sampled_at)
    path.write_text(content, encoding="utf-8")
    return path


def ensure_remote_dir(ftp: FTP, remote_dir: str) -> None:
    ftp.cwd("/")
    for segment in [part for part in remote_dir.split("/") if part]:
        try:
            ftp.mkd(segment)
        except Exception:
            pass
        ftp.cwd(segment)


def upload_file(settings: Settings, sensor_id: str, local_path: Path) -> None:
    remote_dir = remote_sensor_dir(settings.remote_base_dir, sensor_id)
    with FTP() as ftp:
        ftp.connect(settings.ftp_host, settings.ftp_port, timeout=15)
        ftp.login(settings.ftp_user, settings.ftp_password)
        ftp.set_pasv(settings.ftp_passive_mode)
        ensure_remote_dir(ftp, remote_dir)
        with local_path.open("rb") as file:
            ftp.storbinary(f"STOR {local_path.name}", file)


async def upload_with_retries(settings: Settings, sensor_id: str, local_path: Path) -> bool:
    for attempt in range(1, settings.upload_retries + 1):
        try:
            await asyncio.to_thread(upload_file, settings, sensor_id, local_path)
            return True
        except Exception as exc:
            logging.warning(
                "Upload failed sensor=%s file=%s attempt=%s/%s error=%s",
                sensor_id,
                local_path.name,
                attempt,
                settings.upload_retries,
                exc,
            )
            if attempt < settings.upload_retries:
                await asyncio.sleep(settings.retry_backoff_seconds)
    return False


async def run_sensor(sensor_id: str, settings: Settings) -> None:
    rng = random.Random(sensor_id)
    while True:
        sampled_at = datetime.now(timezone.utc).replace(microsecond=0)
        reading = generate_sensor_reading(sensor_id, sampled_at, rng)
        content = build_csv_content(reading)
        local_path = write_local_csv(settings.local_outbox_dir, sensor_id, sampled_at, content)

        uploaded = await upload_with_retries(settings, sensor_id, local_path)
        if uploaded:
            local_path.unlink(missing_ok=True)
            logging.info("Uploaded sensor=%s file=%s", sensor_id, local_path.name)

        await asyncio.sleep(settings.interval_seconds)


async def run_all_sensors(settings: Settings) -> None:
    sensor_ids = [f"sensor_{number:03d}" for number in range(1, settings.sensor_count + 1)]
    await asyncio.gather(*(run_sensor(sensor_id, settings) for sensor_id in sensor_ids))


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    configure_logging()
    settings = Settings()
    logging.info(
        "Starting IoT simulator sensors=%s interval=%ss ftp=%s:%s remote=%s",
        settings.sensor_count,
        settings.interval_seconds,
        settings.ftp_host,
        settings.ftp_port,
        settings.remote_base_dir,
    )
    asyncio.run(run_all_sensors(settings))


if __name__ == "__main__":
    main()
