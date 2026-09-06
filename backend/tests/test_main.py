import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import app.main as main


class FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeDatabase:
    def acquire(self):
        return FakeAcquire()


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
