# Worker Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep both ingestion worker entrypoints alive through transient database/FTP failures, retry bounded operations with exponential backoff, and let Compose restart unhealthy worker containers.

**Architecture:** Extract one small, injectable retry helper for transient operations so tests can control sleep and jitter. The mounted-volume worker retries its database-dependent assignment lookup and isolates each poll cycle; the FTP protocol poller retries each FTP/database operation and continues with other configurations. A process-level database healthcheck is added to the worker image, and every Compose worker receives the same healthcheck and restart policy.

**Tech Stack:** Python 3.12, psycopg 3, ftplib, pytest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-07-project-reliability-and-operations-design.md`

## Global Constraints

- A temporary FTP or database failure does not permanently stop an ingestion worker.
- Transient connection errors use bounded exponential backoff with jitter and the next poll cycle continues.
- The current per-cycle processing model and database idempotency remain unchanged.
- Existing historical sensor data must not be deleted or rewritten.
- Changes are delivered in independently testable phases; this plan covers Phase 1 only.
- No new runtime dependency is added; retain the pinned worker dependencies.

---

### Task 1: Add the retry primitive

**Files:**
- Create: `worker/app/retry.py`
- Test: `worker/tests/test_retry.py`

**Interfaces:**
- Produces `retry_call(operation: Callable[[], T], *, attempts: int, initial_delay: float, max_delay: float, sleep: Callable[[float], None], random_value: Callable[[], float]) -> T`.
- `attempts` counts total calls, not retries; the final exception is re-raised unchanged.
- Delay is bounded exponential backoff with non-negative jitter: for retry index `n`, the base is `min(max_delay, initial_delay * 2**n)` and the actual sleep is within `[base, base * 1.25]`.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.retry import retry_call


def test_retry_call_retries_until_success_with_bounded_backoff():
    attempts = []
    delays = []

    def operation():
        attempts.append(len(attempts) + 1)
        if len(attempts) < 3:
            raise OSError("temporary failure")
        return "ok"

    result = retry_call(
        operation,
        attempts=4,
        initial_delay=1.0,
        max_delay=3.0,
        sleep=delays.append,
        random_value=lambda: 1.0,
    )

    assert result == "ok"
    assert attempts == [1, 2, 3]
    assert delays == [1.25, 2.5]


def test_retry_call_reraises_the_last_error_after_total_attempt_limit():
    delays = []

    def operation():
        raise TimeoutError("database unavailable")

    with pytest.raises(TimeoutError, match="database unavailable"):
        retry_call(
            operation,
            attempts=3,
            initial_delay=2.0,
            max_delay=2.5,
            sleep=delays.append,
            random_value=lambda: 1.0,
        )

    assert delays == [2.5, 2.5]
```

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `cd worker && PYTHONPATH=. pytest tests/test_retry.py -q`

Expected: FAIL because `app.retry` does not exist yet.

- [ ] **Step 3: Implement the minimal retry helper**

Implement the loop in `worker/app/retry.py`: call the operation once, catch `Exception`, stop on the final allowed call, compute the capped base delay and multiply it by `1 + 0.25 * random_value()`, sleep, then retry. Do not catch `BaseException`, swallow the final exception, or add a dependency.

- [ ] **Step 4: Run the focused tests to verify GREEN**

Run: `cd worker && PYTHONPATH=. pytest tests/test_retry.py -q`

Expected: 2 passed.

- [ ] **Step 5: Commit the retry primitive**

```bash
git add worker/app/retry.py worker/tests/test_retry.py
git commit -m "feat: add bounded worker retry helper"
```

### Task 2: Make the mounted-volume worker survive database failures

**Files:**
- Modify: `worker/app/worker.py`
- Test: `worker/tests/test_worker.py`

**Interfaces:**
- Preserve `process_once() -> None` for existing callers and tests.
- Add `run_cycle() -> None` as the exception boundary used by `main()`.
- Add `run_forever(*, sleep: Callable[[float], None] = time.sleep) -> None` so the loop is testable without an infinite real sleep.

- [ ] **Step 1: Write the failing regression tests**

Add this regression test to `worker/tests/test_worker.py`:

