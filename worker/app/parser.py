from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SensorReading:
    station_code: str
    time: datetime
    temperature: float | None
    humidity: float | None
    pm25: float | None


def parse_sensor_file(path: Path) -> list[SensorReading]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _parse_csv(path)
    if suffix == ".json":
        return _parse_json(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _parse_csv(path: Path) -> list[SensorReading]:
    with path.open("r", encoding="utf-8", newline="") as file:
        return [_reading_from_dict(row) for row in csv.DictReader(file)]


def _parse_json(path: Path) -> list[SensorReading]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else [payload]
    return [_reading_from_dict(row) for row in rows]


def _reading_from_dict(row: dict[str, Any]) -> SensorReading:
    return SensorReading(
        station_code=str(row["station_code"]).strip(),
        time=_parse_time(str(row["time"])),
        temperature=_optional_float(row.get("temperature")),
        humidity=_optional_float(row.get("humidity")),
        pm25=_optional_float(row.get("pm25")),
    )


def _parse_time(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)

