# Time-Series Query Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Protect interactive station and analytics charts from oversized time-series payloads by enforcing resolution guardrails, using Timescale continuous aggregates, and returning response metadata to the frontend.

**Architecture:** Add a small backend policy layer that validates interactive query ranges, upgrades requested resolution when the selected range is too long, and computes deterministic downsampling buckets. Repository functions return `{meta, points}` envelopes while preserving export endpoints, and frontend API helpers normalize the new envelope before station and analytics views render status notes.

**Tech Stack:** FastAPI, Pydantic, asyncpg, TimescaleDB continuous aggregates, pytest, React, Vite, Recharts, Node assert tests.

**Spec:** `docs/superpowers/specs/2026-09-06-time-series-query-guardrails-design.md`

## Global Constraints

- Interactive endpoints covered: `GET /api/stations/{station_id}/data`, `GET /api/analytics/series`, `GET /api/analytics/scatter`.
- Export endpoints are not downsampled and keep existing export-specific validation.
- Accepted `resolution` values stay exactly `1m`, `1h`, `1d`.
- Default `max_points` is `1000`.
- Valid `max_points` range is `100..5000`.
- `1m` is allowed only up to `48 hours`.
- `1h` is allowed only up to `90 days`.
- Requests longer than `90 days` use `1d`.
- Interactive requests longer than `5 years` return `400`.
- Station hourly and daily reads must use `sensor_data_hourly` and `sensor_data_daily`; they must not aggregate raw `sensor_data` at request time.
- Every changed interactive response returns an envelope with `meta` and `points`.
- `meta` fields are `requested_resolution`, `effective_resolution`, `max_points`, `returned_points`, `downsampled`, and `resolution_note`.

---

## File Structure

- `backend/app/repository.py`: Owns query policy helpers, Timescale source selection, downsampling SQL construction, and envelope-returning repository functions.
- `backend/app/schemas.py`: Defines shared Pydantic response models for query metadata and station/analytics envelopes.
- `backend/app/main.py`: Validates query parameters, passes `max_points`, converts repository errors to `400`, and declares envelope response models.
- `backend/tests/test_repository.py`: Unit tests policy selection, source SQL, validation, response envelopes, and downsampling query behavior with fake async connections.
- `frontend/src/api.js`: Adds `maxPoints` query parameters and normalizes envelope responses while tolerating old bare-array payloads in tests/dev.
- `frontend/src/features/stations/stationTimeRange.js`: Adds frontend preferred resolution and meta-note helpers.
- `frontend/src/features/stations/stationTimeRange.test.mjs`: Tests preferred resolution, envelope normalization expectations, and optimization note copy helpers.
- `frontend/src/features/stations/StationParameters.jsx`: Reads `{meta, points}`, formats rows with effective resolution labels, and renders the backend optimization note.
- `frontend/src/features/analytics/AnalyticsReports.jsx`: Reads analytics envelopes and renders one compact optimization note for series/scatter.

---

### Task 1: Backend Query Policy Helpers

**Files:**
- Modify: `backend/app/repository.py`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Produces: `MAX_INTERACTIVE_POINTS_DEFAULT = 1000`
- Produces: `MAX_INTERACTIVE_RANGE = timedelta(days=365 * 5)`
- Produces: `RESOLUTION_DURATIONS = {"1m": timedelta(minutes=1), "1h": timedelta(hours=1), "1d": timedelta(days=1)}`
- Produces: `choose_effective_resolution(requested_resolution: str, start_time: datetime, end_time: datetime) -> tuple[str, str | None]`
- Produces: `validate_interactive_query_range(start_time: datetime, end_time: datetime, max_points: int) -> None`
- Produces: `query_meta(requested_resolution: str, effective_resolution: str, max_points: int, returned_points: int, downsampled: bool, resolution_note: str | None) -> dict`

- [ ] **Step 1: Write failing policy tests**

Add these tests near the existing resolution tests in `backend/tests/test_repository.py`:

