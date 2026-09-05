from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import database
from app.repository import fetch_station_data, fetch_stations
from app.schemas import SensorPoint, Station


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


@app.on_event("shutdown")
async def shutdown() -> None:
    await database.close()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stations", response_model=list[Station])
async def list_stations() -> list[dict]:
    async with database.acquire() as connection:
        return await fetch_stations(connection)


@app.get("/api/stations/{station_id}/data", response_model=list[SensorPoint])
async def station_data(
    station_id: int,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    resolution: str = Query("1m", pattern="^(1m|1h|1d)$"),
) -> list[dict]:
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)
    if start_time > end_time:
        raise HTTPException(status_code=400, detail="start_time must be before end_time")

    async with database.acquire() as connection:
        return await fetch_station_data(connection, station_id, start_time, end_time, resolution)

