# Task 2 Report: Station Data Envelope And Continuous Aggregate Sources

Status: DONE_WITH_CONCERNS

## Summary

Implemented Task 2 station data wiring. Station data now returns a `{meta, points}` envelope, uses effective resolution selection, validates interactive query ranges, and reads hourly/daily station data from continuous aggregate sources.

## Changes

- Added `station_data_source(resolution)` in `backend/app/repository.py`.
- Added station SQL sources for:
  - `1m`: raw `sensor_data`
  - `1h`: `sensor_data_hourly`
  - `1d`: `sensor_data_daily`
- Changed `fetch_station_data(...)` to accept `user` and `max_points`, validate the range, resolve station region, enforce station read access, choose effective resolution, and return `meta` plus `points`.
- Added `can_read_station(...)` and `resolve_station_region_id(...)` to support station data permission checks.
- Added `QueryMeta`, `StationDataResponse`, `AnalyticsSeriesResponse`, and `AnalyticsScatterResponse` schemas.
- Added minimal `AnalyticsPoint` and `ScatterPoint` schemas because this branch did not already define them.
- Updated `/api/stations/{station_id}/data` to return `StationDataResponse`, accept `max_points`, normalize naive datetimes, and map lookup, permission, and validation errors to HTTP responses.
- Added repository tests for continuous aggregate station sources and station data envelope output.

## TDD Evidence

RED command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

RED result:

```text
ImportError: cannot import name 'station_data_source' from 'app.repository'
1 error
```

GREEN command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

GREEN result:

```text
18 passed in 0.09s
```

Fresh pre-commit verification:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

Result:

```text
18 passed in 0.12s
```

Additional checks:

```bash
git diff --check
PYTHONPATH=backend .venv/bin/python -m compileall -q backend/app
```

Both exited 0.

## Self-Review

- Scope is limited to station data repository/route wiring, shared schema declarations requested by the brief, and repository tests.
- No downsampling implementation was added.
- No analytics repository or analytics route behavior was changed.
- No frontend files were changed.
- The `1h` and `1d` station SQL paths read continuous aggregate tables instead of aggregating raw `sensor_data`.
- `fetch_station_data` returns query metadata using the Task 1 `query_meta` helper and keeps `downsampled` as `False` for this task.
- Permission behavior is enforced through existing role/region data: super admins can read all stations; other users can read stations in their assigned regions.

## Concerns

- The brief's route snippet uses `require_permission("stations", "read")`, but this branch does not define `require_permission`. I kept the existing `current_user` dependency and enforced station read authorization in the repository to avoid introducing a new auth helper outside Task 2.
- The brief says to add envelope models after `ScatterPoint`, but this branch did not have `AnalyticsPoint` or `ScatterPoint`. I added minimal definitions so the requested response models can import and type-check without implementing analytics behavior.