```python
from app.repository import (
    MAX_INTERACTIVE_POINTS_DEFAULT,
    choose_effective_resolution,
    query_meta,
    validate_interactive_query_range,
)


def test_choose_effective_resolution_keeps_one_minute_for_24_hours():
    start = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)

    effective, note = choose_effective_resolution("1m", start, end)

    assert effective == "1m"
    assert note is None


def test_choose_effective_resolution_upgrades_one_minute_after_48_hours():
    start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=7)

    effective, note = choose_effective_resolution("1m", start, end)

    assert effective == "1h"
    assert note == "Switched from 1m to 1h because the selected range is longer than 48 hours."


def test_choose_effective_resolution_upgrades_one_hour_after_90_days():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=120)

    effective, note = choose_effective_resolution("1h", start, end)

    assert effective == "1d"
    assert note == "Switched from 1h to 1d because the selected range is longer than 90 days."


def test_validate_interactive_query_range_rejects_bad_ranges_and_points():
    start = datetime(2026, 9, 5, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="start_time must be before end_time"):
        validate_interactive_query_range(start, start, MAX_INTERACTIVE_POINTS_DEFAULT)

    with pytest.raises(ValueError, match="max_points must be between 100 and 5000"):
        validate_interactive_query_range(start, start + timedelta(hours=1), 99)

    with pytest.raises(ValueError, match="max_points must be between 100 and 5000"):
        validate_interactive_query_range(start, start + timedelta(hours=1), 5001)

    with pytest.raises(ValueError, match="Interactive time range must not exceed 5 years"):
        validate_interactive_query_range(start, start + timedelta(days=365 * 5 + 1), MAX_INTERACTIVE_POINTS_DEFAULT)


def test_query_meta_includes_required_fields():
    meta = query_meta("1m", "1h", 1000, 168, False, "Switched from 1m to 1h because the selected range is longer than 48 hours.")

    assert meta == {
        "requested_resolution": "1m",
        "effective_resolution": "1h",
        "max_points": 1000,
        "returned_points": 168,
        "downsampled": False,
        "resolution_note": "Switched from 1m to 1h because the selected range is longer than 48 hours.",
    }
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: FAIL because `choose_effective_resolution`, `validate_interactive_query_range`, constants, and `query_meta` are not defined.

- [ ] **Step 3: Implement policy helpers**

Add imports and helpers in `backend/app/repository.py` near the existing resolution helpers:

```python
from math import ceil

MAX_INTERACTIVE_POINTS_DEFAULT = 1000
MIN_INTERACTIVE_POINTS = 100
MAX_INTERACTIVE_POINTS = 5000
MAX_INTERACTIVE_RANGE = timedelta(days=365 * 5)
RESOLUTION_DURATIONS = {
    "1m": timedelta(minutes=1),
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
}


def validate_interactive_query_range(start_time: datetime, end_time: datetime, max_points: int) -> None:
    if start_time >= end_time:
        raise ValueError("start_time must be before end_time")
    if max_points < MIN_INTERACTIVE_POINTS or max_points > MAX_INTERACTIVE_POINTS:
        raise ValueError("max_points must be between 100 and 5000")
    if end_time - start_time > MAX_INTERACTIVE_RANGE:
        raise ValueError("Interactive time range must not exceed 5 years")


def choose_effective_resolution(requested_resolution: str, start_time: datetime, end_time: datetime) -> tuple[str, str | None]:
    span = end_time - start_time
    if requested_resolution == "1m" and span > timedelta(hours=48):
        return "1h", "Switched from 1m to 1h because the selected range is longer than 48 hours."
    if requested_resolution == "1h" and span > timedelta(days=90):
        return "1d", "Switched from 1h to 1d because the selected range is longer than 90 days."
    if requested_resolution in RESOLUTION_DURATIONS:
        return requested_resolution, None
    raise ValueError("Unsupported resolution. Use one of: 1m, 1h, 1d")


