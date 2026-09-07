import asyncio
from datetime import datetime, timezone
from typing import Annotated

import asyncpg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import database
from app.ftp_browser import FtpConnectionSettings, check_ftp_status, list_ftp_directory, normalize_ftp_path, read_ftp_csv_file
from app.repository import (
    MAX_INTERACTIVE_POINTS_DEFAULT,
    authenticate_user,
    create_station,
    delete_station,
    ensure_runtime_schema,
    fetch_analytics_heatmap,
    fetch_analytics_scatter,
    fetch_analytics_series,
    fetch_live_stations,
    fetch_overview,
    fetch_station_data,
    fetch_station_ftp_config,
    fetch_ftp_file_index,
    fetch_stations_for_user,
    fetch_user_context,
    update_station,
)
from app.schemas import (
    AnalyticsScatterResponse,
    AnalyticsSeriesResponse,
    HeatmapPoint,
    LiveStation,
    LoginRequest,
    LoginResponse,
    Overview,
    FtpFilePreview,
    FtpListing,
    FtpStatus,
    Station,
    StationCreate,
    StationDataResponse,
    StationUpdate,
    FtpConnectionRequest,
)


app = FastAPI(title="Environment Monitoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await database.connect()
    async with database.acquire() as connection:
        await ensure_runtime_schema(connection)


@app.on_event("shutdown")
async def shutdown() -> None:
    await database.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def current_user(x_user_id: int = Header(1, alias="X-User-Id")) -> dict:
    async with database.acquire() as connection:
        context = await fetch_user_context(connection, x_user_id)
    return {"id": x_user_id, **context}


def parse_id_list(value: str) -> list[int]:
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="IDs must be comma-separated integers") from exc


@app.get("/api/stations", response_model=list[Station])
async def list_stations(user: dict = Depends(current_user)) -> list[dict]:
    async with database.acquire() as connection:
        return await fetch_stations_for_user(connection, user)


@app.post("/api/stations", response_model=Station, status_code=201)
async def add_station(payload: StationCreate, user: dict = Depends(current_user)) -> dict:
    async with database.acquire() as connection:
        try:
            async with connection.transaction():
                return await create_station(connection, payload.model_dump(), user, settings.ftp_credentials_key)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="Station code already exists") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/stations/{station_id}", response_model=Station)
async def edit_station(station_id: int, payload: StationUpdate, user: dict = Depends(current_user)) -> dict:
    async with database.acquire() as connection:
        try:
            async with connection.transaction():
                station = await update_station(connection, station_id, payload.model_dump(exclude_unset=True), user, settings.ftp_credentials_key)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except asyncpg.UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="Station code already exists") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    if station is None:
        raise HTTPException(status_code=404, detail="Station not found")
    return station


@app.delete("/api/stations/{station_id}", status_code=204)
async def remove_station(station_id: int, user: dict = Depends(current_user)) -> Response:
    async with database.acquire() as connection:
        try:
            deleted = await delete_station(connection, station_id, user)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Station not found")
    return Response(status_code=204)


@app.get("/api/stations/live", response_model=list[LiveStation])
async def live_stations(user: dict = Depends(current_user)) -> list[dict]:
    async with database.acquire() as connection:
        return await fetch_live_stations(connection, user)


@app.get("/api/overview", response_model=Overview)
async def overview(user: dict = Depends(current_user)) -> dict:
    async with database.acquire() as connection:
        return await fetch_overview(connection, user)


