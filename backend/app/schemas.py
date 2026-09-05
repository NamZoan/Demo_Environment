from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Station(BaseModel):
    id: int
    code: str
    name: str
    latitude: float | None
    longitude: float | None
    address: str | None
    status: str
    metadata: dict[str, Any]
    region_id: int | None = None
    last_seen_at: datetime | None = None


class StationCreate(BaseModel):
    code: str
    name: str
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    region_id: int | None = None


class StationUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None
    region_id: int | None = None


class LiveStation(Station):
    time: datetime | None = None
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    pm25: float | None = None
    live_status: str


class SensorPoint(BaseModel):
    time: datetime
    temperature: float | None
    humidity: float | None
    wind_speed: float | None = None
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
    roles: list[str] = Field(default_factory=list)
    region_ids: list[int] = Field(default_factory=list)


class Overview(BaseModel):
    total: int
    online: int
    warning: int
    critical: int
    offline: int


class FtpStatus(BaseModel):
    connected: bool
    host: str
    port: int
    user: str
    root_path: str
    message: str | None = None
    error: str | None = None


class FtpEntry(BaseModel):
    name: str
    path: str
    type: str
    size: int | None = None
    modified: str | None = None


class FtpListing(BaseModel):
    path: str
    entries: list[FtpEntry] = Field(default_factory=list)


class FtpFilePreview(BaseModel):
    path: str
    name: str
    content: str
    size: int