def query_meta(
    requested_resolution: str,
    effective_resolution: str,
    max_points: int,
    returned_points: int,
    downsampled: bool,
    resolution_note: str | None,
) -> dict:
    return {
        "requested_resolution": requested_resolution,
        "effective_resolution": effective_resolution,
        "max_points": max_points,
        "returned_points": returned_points,
        "downsampled": downsampled,
        "resolution_note": resolution_note,
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: PASS for the new policy tests and no regression in existing repository tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: add time-series query guardrails policy"
```

---

### Task 2: Station Data Envelope And Continuous Aggregate Sources

**Files:**
- Modify: `backend/app/repository.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Consumes: `choose_effective_resolution(requested_resolution, start_time, end_time)`
- Consumes: `validate_interactive_query_range(start_time, end_time, max_points)`
- Consumes: `query_meta(requested_resolution, effective_resolution, max_points, returned_points, downsampled, resolution_note)`
- Produces: `StationDataResponse(BaseModel)` with `meta: QueryMeta` and `points: list[SensorPoint]`
- Produces: `fetch_station_data(connection, station_id: int, start_time: datetime, end_time: datetime, resolution: str, user: dict, max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT) -> dict`
- Produces: `station_data_source("1h")` SQL reading `sensor_data_hourly`
- Produces: `station_data_source("1d")` SQL reading `sensor_data_daily`

- [ ] **Step 1: Replace station source tests with continuous aggregate expectations**

Update the two existing station source tests in `backend/tests/test_repository.py`:

```python
def test_station_data_source_selects_hourly_continuous_aggregate():
    query, bucket_column = station_data_source("1h")

    assert bucket_column == "bucket"
    assert "FROM sensor_data_hourly" in query
    assert "time_bucket('1 hour', time)" not in query
    assert "valid_hours" in query


def test_station_data_source_selects_daily_continuous_aggregate():
    query, bucket_column = station_data_source("1d")

    assert bucket_column == "bucket"
    assert "FROM sensor_data_daily" in query
    assert "time_bucket('1 day'" not in query
    assert "valid_hours" in query
```

- [ ] **Step 2: Add station envelope repository test**

Extend `FakeStationDataConnection.fetch` to return the configured rows, then add:

```python
class FakeStationDataConnection:
    def __init__(self, region_id, rows=None):
        self.region_id = region_id
        self.rows = rows or []
        self.fetch_calls = []

    async def fetchrow(self, query, *args):
        if "SELECT region_id FROM stations" in query:
            return {"region_id": self.region_id}
        return None

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows


def test_fetch_station_data_returns_meta_and_points_envelope():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    connection = FakeStationDataConnection(
        region_id=20,
        rows=[
            {
                "time": row_time,
                "temperature": 30.5,
                "humidity": 72.0,
                "wind_speed": 2.1,
                "pm25": 41.2,
                "samples": None,
                "valid_hours": None,
            }
        ],
    )
    user = {"roles": ["super_admin"], "region_ids": []}

    payload = asyncio.run(
        fetch_station_data(
            connection,
            station_id=100,
            start_time=row_time,
            end_time=row_time + timedelta(hours=1),
            resolution="1m",
            user=user,
            max_points=1000,
        )
    )

    assert payload["meta"]["requested_resolution"] == "1m"
    assert payload["meta"]["effective_resolution"] == "1m"
    assert payload["meta"]["returned_points"] == 1
    assert payload["meta"]["downsampled"] is False
    assert payload["points"][0]["time"] == row_time
    assert payload["points"][0]["pm25"] == 41.2
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: FAIL because station aggregate SQL still reads raw `sensor_data`, `fetch_station_data` has no `max_points` parameter, and it returns a bare list.

- [ ] **Step 4: Add Pydantic envelope models**

In `backend/app/schemas.py`, add these models after `ScatterPoint`:

```python
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
```

- [ ] **Step 5: Change station SQL sources and repository return shape**

Update `station_data_source` for `1h` and `1d` in `backend/app/repository.py`:

```python
if resolution == "1h":
    return (
        """
        SELECT
            bucket,
            temperature,
            humidity,
            wind_speed,
            pm25,
            samples,
            NULL::bigint AS valid_hours
        FROM sensor_data_hourly
        WHERE station_id = $1
          AND bucket >= $2
          AND bucket <= $3
        ORDER BY bucket
        """,
        "bucket",
    )
if resolution == "1d":
    return (
        """
        SELECT
            bucket,
            temperature,
            humidity,
            wind_speed,
            pm25,
            samples,
            valid_hours
        FROM sensor_data_daily
        WHERE station_id = $1
          AND bucket >= $2
          AND bucket <= $3
        ORDER BY bucket
        """,
        "bucket",
    )
```

Then change `fetch_station_data` to:

```python
async def fetch_station_data(
    connection,
    station_id: int,
    start_time: datetime,
    end_time: datetime,
    resolution: str,
    user: dict,
    max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT,
) -> dict:
    validate_interactive_query_range(start_time, end_time, max_points)
    station_region_id = await resolve_station_region_id(connection, station_id)
    if not can_read_station(user, station_region_id):
        raise PermissionError("Station is outside assigned regions")

    effective_resolution, resolution_note = choose_effective_resolution(resolution, start_time, end_time)
    query, bucket_column = station_data_source(effective_resolution)
    rows = await connection.fetch(query, station_id, start_time, end_time)
    points = [{**dict(row), "time": row[bucket_column]} for row in rows]
    return {
        "meta": query_meta(resolution, effective_resolution, max_points, len(points), False, resolution_note),
        "points": points,
    }
```

- [ ] **Step 6: Update station route**

In `backend/app/main.py`, import `Annotated` from `typing`, import `MAX_INTERACTIVE_POINTS_DEFAULT` and `StationDataResponse`, then update the route:

```python
@app.get("/api/stations/{station_id}/data", response_model=StationDataResponse)
async def station_data(
    station_id: int,
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    resolution: str = Query("1m", pattern="^(1m|1h|1d)$"),
    max_points: int = Query(MAX_INTERACTIVE_POINTS_DEFAULT),
    user: dict = Depends(require_permission("stations", "read")),
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
```

- [ ] **Step 7: Run tests to verify pass**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/main.py backend/app/repository.py backend/app/schemas.py backend/tests/test_repository.py
git commit -m "feat: return station data query envelopes"
```

---

### Task 3: Station Detail Downsampling

**Files:**
- Modify: `backend/app/repository.py`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Consumes: `RESOLUTION_DURATIONS`
- Consumes: `query_meta(requested_resolution, effective_resolution, max_points, returned_points, downsampled, resolution_note)`
- Produces: `estimated_candidate_points(start_time: datetime, end_time: datetime, resolution: str) -> int`
- Produces: `downsample_interval_seconds(candidate_points: int, max_points: int, resolution: str) -> int`
- Produces: `station_downsample_source(resolution: str) -> tuple[str, str]`

- [ ] **Step 1: Add downsampling helper tests**

Add:

```python
def test_downsample_interval_seconds_scales_by_effective_resolution():
    assert estimated_candidate_points(
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 2, tzinfo=timezone.utc),
        "1m",
    ) == 1441

    assert downsample_interval_seconds(candidate_points=1441, max_points=1000, resolution="1m") == 120
    assert downsample_interval_seconds(candidate_points=2400, max_points=1000, resolution="1h") == 10800
```

- [ ] **Step 2: Add repository downsampling behavior test**

Add a fake connection that records SQL and returns one bucket row:

```python
def test_fetch_station_data_downsamples_when_candidate_count_exceeds_max_points():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    connection = FakeStationDataConnection(
        region_id=20,
        rows=[
            {
                "bucket": row_time,
                "temperature": 30.5,
                "humidity": 72.0,
                "wind_speed": 2.1,
                "pm25": 41.2,
                "samples": 2,
                "valid_hours": None,
            }
        ],
    )

    payload = asyncio.run(
        fetch_station_data(
            connection,
            station_id=100,
            start_time=row_time,
            end_time=row_time + timedelta(hours=24),
            resolution="1m",
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=100,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "floor(extract(epoch from time)" in query
    assert args[3] == 900
    assert payload["meta"]["downsampled"] is True
    assert payload["meta"]["returned_points"] == 1
    assert payload["meta"]["resolution_note"] == "Returned 100 representative points from 1441 available points."
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: FAIL because downsampling helpers and SQL path do not exist.

- [ ] **Step 4: Implement station downsampling helpers**

Add in `backend/app/repository.py`:

```python
def estimated_candidate_points(start_time: datetime, end_time: datetime, resolution: str) -> int:
    duration = RESOLUTION_DURATIONS[resolution]
    return int((end_time - start_time).total_seconds() // duration.total_seconds()) + 1


def downsample_interval_seconds(candidate_points: int, max_points: int, resolution: str) -> int:
    multiplier = ceil(candidate_points / max_points)
    return int(multiplier * RESOLUTION_DURATIONS[resolution].total_seconds())


def station_downsample_source(resolution: str) -> tuple[str, str]:
    table, bucket_column = resolution_source(resolution)
    return (
        f"""
        SELECT
            to_timestamp(floor(extract(epoch from {bucket_column}) / $4) * $4) AS bucket,
            avg(temperature) AS temperature,
            avg(humidity) AS humidity,
            avg(wind_speed) AS wind_speed,
            avg(pm25) AS pm25,
            sum(samples)::bigint AS samples,
            sum(valid_hours)::bigint AS valid_hours
        FROM {table}
        WHERE station_id = $1
          AND {bucket_column} >= $2
          AND {bucket_column} <= $3
        GROUP BY bucket
        ORDER BY bucket
        """,
        "bucket",
    )
```

- [ ] **Step 5: Wire downsampling into `fetch_station_data`**

Change the query selection block:

```python
candidate_points = estimated_candidate_points(start_time, end_time, effective_resolution)
downsampled = candidate_points > max_points
if downsampled:
    query, bucket_column = station_downsample_source(effective_resolution)
    interval_seconds = downsample_interval_seconds(candidate_points, max_points, effective_resolution)
    rows = await connection.fetch(query, station_id, start_time, end_time, interval_seconds)
    resolution_note = f"Returned {max_points} representative points from {candidate_points} available points."
else:
    query, bucket_column = station_data_source(effective_resolution)
    rows = await connection.fetch(query, station_id, start_time, end_time)
points = [{**dict(row), "time": row[bucket_column]} for row in rows]
return {
    "meta": query_meta(resolution, effective_resolution, max_points, len(points), downsampled, resolution_note),
    "points": points,
}
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/repository.py backend/tests/test_repository.py
git commit -m "feat: downsample station chart queries"
```

---

### Task 4: Analytics Series And Scatter Envelopes

**Files:**
- Modify: `backend/app/repository.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas.py`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Consumes: `AnalyticsSeriesResponse`
- Consumes: `AnalyticsScatterResponse`
- Consumes: `estimated_candidate_points(start_time, end_time, resolution)`
- Consumes: `downsample_interval_seconds(candidate_points, max_points, resolution)`
- Produces: `fetch_analytics_series(connection, station_ids: list[int], metric: str, start_time: datetime, end_time: datetime, resolution: str, max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT) -> dict`
- Produces: `fetch_analytics_scatter(connection, station_id: int, x_metric: str, y_metric: str, start_time: datetime, end_time: datetime, resolution: str, max_points: int = MAX_INTERACTIVE_POINTS_DEFAULT) -> dict`

- [ ] **Step 1: Add analytics envelope tests**

Add fake connection tests:

```python
class FakeAnalyticsConnection:
    def __init__(self, rows):
        self.rows = rows
        self.fetch_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows


def test_fetch_analytics_series_returns_envelope_and_uses_effective_resolution():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([
        {
            "time": row_time,
            "station_id": 1,
            "station_code": "AQ-001",
            "station_name": "Station 1",
            "value": 42.0,
        }
    ])

    payload = asyncio.run(
        fetch_analytics_series(
            connection,
            station_ids=[1],
            metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(days=7),
            resolution="1m",
            max_points=1000,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "FROM sensor_data_hourly data" in query
    assert payload["meta"]["requested_resolution"] == "1m"
    assert payload["meta"]["effective_resolution"] == "1h"
    assert payload["points"][0]["aqi_level"] is not None


def test_fetch_analytics_scatter_returns_envelope_and_downsamples_pairs():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([
        {"time": row_time, "station_id": 1, "x": 30.0, "y": 42.0}
    ])

    payload = asyncio.run(
        fetch_analytics_scatter(
            connection,
            station_id=1,
            x_metric="temperature",
            y_metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(hours=24),
            resolution="1m",
            max_points=100,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "avg(temperature) AS x" in query
    assert "avg(pm25) AS y" in query
    assert args[3] == 900
    assert payload["meta"]["downsampled"] is True
    assert payload["points"][0]["x"] == 30.0
    assert payload["points"][0]["y"] == 42.0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: FAIL because analytics functions return bare lists and do not accept `max_points`.

- [ ] **Step 3: Update analytics repository functions**

For `fetch_analytics_series`, validate range, choose effective resolution, and return:

```python
candidate_points = estimated_candidate_points(start_time, end_time, effective_resolution)
downsampled = candidate_points > max_points
interval_seconds = downsample_interval_seconds(candidate_points, max_points, effective_resolution) if downsampled else None
```

Use normal SQL when `downsampled` is false. Use this SQL when true:

```python
f"""
SELECT
    to_timestamp(floor(extract(epoch from data.{bucket_column}) / $4) * $4) AS time,
    s.id AS station_id,
    s.code AS station_code,
    s.name AS station_name,
    avg(data.{column}) AS value
FROM {table} data
JOIN stations s ON s.id = data.station_id
WHERE data.station_id = ANY($1::bigint[])
  AND data.{bucket_column} >= $2
  AND data.{bucket_column} <= $3
GROUP BY time, s.id, s.code, s.name
ORDER BY time, s.code
"""
```

Pass args `(station_ids, start_time, end_time, interval_seconds)` because `metric_column(metric)` already validates the embedded column name. Return:

```python
points = [{**dict(row), "metric": metric, "aqi_level": aqi_level(row["value"]) if metric == "pm25" else None} for row in rows]
return {
    "meta": query_meta(resolution, effective_resolution, max_points, len(points), downsampled, resolution_note),
    "points": points,
}
```

For `fetch_analytics_scatter`, downsample paired axes in one query:

```python
f"""
SELECT
    to_timestamp(floor(extract(epoch from {bucket_column}) / $4) * $4) AS time,
    station_id,
    avg({x_column}) AS x,
    avg({y_column}) AS y
FROM {table}
WHERE station_id = $1
  AND {bucket_column} >= $2
  AND {bucket_column} <= $3
  AND {x_column} IS NOT NULL
  AND {y_column} IS NOT NULL
GROUP BY time, station_id
ORDER BY time
"""
```

- [ ] **Step 4: Update analytics routes**

In `backend/app/main.py`, change response models and add `max_points`:

```python
@app.get("/api/analytics/series", response_model=AnalyticsSeriesResponse)
async def analytics_series(
    station_ids: Annotated[str, Query()],
    start_time: Annotated[datetime, Query()],
    end_time: Annotated[datetime, Query()],
    metric: str = Query("pm25"),
    resolution: str = Query("1h", pattern="^(1m|1h|1d)$"),
    max_points: int = Query(MAX_INTERACTIVE_POINTS_DEFAULT),
    user: dict = Depends(require_permission("reports", "read")),
) -> dict:
    async with database.acquire() as connection:
        try:
            return await fetch_analytics_series(connection, parse_id_list(station_ids), metric, start_time, end_time, resolution, max_points)
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
    user: dict = Depends(require_permission("reports", "read")),
) -> dict:
    async with database.acquire() as connection:
        try:
            return await fetch_analytics_scatter(connection, station_id, x_metric, y_metric, start_time, end_time, resolution, max_points)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
```

Keep `analytics_heatmap` as a bare list because the spec does not change that endpoint.

- [ ] **Step 5: Run tests to verify pass**

Run: `cd backend && pytest tests/test_repository.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/repository.py backend/app/schemas.py backend/tests/test_repository.py
git commit -m "feat: return analytics query envelopes"
```

---

### Task 5: Frontend API Normalization

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/features/stations/stationTimeRange.js`
- Modify: `frontend/src/features/stations/stationTimeRange.test.mjs`

**Interfaces:**
- Produces: `normalizeQueryEnvelope(payload) -> { meta: object | null, points: array }`
- Produces: `queryOptimizationNote(meta) -> string`
- Produces: `preferredStationResolution({ startTime, endTime }) -> "1m" | "1h" | "1d"`
- Updates: `fetchStationData({ stationId, startTime, endTime, resolution, maxPoints, currentUser })` returns a normalized envelope.
- Updates: `fetchAnalyticsSeries({ stationIds, metric, startTime, endTime, resolution, maxPoints, currentUser })` returns a normalized envelope.
- Updates: `fetchAnalyticsScatter({ stationId, xMetric, yMetric, startTime, endTime, resolution, maxPoints, currentUser })` returns a normalized envelope.

- [ ] **Step 1: Add frontend helper tests**

Update import in `frontend/src/features/stations/stationTimeRange.test.mjs` and add:

```javascript
import {
  defaultStationTimeRange,
  isStationTimeRangeValid,
  preferredStationResolution,
  queryOptimizationNote,
  stationDataQuery,
} from "./stationTimeRange.js";

assert.equal(
  preferredStationResolution({
    startTime: "2026-09-01T00:00",
    endTime: "2026-09-01T23:59",
  }),
  "1m",
);

assert.equal(
  preferredStationResolution({
    startTime: "2026-09-01T00:00",
    endTime: "2026-09-07T00:00",
  }),
  "1h",
);

assert.equal(
  preferredStationResolution({
    startTime: "2026-01-01T00:00",
    endTime: "2026-06-01T00:00",
  }),
  "1d",
);

assert.equal(
  queryOptimizationNote({
    requested_resolution: "1m",
    effective_resolution: "1h",
    downsampled: false,
    resolution_note: "Switched from 1m to 1h because the selected range is longer than 48 hours.",
  }),
  "Dữ liệu đã được tối ưu: hiển thị 1h thay vì 1m vì khoảng thời gian quá dài.",
);

assert.equal(
  queryOptimizationNote({
    requested_resolution: "1h",
    effective_resolution: "1h",
    downsampled: true,
    resolution_note: "Returned 1000 representative points from 86342 available points.",
  }),
  "Dữ liệu đã được tối ưu: hiển thị tối đa 1000 điểm đại diện.",
);
```

- [ ] **Step 2: Add API normalization unit test by exporting helper**

Create or extend a lightweight API test if one exists. If no API test exists, add `frontend/src/api.test.mjs`:

```javascript
import assert from "node:assert/strict";

import { normalizeQueryEnvelope } from "./api.js";

const meta = {
  requested_resolution: "1m",
  effective_resolution: "1h",
  max_points: 1000,
  returned_points: 1,
  downsampled: false,
  resolution_note: "Switched from 1m to 1h because the selected range is longer than 48 hours.",
};

assert.deepEqual(normalizeQueryEnvelope({ meta, points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }] }), {
  meta,
  points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }],
});

assert.deepEqual(normalizeQueryEnvelope([{ time: "2026-09-06T00:00:00Z", pm25: 42 }]), {
  meta: null,
  points: [{ time: "2026-09-06T00:00:00Z", pm25: 42 }],
});
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
cd frontend
node src/features/stations/stationTimeRange.test.mjs
node src/api.test.mjs
```

Expected: FAIL because helpers are not implemented.

- [ ] **Step 4: Implement frontend helpers**

In `frontend/src/api.js`:

```javascript
export function normalizeQueryEnvelope(payload) {
  if (Array.isArray(payload)) return { meta: null, points: payload };
  return {
    meta: payload?.meta || null,
    points: Array.isArray(payload?.points) ? payload.points : [],
  };
}
```

Update fetchers:

```javascript
export async function fetchStationData({ stationId, startTime, endTime, resolution, maxPoints = 1000, currentUser }) {
  const params = new URLSearchParams({
    start_time: new Date(startTime).toISOString(),
    end_time: new Date(endTime).toISOString(),
    resolution,
    max_points: String(maxPoints),
  });
  await requireOk(response, "Cannot load sensor data");
  return normalizeQueryEnvelope(await response.json());
}
```

Apply the same `maxPoints = 1000` parameter and `normalizeQueryEnvelope(await response.json())` return to `fetchAnalyticsSeries` and `fetchAnalyticsScatter`. Do not change `fetchAnalyticsHeatmap`.

In `frontend/src/features/stations/stationTimeRange.js`:

```javascript
export function preferredStationResolution({ startTime, endTime }) {
  const start = new Date(startTime);
  const end = new Date(endTime);
  const hours = (end.getTime() - start.getTime()) / (60 * 60 * 1000);
  if (!Number.isFinite(hours)) return "1m";
  if (hours > 24 * 90) return "1d";
  if (hours > 48) return "1h";
  return "1m";
}

export function queryOptimizationNote(meta) {
  if (!meta) return "";
  if (meta.requested_resolution !== meta.effective_resolution) {
    return `Dữ liệu đã được tối ưu: hiển thị ${meta.effective_resolution} thay vì ${meta.requested_resolution} vì khoảng thời gian quá dài.`;
  }
  if (meta.downsampled) {
    return `Dữ liệu đã được tối ưu: hiển thị tối đa ${meta.max_points} điểm đại diện.`;
  }
  return "";
}
```

- [ ] **Step 5: Run tests to verify pass**

Run:

```bash
cd frontend
node src/features/stations/stationTimeRange.test.mjs
node src/api.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api.js frontend/src/api.test.mjs frontend/src/features/stations/stationTimeRange.js frontend/src/features/stations/stationTimeRange.test.mjs
git commit -m "feat: normalize time-series query envelopes"
```

---

### Task 6: Frontend Station And Analytics Views

**Files:**
- Modify: `frontend/src/features/stations/StationParameters.jsx`
- Modify: `frontend/src/features/analytics/AnalyticsReports.jsx`

**Interfaces:**
- Consumes: `fetchStationData({ stationId, startTime, endTime, resolution, currentUser }) -> { meta, points }`
- Consumes: `fetchAnalyticsSeries({ stationIds, metric, startTime, endTime, resolution, currentUser }) -> { meta, points }`
- Consumes: `fetchAnalyticsScatter({ stationId, xMetric, yMetric, startTime, endTime, resolution, currentUser }) -> { meta, points }`
- Consumes: `queryOptimizationNote(meta) -> string`

- [ ] **Step 1: Update station detail state**

In `StationParameters.jsx`, import `queryOptimizationNote`, add state, and compute label:

```javascript
const [queryMeta, setQueryMeta] = useState(null);
const optimizationNote = queryOptimizationNote(queryMeta);
const effectiveResolution = queryMeta?.effective_resolution || resolution;
const effectiveResolutionOption = stationResolutionOptions.find((item) => item.value === effectiveResolution) || selectedResolution;
```

Change detail row labels to use `effectiveResolutionOption.label`.

- [ ] **Step 2: Consume station envelope**

Change fetch handler:

```javascript
.then((payload) => {
  if (cancelled) return;
  const normalized = normalizeSeries(payload.points, payload.meta?.effective_resolution || resolution);
  setQueryMeta(payload.meta);
  setBackendSeries(normalized);
  setDataSource("backend");
})
```

Reset `setQueryMeta(null)` in invalid-range and error paths.

- [ ] **Step 3: Render station optimization note**

Under the range error block, add:

```jsx
{optimizationNote && (
  <p className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-800">
    {optimizationNote}
  </p>
)}
```

- [ ] **Step 4: Update analytics state**

In `AnalyticsReports.jsx`, import `queryOptimizationNote`, add:

```javascript
const [seriesMeta, setSeriesMeta] = useState(null);
const [scatterMeta, setScatterMeta] = useState(null);
const analyticsOptimizationNote = queryOptimizationNote(seriesMeta) || queryOptimizationNote(scatterMeta);
```

Change load handling:

```javascript
setSeries(seriesPayload.points);
setScatter(scatterPayload.points);
setSeriesMeta(seriesPayload.meta);
setScatterMeta(scatterPayload.meta);
```

- [ ] **Step 5: Render analytics optimization note**

Below the filter section, add:

```jsx
{analyticsOptimizationNote && (
  <p className="rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-800">
    {analyticsOptimizationNote}
  </p>
)}
```

- [ ] **Step 6: Build frontend**

Run: `cd frontend && npm run build`

Expected: Vite build completes without JSX/import errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/stations/StationParameters.jsx frontend/src/features/analytics/AnalyticsReports.jsx
git commit -m "feat: show query optimization notes"
```

---

### Task 7: Full Verification

**Files:**
- No source files modified.

**Interfaces:**
- Verifies backend repository behavior, frontend helper behavior, and production frontend build.

- [ ] **Step 1: Run backend tests**

Run: `cd backend && pytest -q`

Expected: All backend tests pass.

- [ ] **Step 2: Run frontend unit tests**

Run:

```bash
cd frontend
for test_file in $(find src -name "*.test.mjs" | sort); do node "$test_file"; done
```

Expected: Every Node assert test exits 0.

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`

Expected: Vite production build succeeds.

- [ ] **Step 4: Inspect diff**

Run: `git diff --stat HEAD~6..HEAD`

Expected: Diff contains only the planned backend, frontend, and test files for query guardrails. Existing export endpoint files are unchanged except shared imports/helpers if a prior task required them.

- [ ] **Step 5: Commit verification note if needed**

No commit is required when verification passes without file changes. If formatting or import-order fixes are needed, commit only those fixes:

```bash
git add <fixed-files>
git commit -m "chore: verify time-series query guardrails"
```
