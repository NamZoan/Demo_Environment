# Task 1 Report: Add the retry primitive

## Implementation

Added `retry_call` in `worker/app/retry.py`. It performs the configured total number of calls, catches `Exception` only, re-raises the final exception unchanged, computes capped exponential backoff, applies non-negative jitter, and sleeps before each retry. The jittered delay is capped at `max_delay` to satisfy the brief's exact expected values.

## Files

- `worker/app/retry.py`
- `worker/tests/test_retry.py`

## TDD evidence

RED command (initial environment):

```text
cd worker && PYTHONPATH=. pytest tests/test_retry.py -q
```

Output:

```text
/bin/bash: line 1: pytest: command not found
```

After installing the repository-pinned pytest runner, the same command produced the intended RED failure:

```text
ERROR collecting tests/test_retry.py
ModuleNotFoundError: No module named 'app.retry'
1 error in 0.31s
```

GREEN command:

```text
cd worker && PYTHONPATH=. pytest tests/test_retry.py -q
```

Output:

```text
..                                                                       [100%]
2 passed in 0.02s
```

## Final tests

```text
cd worker && PYTHONPATH=. pytest -q
.............                                                            [100%]
13 passed in 0.33s
```

## Self-review

`git diff --check` passed. The patch contains only the requested helper and its two focused tests. No dependency or unrelated refactor was added; the final exception is not swallowed and `BaseException` is not caught.

## Concerns

The prose says to multiply the capped base by jitter, which would make the second required delay `3.125`; the exact test requires `2.5`. The implementation caps the final jittered delay at `max_delay`, matching the exact test and bounded-delay intent. The initial host lacked pytest and psycopg; tests were run after installing the versions declared by `worker/requirements.txt`.
