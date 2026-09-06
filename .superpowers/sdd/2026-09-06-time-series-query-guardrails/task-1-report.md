# Task 1 Report: Backend Query Policy Helpers

Status: DONE

## Summary

Implemented backend time-series query policy helpers in `backend/app/repository.py` and added focused repository tests in `backend/tests/test_repository.py`.

## Changes

- Added `MAX_INTERACTIVE_POINTS_DEFAULT = 1000`.
- Added `MIN_INTERACTIVE_POINTS = 100` and `MAX_INTERACTIVE_POINTS = 5000`.
- Added `MAX_INTERACTIVE_RANGE = timedelta(days=365 * 5)`.
- Added `RESOLUTION_DURATIONS = {"1m": timedelta(minutes=1), "1h": timedelta(hours=1), "1d": timedelta(days=1)}`.
- Added `validate_interactive_query_range(...)`.
- Added `choose_effective_resolution(...)`.
- Added `query_meta(...)`.
- Added the Task 1 policy tests near the existing resolution tests.

## TDD Evidence

RED command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

RED result:

```text
ImportError: cannot import name 'MAX_INTERACTIVE_POINTS_DEFAULT' from 'app.repository'
1 error
```

GREEN command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

GREEN result:

```text
14 passed in 0.07s
```

Fresh pre-commit verification:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

Result:

```text
14 passed in 0.07s
```

## Commit

- `3015707 feat: add time-series query guardrails policy`

## Self-Review

- Scope is limited to `backend/app/repository.py` and `backend/tests/test_repository.py`.
- No route wiring, response envelope changes, downsampling behavior, or frontend changes were added.
- Error messages and resolution notes match the Task 1 brief verbatim.
- Query meta output includes the required fields and preserves the provided values.
- Range validation enforces start/end ordering, max point bounds, and the 5-year interactive range cap.

## Concerns

None.

---

# Review Fix Report

Status: DONE

## Review Finding Addressed

- Fixed `choose_effective_resolution("1m", start, end)` for ranges longer than 90 days so the 90-day rule takes precedence and returns `1d`.
- Added regression coverage for a 120-day `1m` request.
- Left the unused `ceil` import unchanged because it is deferred for Task 3.

## TDD Evidence

RED command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

RED result:

```text
.....F.........                                                          [100%]
=================================== FAILURES ===================================
______ test_choose_effective_resolution_upgrades_one_minute_after_90_days ______

    def test_choose_effective_resolution_upgrades_one_minute_after_90_days():
        start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(days=120)

        effective, note = choose_effective_resolution("1m", start, end)

>       assert effective == "1d"
E       AssertionError: assert '1h' == '1d'

1 failed, 14 passed in 0.12s
```

GREEN command:

```bash
PYTHONPATH=backend .venv/bin/python -m pytest backend/tests/test_repository.py -q
```

GREEN result:

```text
...............                                                          [100%]
15 passed in 0.07s
```

## Self-Review

- The new test fails if the 48-hour `1m` rule is evaluated before the 90-day rule.
- The existing `1h` over 90 days test still validates that `1h` requests return the same effective resolution and note as before.
- No route, envelope, downsampling, frontend, or unrelated cleanup changes were made.
