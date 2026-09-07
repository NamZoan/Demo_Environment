import asyncio

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


def test_ftp_file_index_returns_404_for_missing_station(monkeypatch):
    async def missing_station(*args):
        raise LookupError("Station not found")

    monkeypatch.setattr(main, "database", FakeDatabase())
    monkeypatch.setattr(main, "fetch_ftp_file_index", missing_station)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(main.ftp_file_index(999, {"roles": ["super_admin"], "region_ids": []}))

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Station not found"
