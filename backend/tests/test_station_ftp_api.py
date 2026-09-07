import asyncio

import app.main as main
from app.schemas import FtpConnectionRequest


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
