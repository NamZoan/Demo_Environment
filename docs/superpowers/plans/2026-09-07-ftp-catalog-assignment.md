# FTP Catalog and Station Assignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow administrators to create an independent FTP catalog first and assign each FTP configuration to one or more stations later.

**Architecture:** Add `ftp_servers` as the independent encrypted FTP catalog and `station_ftp_assignments` as the station-to-FTP relation. Preserve legacy `station_ftp_configs` rows through an idempotent migration, expose the new relation through the existing FTP API paths, and keep station file browsing/worker ingestion resolving FTP through the assignment table.

**Tech Stack:** PostgreSQL/TimescaleDB SQL migrations, FastAPI/asyncpg, Python worker/psycopg, React/Vite/Tailwind.

**Spec:** Approved in chat: one FTP may be assigned to multiple stations; FTP creation must not require a station.

## Global Constraints

- Passwords remain encrypted at rest and never appear in API responses.
- Existing station-specific FTP browsing and file indexing continue to work through station assignments.
- Existing legacy FTP rows are migrated without destructive deletion.
- FTP catalog management remains restricted to users who can manage the existing FTP configuration.

---

### Task 1: Add schema migration and repository tests

**Files:**
- Modify: `db/init/001_schema.sql`
- Modify: `backend/app/repository.py`
- Test: `backend/tests/test_station_ftp_schema.py`

- [ ] Write failing tests asserting the new tables, migration copy, and assignment query exist.
- [ ] Run the focused tests and confirm they fail because the new schema/query is absent.
- [ ] Add `ftp_servers` and `station_ftp_assignments`, including encrypted password storage and assignment root path.
- [ ] Add idempotent legacy migration from `station_ftp_configs` into the new tables.
- [ ] Run focused tests again.

### Task 2: Change backend FTP API to catalog CRUD and assignments

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/repository.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_station_ftp_api.py`

- [ ] Add request/response fields for FTP name, independent server data, and station assignments.
- [ ] Write failing tests for creating an unassigned FTP, updating station assignments, and deleting a catalog entry.
- [ ] Implement repository CRUD with validation, encrypted passwords, station authorization, and no password in responses.
- [ ] Keep `fetch_station_ftp_config` resolving the assigned catalog entry for station status/files.
- [ ] Run the focused backend tests.

### Task 3: Update worker and station compatibility path

**Files:**
- Modify: `worker/app/ftp_poller.py`
- Modify: `backend/app/repository.py`
- Test: `worker/tests/test_ftp_poller.py` or an existing focused worker test location

- [ ] Write a failing query/shape test for assignments resolving to station-specific FTP settings.
- [ ] Update worker SQL to join `station_ftp_assignments` with `ftp_servers` and use assignment roots.
- [ ] Preserve the legacy station-create payload by creating/assigning a catalog FTP when `ftp_config` is supplied.
- [ ] Run worker/backend focused tests.

### Task 4: Replace FTP UI with independent catalog management

**Files:**
- Modify: `frontend/src/api.js`
- Modify: `frontend/src/features/ftp/FtpManagement.jsx`
- Modify: `frontend/src/features/stations/StationManager.jsx`

- [ ] Replace station-required form state with FTP catalog fields and optional station assignment selection.
- [ ] Keep FTP file navigation linked to assigned stations.
- [ ] Ensure the Add FTP button is enabled with zero stations and displays “Chưa gán trạm” for unassigned entries.
- [ ] Remove the station picker requirement from FTP creation while retaining edit/delete/test actions.
- [ ] Run the frontend production build.

### Task 5: Verification and deployment

**Files:**
- No additional files.

- [ ] Run the full backend test suite in the backend image with the repository mounted.
- [ ] Run the frontend production build.
- [ ] Rebuild/restart backend, frontend, and worker without deleting existing database volumes.
- [ ] Verify create/list/update/delete API behavior and station-assignment behavior against the live database.

