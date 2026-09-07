import asyncio

import app.main as main
from app.schemas import FtpConnectionRequest


class FakeAcquire:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, traceback):
        return False


def test_ftp_connection_endpoint_returns_success_without_exposing_password(monkeypatch):
    def fake_check(settings):
        assert settings.password == "secret"
        return {"connected": True, "host": settings.host, "port": settings.port, "user": settings.user, "root_path": "/data", "message": "220 ready"}

    monkeypatch.setattr(main, "check_ftp_status", fake_check)
    result = asyncio.run(
        main.test_ftp_connection(
            FtpConnectionRequest(host="ftp.example", port=2121, user="station", password="secret", root_path="/data/env-001"),
            user={"id": 1},
        )
    )

    assert result["connected"] is True
    assert result["root_path"] == "/data/env-001"
    assert "password" not in result


def test_ftp_connection_endpoint_reports_connection_error(monkeypatch):
    def fake_check(settings):
        raise TimeoutError("timed out")

    monkeypatch.setattr(main, "check_ftp_status", fake_check)
    result = asyncio.run(
        main.test_ftp_connection(
            FtpConnectionRequest(host="ftp.example", user="station", password="secret"),
            user={"id": 1},
        )
    )

    assert result["connected"] is False
    assert result["error"] == "timed out"
    assert "password" not in result


def test_ftp_connection_endpoint_rejects_path_outside_data():
    try:
        asyncio.run(
            main.test_ftp_connection(
                FtpConnectionRequest(host="ftp.example", user="station", password="secret", root_path="/etc"),
                user={"id": 1},
            )
        )
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400
        assert "FTP path must stay under /data" in str(exc.detail)
    else:
        raise AssertionError("Expected an HTTP 400 error")


def test_ftp_directory_endpoint_uses_catalog_configuration(monkeypatch):
    expected_settings = {
        "host": "ftp.example",
        "port": 2121,
        "user": "station",
        "password": "secret",
        "root_path": "/data",
        "timeout_seconds": 5,
    }

    async def fake_fetch(connection, ftp_id, user, encryption_key):
        assert ftp_id == 7
        assert user["id"] == 1
        return expected_settings

    def fake_list(settings, path):
        assert settings.host == expected_settings["host"]
        assert settings.port == expected_settings["port"]
        assert settings.password == expected_settings["password"]
        assert path == "/data"
        return {"path": "/data", "entries": []}

    monkeypatch.setattr(main, "database", type("Database", (), {"acquire": lambda self: FakeAcquire()})())
    monkeypatch.setattr(main, "fetch_ftp_connection_settings", fake_fetch)
    monkeypatch.setattr(main, "list_ftp_directory", fake_list)

    result = asyncio.run(main.ftp_files(path="/data", ftp_id=7, user={"id": 1}))

    assert result == {"path": "/data", "entries": []}