```python
def test_run_cycle_survives_database_failure_and_processes_after_recovery(monkeypatch, tmp_path):
    incoming = tmp_path / "data"
    source = incoming / "sensor_001" / "reading.csv"
    source.parent.mkdir(parents=True)
    source.write_text("unused", encoding="utf-8")
    calls = []
    outcomes = [TimeoutError("database unavailable"), {"/data/sensor_001": "station-renamed"}]

    monkeypatch.setattr(worker, "FTP_INCOMING_DIR", incoming)
    monkeypatch.setattr(worker, "FTP_ARCHIVE_DIR", tmp_path / "archive")
    monkeypatch.setattr(worker, "FTP_ERROR_DIR", tmp_path / "error")
    monkeypatch.setattr(worker, "ARCHIVE_PROCESSED_FILES", False)
    monkeypatch.setattr(worker, "RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(worker, "fetch_folder_station_codes", lambda: _raise_or_return(outcomes))
    monkeypatch.setattr(worker, "parse_sensor_file", lambda path: [_reading("sensor_001")])
    monkeypatch.setattr(worker, "bulk_upsert_readings", lambda _url, readings: calls.append(readings) or 1)
    worker.PROCESSED_FILE_SIGNATURES.clear()

    worker.run_cycle()
    worker.run_cycle()

    assert len(calls) == 1
    assert calls[0][0].station_code == "station-renamed"


def _raise_or_return(outcomes):
    outcome = outcomes.pop(0)
    if isinstance(outcome, Exception):
        raise outcome
    return outcome
```

The first call must not raise; the second call must invoke the upsert exactly once.

- [ ] **Step 2: Run the focused test to verify RED**

Run: `cd worker && PYTHONPATH=. pytest tests/test_worker.py -q`

Expected: FAIL because `run_cycle()` is absent and the current main-cycle boundary does not expose recovery behavior.

- [ ] **Step 3: Implement the minimal cycle boundary and retry wiring**

Refactor `main()` to initialize directories once and delegate to `run_forever()`. Make `run_cycle()` invoke `process_once()` inside a logged exception boundary. Wrap the database-backed folder assignment lookup in `retry_call` with module-level settings `RETRY_ATTEMPTS`, `RETRY_INITIAL_DELAY_SECONDS`, and `RETRY_MAX_DELAY_SECONDS`, while keeping the existing defaults safe for local Compose. Keep parse/upsert failures isolated to their individual files and preserve archive/error-folder behavior. Do not retry parser errors or move an unassigned file.

- [ ] **Step 4: Run worker tests to verify GREEN**

Run: `cd worker && PYTHONPATH=. pytest tests/test_worker.py -q`

Expected: all worker tests pass, including the new recovery test.

- [ ] **Step 5: Commit the mounted-volume worker change**

```bash
git add worker/app/worker.py worker/tests/test_worker.py
git commit -m "fix: keep mounted FTP worker alive after database errors"
```

### Task 3: Add bounded retries and failure isolation to the FTP protocol poller

**Files:**
- Modify: `worker/app/ftp_poller.py`
- Test: `worker/tests/test_ftp_poller.py`

**Interfaces:**
- Preserve `main() -> None`, `process_once(processed_paths: set[str]) -> int`, and `_connect(config) -> FTP`.
- Use the Task 1 `retry_call` helper for connection, assignment lookup, file-index write, and remote download/database write operations.

- [ ] **Step 1: Write failing regression tests**

Add these two tests to `worker/tests/test_ftp_poller.py` (the fake FTP only needs `mlsd`, `retrbinary`, and context-manager methods):

