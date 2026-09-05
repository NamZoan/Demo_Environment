from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Station(BaseModel):
    id: int
    code: str
    name: str
    latitude: float | None
    longitude: float | None
    address: str | None
    status: str
    metadata: dict[str, Any]


class SensorPoint(BaseModel):
    time: datetime
    temperature: float | None
    humidity: float | None
    pm25: float | None
    samples: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str
