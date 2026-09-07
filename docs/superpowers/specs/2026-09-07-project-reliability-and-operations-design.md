# Project Reliability and Operations Design

**Date:** 2026-09-07  
**Status:** Draft for review  
**Scope:** Worker reliability, in-app station alerts, ingestion observability, station data UX, data quality, production security, and verification/backup operations.

## Goal

Make FTP-to-database ingestion reliable and observable, clearly report station connectivity in the web interface, improve the station data workflow, and establish safe production operating practices without changing the existing station/QCVN domain model.

## Success criteria

- A temporary FTP or database failure does not permanently stop an ingestion worker.
- The web interface records and displays a deduplicated notification when a station becomes offline after 30 minutes without new sensor data, and when it recovers.
- Operators can see the latest ingestion time, processed/error counts, and the latest ingestion error.
- Station data can be filtered, sorted, paginated server-side, and exported as CSV.
- Invalid or suspicious files are retained with a reason and can be retried without losing the original file.
- Production secrets are supplied externally, default credentials are rejected outside development, and access remains auditable.
- Automated tests cover parser, assignment, ingestion, API, notification transition, and database integration paths; a documented backup can be restored.

## Constraints and decisions

- Notifications are in-app only. No Telegram or email integration is included in this scope.
- The existing `sensor_data`, `latest_station_readings`, `ftp_files`, and `station_ftp_assignments` concepts remain the source of truth.
- The 30-minute threshold remains the existing `STALE_AFTER` value and is centralized in configuration.
- Existing historical sensor data must not be deleted or rewritten.
- Changes are delivered in independently testable phases; each phase may be deployed separately.
- Existing API consumers remain compatible where practical; new response fields are additive unless a breaking change is explicitly required.

## Architecture

### Ingestion reliability

The worker keeps its current per-cycle processing model but isolates failures by operation: database assignment lookup, FTP connection, file download, parsing, and database write. Transient connection errors use bounded exponential backoff with jitter and the next poll cycle continues. Permanent file errors are recorded and moved to the quarantine location. Container healthchecks verify that the process is alive and can reach the required database; the compose deployment uses a restart policy for worker services.

The current in-memory processed-file signature remains a performance optimization only. Database uniqueness (`station_id`, `time`) and file identity records provide idempotency after a restart.

### In-app connection notifications

Add a small connection-state/notification layer:

- `station_connection_state`: one row per station with the last observed state, transition time, and last notification transition.
- `notifications`: user-visible notification rows with station, type (`offline` or `recovered`), message, created time, read time, and a deduplication key.

The worker updates station observation data as it writes readings. A backend monitoring operation compares `last_seen_at` to `STALE_AFTER`, performs an idempotent state transition, and creates one notification per transition. The API exposes unread/list/read operations. The frontend shows an unread count and a notification panel; the station dashboard continues to show the derived `Mất kết nối` status.

### Ingestion observability

Add ingestion run/file metrics without duplicating sensor data:

- `ftp_ingestion_runs`: worker/server, start/end, status, files scanned, files processed, rows written, errors, and last error.
- Extend `ftp_files` with processing status, processed time, row count, error message, and a stable file signature where the columns do not already exist.

The backend exposes scoped read-only summaries. The UI presents the latest state on the station detail and an operations section; credentials are never included.

### Station data experience

Extend the existing station-data API with validated filter parameters for metric selection, sorting, page/page-size, and CSV export. The existing filtered table remains backed by the API rather than loading the entire history into the browser. Export uses the same authorization and filter validation as the table.

### Data quality and quarantine

Parsing is split into validation and persistence. Validation checks supported extension, required identifiers, timestamp format/timezone, numeric ranges, and duplicate/out-of-order policy. Invalid files remain available in quarantine with a structured reason and can be retried after correction. Valid rows continue to use the existing upsert behavior.

### Production security and operations

- Production compose configuration requires `DATABASE_URL`, credential encryption key, admin bootstrap credentials, and FTP secrets through environment/secret files.
- Development defaults remain available only under an explicit development profile.
- API responses continue to redact passwords; logs redact connection strings and credentials.
- Add a documented backup command for PostgreSQL and a restore verification procedure. Do not add destructive automatic cleanup.

### Verification and CI

Add deterministic unit tests for pure functions, worker tests with mocked FTP/database boundaries, API tests, and an opt-in PostgreSQL integration suite. CI runs lint/build/unit tests and marks integration tests according to the available service container. Deployment verification checks health, bundle/API version, worker status, and a real ingestion round trip.

## Phased delivery

### Phase 1 — Worker reliability

Deliver bounded retries/backoff, failure isolation, structured logs, worker healthcheck/restart policy, and regression tests for database timeout and FTP failure. Acceptance: a worker remains alive through a transient failure and processes the file once the dependency recovers.

### Phase 2 — In-app offline/recovery notifications

Deliver migration, transition evaluator, notification API/UI, deduplication, and tests for offline/recovery/repeated polling. Acceptance: one offline notification appears after 30 minutes, no duplicates are created, and one recovery notification appears after data resumes.

### Phase 3 — Ingestion monitoring

Deliver run/file metrics, API summary, station detail display, and tests. Acceptance: an operator can identify the last successful file, rows written, and latest error for a station/FTP server.

### Phase 4 — Data table, filters, and export

Deliver server-side metric/sort filters, CSV export, UI controls, and authorization tests. Acceptance: table and export return the same filtered dataset and remain bounded for large histories.

### Phase 5 — Data quality/quarantine

Deliver validation result types, persisted error details, retry endpoint/action, and parser tests. Acceptance: malformed files are not silently marked successful and can be retried after correction.

### Phase 6 — Production security

Deliver production configuration validation, secret redaction checks, removal of unsafe defaults in production, and operator documentation. Acceptance: production startup fails clearly when required secrets are missing and no password appears in API/log output.

### Phase 7 — Integration, CI, and backup

Deliver PostgreSQL integration fixtures, CI workflow, backup/restore scripts and deployment checklist. Acceptance: CI is reproducible and a backup is restored into a disposable database with sensor/assignment counts verified.

## Risks and mitigations

- **Notification duplication across workers:** use a database uniqueness key and transaction-level upsert.
- **Large exports:** stream CSV rows and enforce maximum range/row limits.
- **Old files replayed after restart:** retain database uniqueness and file signatures; report replay counts instead of silently hiding them.
- **Production secret migration:** introduce validation and documentation first, then remove defaults only from production profile.
- **Schema migration failure:** use additive, idempotent migrations and run them against a database snapshot before deployment.

## Out of scope

- Telegram/email/SMS delivery.
- Replacing FTP with MQTT.
- Redesigning station, QCVN, or RBAC ownership models.
- Deleting historical sensor data or automatically deleting files from FTP.
