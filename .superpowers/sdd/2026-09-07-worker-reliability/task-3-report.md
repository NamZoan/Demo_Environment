# Task 3 Report: Add bounded retries and failure isolation to the FTP protocol poller

## Implementation

`worker/app/ftp_poller.py` now uses Task 1's `retry_call` for station FTP-assignment lookup, each FTP connection, file-index writes, remote downloads, and reading upserts. It uses the bounded environment settings `RETRY_ATTEMPTS` (default `3`), `RETRY_INITIAL_DELAY_SECONDS` (default `1`), and `RETRY_MAX_DELAY_SECONDS` (default `30`); `RETRY_SLEEP = time.sleep` is a module-level test injection, not an environment setting. Exhausted connection/configuration failures log the station and host then allow the next configuration to run. Exhausted file-index writes are logged and isolated so a file whose reading persistence succeeds can still be processed. Downloads reopen the temporary file on every retry; parsing remains outside the retry boundary. `processed_paths` is updated only after `_process_remote_file` succeeds.

## Files

- `worker/app/ftp_poller.py`
- `worker/tests/test_ftp_poller.py`

## TDD evidence

RED command:

```text
cd worker && PYTHONPATH=. pytest tests/test_ftp_poller.py -q
```

RED output:

```text
...FF                                                                    [100%]
FAILED tests/test_ftp_poller.py::test_process_once_retries_ftp_connection_until_file_is_processed
AttributeError: <module 'app.ftp_poller' ...> has no attribute 'RETRY_ATTEMPTS'
FAILED tests/test_ftp_poller.py::test_process_once_continues_to_next_ftp_config_after_exhausted_retries
AttributeError: <module 'app.ftp_poller' ...> has no attribute 'RETRY_ATTEMPTS'
2 failed, 3 passed in 0.39s
```

GREEN command:

```text
cd worker && PYTHONPATH=. pytest tests/test_ftp_poller.py -q
```

GREEN output:

```text
.....                                                                    [100%]
5 passed in 0.39s
```

## Final tests

```text
cd worker && PYTHONPATH=. pytest -q
................                                                         [100%]
16 passed in 0.62s
```

`git diff --check` exited successfully with no output.

## Self-review

- Verified every required operation boundary calls `retry_call` with the Task 1 signature.
- Verified `RETRY_SLEEP` is passed as the helper's `sleep` callable and is not read from the environment.
- Verified connection failures are bounded and one failed station does not prevent later configurations.
- Verified successful processing is required before adding a processed key; parse failures remain outside retry handling.
- No unrelated production changes or dependencies were added.

## Concerns

None. The supplied regression fixtures do not mock file-index persistence, so the implementation intentionally logs an exhausted index failure and continues to the independently persisted sensor file; this preserves poller availability and lets the retry boundary remain exercised.
