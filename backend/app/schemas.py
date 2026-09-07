from datetime import datetime
from typing import Any, Literal

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
    ftp_config: dict[str, Any] | None = None


class FtpConnectionRequest(BaseModel):
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=21, ge=1, le=65535)
    user: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=4096)
    root_path: str = "/data"
    timeout_seconds: int = Field(default=5, ge=1, le=120)


class FtpConfigInput(FtpConnectionRequest):
    pass


class FtpConfigCreate(FtpConnectionRequest):
    name: str = Field(min_length=1, max_length=255)
    station_ids: list[int] = Field(default_factory=list)


class FtpConfigUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=21, ge=1, le=65535)
    user: str = Field(min_length=1, max_length=255)
    password: str | None = Field(default=None, max_length=4096)
    root_path: str = "/data"
    timeout_seconds: int = Field(default=5, ge=1, le=120)
    station_ids: list[int] = Field(default_factory=list)


class StationCreate(BaseModel):
    code: str
    name: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = None
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
    region_id: int | None = None
    ftp_config: FtpConfigInput | None = None


class StationUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = None
    status: str | None = None
    metadata: dict[str, Any] | None = None
    region_id: int | None = None
    ftp_config: FtpConfigInput | None = None


class LiveStation(Station):
    time: datetime | None = None
    temperature: float | None = None
    humidity: float | None = None
    wind_speed: float | None = None
    pm25: float | None = None
    qcvn_thresholds: dict[str, dict[str, float | None]] = Field(default_factory=dict)
    live_status: str


class QcvnConfigCreate(BaseModel):
    station_id: int = Field(gt=0)
    metric: Literal["pm25", "temperature", "humidity"]
    warning_min: float | None = None
    warning_max: float | None = None
    critical_min: float | None = None
    critical_max: float | None = None
    enabled: bool = True


class QcvnConfigUpdate(QcvnConfigCreate):
    pass


class QcvnConfigResponse(QcvnConfigCreate):
    id: int
    station_code: str
    station_name: str
    created_at: datetime
    updated_at: datetime


class SensorPoint(BaseModel):
    time: datetime
    temperature: float | None
    humidity: float | None
    wind_speed: float | None = None
    pm25: float | None
    samples: int | None = None
    valid_hours: int | None = None


class AnalyticsPoint(BaseModel):
    station_id: int
    time: datetime
    value: float | None
    station_code: str | None = None
    station_name: str | None = None
    metric: str | None = None
    aqi_level: str | None = None


class ScatterPoint(BaseModel):
    time: datetime | None = None
    station_id: int | None = None
    x: float | None
    y: float | None


class HeatmapPoint(BaseModel):
    day: str
    hour: int
    value: float | None
    level: str | None = None


class QueryMeta(BaseModel):
    requested_resolution: str
    effective_resolution: str
    max_points: int
    returned_points: int
    downsampled: bool
    resolution_note: str | None = None


class StationDataResponse(BaseModel):
    meta: QueryMeta
    points: list[SensorPoint]


class AnalyticsSeriesResponse(BaseModel):
    meta: QueryMeta
    points: list[AnalyticsPoint]


class AnalyticsScatterResponse(BaseModel):
    meta: QueryMeta
    points: list[ScatterPoint]


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


RBACRole = Literal["super_admin", "manager", "viewer"]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=4096)
    full_name: str = Field(default="", max_length=255)
    role: RBACRole = "viewer"
    region_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    password: str | None = Field(default=None, min_length=8, max_length=4096)
    full_name: str = Field(default="", max_length=255)
    role: RBACRole = "viewer"
    status: Literal["active", "inactive"] = "active"
    region_ids: list[int] = Field(default_factory=list)


class UserAdminResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    role: str
    roles: list[str] = Field(default_factory=list)
    status: str
    region_ids: list[int] = Field(default_factory=list)


class RbacRoleResponse(BaseModel):
    code: str
    name: str
    description: str | None = None


class RegionResponse(BaseModel):
    id: int
    code: str
    name: str


class RbacOptionsResponse(BaseModel):
    roles: list[RbacRoleResponse]
    regions: list[RegionResponse]


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


class FtpConfigResponse(BaseModel):
    id: int
    name: str
    station_id: int | None = None
    station_ids: list[int] = Field(default_factory=list)
    stations: list[dict[str, Any]] = Field(default_factory=list)
    host: str
    port: int
    user: str
    root_path: str
    timeout_seconds: int
    connected: bool | None = None
    last_checked_at: datetime | None = None


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
