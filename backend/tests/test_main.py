import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import app.main as main
from app.schemas import QcvnConfigCreate, QcvnConfigUpdate


class FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeDatabase:
    def acquire(self):
        return FakeAcquire()


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeQcvnConnection:
    def transaction(self):
        return FakeTransaction()


class FakeQcvnAcquire:
    async def __aenter__(self):
        return FakeQcvnConnection()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeQcvnDatabase:
    def acquire(self):
        return FakeQcvnAcquire()


@pytest.mark.parametrize(
    ("route_name", "fetch_name", "kwargs"),
    [
        (
            "analytics_series",
            "fetch_analytics_series",
            {"station_ids": "999", "resolution": "1h", "max_points": 1000},
        ),
        (
            "analytics_heatmap",
            "fetch_analytics_heatmap",
            {"station_id": 999},
        ),
        (
            "analytics_scatter",
            "fetch_analytics_scatter",
            {"station_id": 999, "resolution": "1h", "max_points": 1000},
        ),
    ],
)
def test_analytics_routes_return_404_for_missing_station(monkeypatch, route_name, fetch_name, kwargs):
    start_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    common_kwargs = {
        "start_time": start_time,
        "end_time": start_time + timedelta(hours=1),
        "user": {"roles": ["super_admin"], "region_ids": []},
    }

    async def missing_station_fetch(*args, **kwargs):
        raise LookupError("Station not found")

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, fetch_name, missing_station_fetch)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(getattr(main, route_name)(**common_kwargs, **kwargs))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Station not found"


def test_add_qcvn_config_route_delegates_station_threshold_payload(monkeypatch):
    payload = QcvnConfigCreate(station_ids=[7, 8], metric="pm25", warning_max=35, critical_max=150)
    expected = {"id": 1, "station_ids": [7, 8], "metric": "pm25", "warning_max": 35, "critical_max": 150}
    captured = {}

    async def fake_create(connection, data, user):
        captured.update(data)
        return expected

    monkeypatch.setattr(main, "database", FakeQcvnDatabase())
    monkeypatch.setattr(main, "create_qcvn_config", fake_create)

    result = asyncio.run(main.add_qcvn_config(payload, {"id": 1, "roles": ["super_admin"], "region_ids": []}))

    assert result == expected
    assert captured["station_ids"] == [7, 8]
    assert captured["warning_max"] == 35.0


def test_edit_qcvn_config_route_returns_not_found(monkeypatch):
    payload = QcvnConfigUpdate(station_ids=[7], metric="pm25", warning_max=35, critical_max=150)

    async def missing_update(*args):
        return None

    monkeypatch.setattr(main, "database", FakeQcvnDatabase())
    monkeypatch.setattr(main, "update_qcvn_config", missing_update)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.edit_qcvn_config(999, payload, {"id": 1, "roles": ["super_admin"], "region_ids": []}))

    assert exc_info.value.status_code == 404