@app.get("/api/analytics/series", response_model=AnalyticsSeriesResponse)
async def analytics_series(
    station_ids: Annotated[str, Query()],
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    metric: str = Query("pm25"),
    resolution: str = Query("1h", pattern="^(1m|1h|1d)$"),
    max_points: int = Query(MAX_INTERACTIVE_POINTS_DEFAULT),
    user: dict = Depends(current_user),
) -> dict:
    async with database.acquire() as connection:
        try:
            return await fetch_analytics_series(
                connection,
                parse_id_list(station_ids),
                metric,
                start_time,
                end_time,
                resolution,
                user,
                max_points,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/heatmap", response_model=list[HeatmapPoint])
async def analytics_heatmap(
    station_id: int,
    metric: str = Query("pm25"),
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    user: dict = Depends(current_user),
) -> list[dict]:
    async with database.acquire() as connection:
        try:
            return await fetch_analytics_heatmap(connection, station_id, metric, start_time, end_time, user)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/analytics/scatter", response_model=AnalyticsScatterResponse)
async def analytics_scatter(
    station_id: int,
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    x_metric: str = Query("temperature"),
    y_metric: str = Query("pm25"),
    resolution: str = Query("1h", pattern="^(1m|1h|1d)$"),
    max_points: int = Query(MAX_INTERACTIVE_POINTS_DEFAULT),
    user: dict = Depends(current_user),
) -> dict:
    async with database.acquire() as connection:
        try:
            return await fetch_analytics_scatter(
                connection,
                station_id,
                x_metric,
                y_metric,
                start_time,
                end_time,
                resolution,
                user,
                max_points,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


def ftp_settings() -> FtpConnectionSettings:
    return FtpConnectionSettings(
        host=settings.ftp_host,
        port=settings.ftp_port,
        user=settings.ftp_user,
        password=settings.ftp_password,
        timeout_seconds=settings.ftp_timeout_seconds,
    )


async def station_ftp_settings(station_id: int, connection) -> FtpConnectionSettings:
    config = await fetch_station_ftp_config(connection, station_id, settings.ftp_credentials_key)
    if config is None:
        raise HTTPException(status_code=404, detail="FTP configuration is not set for this station")
    return FtpConnectionSettings(**config)


@app.post("/api/ftp/test", response_model=FtpStatus)
async def test_ftp_connection(payload: FtpConnectionRequest, user: dict = Depends(current_user)) -> dict:
    try:
        ftp_config = payload.model_dump()
        ftp_config["root_path"] = normalize_ftp_path(payload.root_path)
        result = await asyncio.to_thread(check_ftp_status, FtpConnectionSettings(**ftp_config))
        result["root_path"] = ftp_config["root_path"]
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        ftp_config = payload.model_dump()
        return {
            "connected": False,
            "host": payload.host,
            "port": payload.port,
            "user": payload.user,
            "root_path": ftp_config.get("root_path", payload.root_path),
            "error": str(exc),
        }


@app.get("/api/ftp/status", response_model=FtpStatus)
async def ftp_status(station_id: int | None = Query(None), user: dict = Depends(current_user)) -> dict:
    connection_settings = ftp_settings()
    root_path = "/data"
    if station_id is not None:
        async with database.acquire() as connection:
            connection_settings = await station_ftp_settings(station_id, connection)
        root_path = connection_settings.root_path if hasattr(connection_settings, "root_path") else root_path
    try:
        result = await asyncio.to_thread(check_ftp_status, connection_settings)
        result["root_path"] = root_path
        return result
    except Exception as exc:
        return {
            "connected": False,
            "host": connection_settings.host,
            "port": connection_settings.port,
            "user": connection_settings.user,
            "root_path": root_path,
            "error": str(exc),
        }


@app.get("/api/ftp/files", response_model=FtpListing)
async def ftp_files(path: str | None = Query(None), station_id: int | None = Query(None), user: dict = Depends(current_user)) -> dict:
    connection_settings = ftp_settings()
    if station_id is not None:
        async with database.acquire() as connection:
            connection_settings = await station_ftp_settings(station_id, connection)
    path = path or (getattr(connection_settings, "root_path", "/data"))
    try:
        return await asyncio.to_thread(list_ftp_directory, connection_settings, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot browse FTP directory: {exc}") from exc


@app.get("/api/ftp/index", response_model=FtpListing)
async def ftp_file_index(station_id: int = Query(...), user: dict = Depends(current_user)) -> dict:
    async with database.acquire() as connection:
        try:
            entries = await fetch_ftp_file_index(connection, station_id, user)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return {"path": "/data", "entries": entries}


@app.get("/api/ftp/file", response_model=FtpFilePreview)
async def ftp_file(path: str = Query(...), station_id: int | None = Query(None), user: dict = Depends(current_user)) -> dict:
    connection_settings = ftp_settings()
    if station_id is not None:
        async with database.acquire() as connection:
            connection_settings = await station_ftp_settings(station_id, connection)
    try:
        return await asyncio.to_thread(read_ftp_csv_file, connection_settings, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Cannot read FTP file: {exc}") from exc


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> dict:
    async with database.acquire() as connection:
        user = await authenticate_user(connection, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return user


@app.get("/api/stations/{station_id}/data", response_model=StationDataResponse)
async def station_data(
    station_id: int,
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    resolution: str = Query("1m", pattern="^(1m|1h|1d)$"),
    max_points: int = Query(MAX_INTERACTIVE_POINTS_DEFAULT),
    user: dict = Depends(current_user),
) -> dict:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    async with database.acquire() as connection:
        try:
            return await fetch_station_data(connection, station_id, start_time, end_time, resolution, user, max_points)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket, user_id: int = 1) -> None:
    await websocket.accept()
    user = {"id": user_id}
    try:
        async with database.acquire() as connection:
            user.update(await fetch_user_context(connection, user_id))
        while True:
            async with database.acquire() as connection:
                payload = await fetch_live_stations(connection, user)
            await websocket.send_json({"type": "stations.live", "stations": payload})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