```python
def test_process_once_retries_ftp_connection_until_file_is_processed(monkeypatch):
    attempts = []
    processed_paths = set()
    ftp = _FakeFtp(files=[{"path": "/data/sensor_001/reading.csv", "type": "file", "size": 1, "modified": None}])

    def connect(_config):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("FTP unavailable")
        return ftp

    monkeypatch.setattr(ftp_poller, "_fetch_station_ftp_configs", lambda: [{"station_id": 7, "host": "ftp", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1}])
    monkeypatch.setattr(ftp_poller, "_connect", connect)
    monkeypatch.setattr(ftp_poller, "_process_remote_file", lambda _ftp, _path: 1)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 2)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller.process_once(processed_paths) == 1
    assert len(attempts) == 2
    assert processed_paths == {"7:/data/sensor_001/reading.csv"}


def test_process_once_continues_to_next_ftp_config_after_exhausted_retries(monkeypatch):
    processed_paths = set()
    configs = [
        {"station_id": 1, "host": "bad", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1},
        {"station_id": 2, "host": "good", "port": 21, "user": "u", "password": "p", "root_path": "/data", "timeout_seconds": 1},
    ]
    good_ftp = _FakeFtp(files=[{"path": "/data/sensor_002/reading.csv", "type": "file", "size": 1, "modified": None}])

    monkeypatch.setattr(ftp_poller, "_fetch_station_ftp_configs", lambda: configs)
    monkeypatch.setattr(ftp_poller, "_connect", lambda config: (_ for _ in ()).throw(ConnectionError("bad")) if config["station_id"] == 1 else good_ftp)
    monkeypatch.setattr(ftp_poller, "_process_remote_file", lambda _ftp, _path: 1)
    monkeypatch.setattr(ftp_poller, "RETRY_ATTEMPTS", 1)
    monkeypatch.setattr(ftp_poller, "RETRY_SLEEP", lambda _seconds: None)

    assert ftp_poller.process_once(processed_paths) == 1
    assert processed_paths == {"2:/data/sensor_002/reading.csv"}
```

Define `_FakeFtp` in the test file with `__enter__`, `__exit__`, and `mlsd` returning its `files`; the existing tests continue to cover path filtering.

- [ ] **Step 2: Run the focused tests to verify RED**

Run: `cd worker && PYTHONPATH=. pytest tests/test_ftp_poller.py -q`

Expected: FAIL because connection failures are currently swallowed without retry and the retry behavior is not present.

- [ ] **Step 3: Implement minimal FTP poller retries**

Wrap each configured FTP connection in the retry helper. Keep configuration failures isolated: after the bounded attempts, log the station/server context and continue to the next config. Retry transient remote retrieval and database index/upsert operations at their existing operation boundary, but leave parse/unsupported-file handling unchanged. Ensure a file is added to `processed_paths` only after successful persistence, so recovery can process it on the next attempt.

- [ ] **Step 4: Run all worker tests to verify GREEN**

Run: `cd worker && PYTHONPATH=. pytest -q`

Expected: all worker tests pass with no warnings or unhandled exceptions.

- [ ] **Step 5: Commit the protocol poller change**

```bash
git add worker/app/ftp_poller.py worker/tests/test_ftp_poller.py
git commit -m "fix: retry transient FTP poller failures"
```

### Task 4: Add a worker database healthcheck

**Files:**
- Create: `worker/app/healthcheck.py`
- Modify: `worker/Dockerfile`
- Test: `worker/tests/test_healthcheck.py`

**Interfaces:**
- Add `check_database(database_url: str, connect: Callable = psycopg.connect) -> None`; it succeeds when a connection can be opened and executes `SELECT 1`, and raises on failure.
- Running `python -m app.healthcheck` reads `DATABASE_URL` and exits `0` on success or `1` on failure without printing the password.

- [ ] **Step 1: Write failing unit tests**

Add these tests to `worker/tests/test_healthcheck.py`:

```python
def test_check_database_executes_select_one():
    connection = _FakeConnection()

    healthcheck.check_database("postgresql://monitor:secret@db/environment", connect=lambda _url, **_kwargs: connection)

    assert connection.cursor_obj.statements == ["SELECT 1"]


def test_main_returns_failure_without_leaking_database_url(monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://monitor:secret@db/environment")
    monkeypatch.setattr(healthcheck.psycopg, "connect", lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("secret")))

    assert healthcheck.main() == 1
    output = capsys.readouterr().out
    assert "Worker database healthcheck failed" in output
    assert "secret" not in output
    assert "postgresql://" not in output
```

`_FakeConnection` and its cursor implement context managers; the cursor's `execute` appends its SQL to `statements`.

- [ ] **Step 2: Run focused tests to verify RED**

Run: `cd worker && PYTHONPATH=. pytest tests/test_healthcheck.py -q`

Expected: FAIL because the healthcheck module does not exist.

- [ ] **Step 3: Implement the healthcheck and image entrypoint support**

Use psycopg's context managers, execute exactly `SELECT 1`, and configure a short `connect_timeout` only when the URL does not already provide one. Copy `healthcheck.py` through the existing Dockerfile `COPY app ./app`; no new package is required. Keep normal worker startup as the image `CMD`.

- [ ] **Step 4: Run focused and full worker tests**

