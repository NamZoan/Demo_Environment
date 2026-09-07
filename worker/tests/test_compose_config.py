import re
from pathlib import Path


def test_all_ftp_workers_have_restart_healthcheck_and_retry_settings():
    compose = (Path(__file__).parents[2] / "docker-compose.yml").read_text(encoding="utf-8")

    for service in ("ftp-worker:", "ftp-worker-2:", "ftp-worker-3:", "ftp-worker-4:", "ftp-worker-5:"):
        block = re.split(r"\n  (?=\S)", compose.split(f"  {service}", 1)[1], maxsplit=1)[0]
        assert "restart: unless-stopped" in block
        assert "python -m app.healthcheck" in block
        assert "interval: 30s" in block
        assert "timeout: 5s" in block
        assert "retries: 3" in block
        assert "start_period: 10s" in block
        assert "RETRY_ATTEMPTS" in block
        assert "RETRY_INITIAL_DELAY_SECONDS" in block
        assert "RETRY_MAX_DELAY_SECONDS" in block