Run: `cd worker && PYTHONPATH=. pytest -q`

Expected: all worker tests pass.

- [ ] **Step 5: Commit the healthcheck**

```bash
git add worker/app/healthcheck.py worker/tests/test_healthcheck.py worker/Dockerfile
git commit -m "feat: add worker database healthcheck"
```

### Task 5: Configure Compose restart and health policies

**Files:**
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Test: `worker/tests/test_compose_config.py`

**Interfaces:**
- Every `ftp-worker*` service has `restart: unless-stopped` and a healthcheck running `python -m app.healthcheck`.
- Healthcheck settings are explicit: `interval: 30s`, `timeout: 5s`, `retries: 3`, `start_period: 10s`.
- Retry settings are configurable through environment variables and default to bounded values suitable for local development.

- [ ] **Step 1: Write the failing Compose configuration test**

Add this dependency-free text test to `worker/tests/test_compose_config.py`:

```python
from pathlib import Path


def test_all_ftp_workers_have_restart_healthcheck_and_retry_settings():
    compose = (Path(__file__).parents[2] / "docker-compose.yml").read_text(encoding="utf-8")

    for service in ("ftp-worker:", "ftp-worker-2:", "ftp-worker-3:", "ftp-worker-4:", "ftp-worker-5:"):
        block = compose.split(f"  {service}", 1)[1].split("\n  ", 1)[0]
        assert "restart: unless-stopped" in block
        assert "python -m app.healthcheck" in block
        assert "interval: 30s" in block
        assert "timeout: 5s" in block
        assert "retries: 3" in block
        assert "start_period: 10s" in block
        assert "RETRY_ATTEMPTS" in block
        assert "RETRY_INITIAL_DELAY_SECONDS" in block
        assert "RETRY_MAX_DELAY_SECONDS" in block
```

- [ ] **Step 2: Run the focused test to verify RED**

Run: `cd worker && PYTHONPATH=. pytest tests/test_compose_config.py -q`

Expected: FAIL because the worker service blocks have no restart/healthcheck/retry environment entries.

- [ ] **Step 3: Add the shared worker policy to Compose and document operations**

Add the same healthcheck and `restart: unless-stopped` to `ftp-worker`, `ftp-worker-2`, `ftp-worker-3`, `ftp-worker-4`, and `ftp-worker-5`. Add bounded retry environment values to each worker. Document `docker compose ps`, `docker compose logs -f ftp-worker`, and the meaning of an unhealthy worker in the worker operations section of `README.md`.

- [ ] **Step 4: Run configuration and worker verification**

Run: `cd worker && PYTHONPATH=. pytest -q`

Run: `docker compose config`

Expected: all worker tests pass and Compose renders successfully with five healthy-policy worker services.

- [ ] **Step 5: Commit the deployment policy**

```bash
git add docker-compose.yml README.md worker/tests/test_compose_config.py
git commit -m "ops: add worker healthcheck and restart policy"
```

### Task 6: Phase 1 verification and deployment check

**Files:**
- No additional files.

- [ ] **Step 1: Run the complete worker test suite**

Run: `cd worker && PYTHONPATH=. pytest -q`

Expected: all tests pass.

- [ ] **Step 2: Build the worker image**

Run: `docker compose build ftp-worker ftp-worker-2 ftp-worker-3 ftp-worker-4 ftp-worker-5`

Expected: all five worker images build successfully.

- [ ] **Step 3: Recreate only the worker services**

Run: `docker compose up -d --no-deps --force-recreate ftp-worker ftp-worker-2 ftp-worker-3 ftp-worker-4 ftp-worker-5`

Expected: containers start without changing or deleting the database volume.

- [ ] **Step 4: Verify live health and logs**

Run: `docker compose ps ftp-worker ftp-worker-2 ftp-worker-3 ftp-worker-4 ftp-worker-5`

Run: `docker compose logs --tail=80 ftp-worker`

Expected: each worker reports `Up` with a healthy status after startup, logs show the worker started, and no credential values appear.

- [ ] **Step 5: Review the complete diff and record acceptance evidence**

Run: `git diff HEAD~5..HEAD --stat` and `git log --oneline -6`.

Confirm the diff is limited to Phase 1 worker reliability, all focused tests were observed failing before implementation, all final verification commands passed, and no database schema/history was changed.
