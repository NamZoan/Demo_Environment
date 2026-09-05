# Environment Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Dockerized environmental monitoring stack with TimescaleDB schema, FastAPI APIs, FTP ingestion worker, RBAC station management, WebSocket live data, GIS map, and React chart dashboard.

**Architecture:** TimescaleDB stores raw 1-minute sensor data, continuous aggregates, RBAC metadata, alert thresholds, audit logs, and latest station snapshots. FastAPI exposes station CRUD, overview, live, time-series, auth, and WebSocket endpoints. A Python worker ingests FTP-uploaded CSV/JSON files with bulk insert and updates latest snapshots. React renders KPI counts, a Leaflet map, live station table, and Recharts line charts.

**Tech Stack:** PostgreSQL + TimescaleDB, Python 3.12, FastAPI, asyncpg, psycopg, pytest, React, Vite, Recharts, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-09-05-environment-monitoring-design.md`

## Global Constraints

- Support 2,000 outdoor stations.
- Handle around 2.88 million 1-minute sensor rows per day.
- Ingest CSV and JSON files uploaded through FTP.
- Use bulk insert for sensor ingestion.
- Enforce station write access with `super_admin`, `manager`, and `viewer` roles.
- Scope manager/viewer access by assigned `regions`.
- Stream live station snapshots over `/ws/live`.
- Expose API resolution options `1m`, `1h`, and `1d`.
- Keep production note for RAM disk or future MQTT plus queue migration.

---

### Task 1: Database Schema

**Files:**
- Create: `db/init/001_schema.sql`

**Interfaces:**
- Produces: `roles`, `regions`, `user_roles`, `user_regions`, `stations`, `sensor_data`, `latest_station_readings`, `alert_configs`, `audit_logs`, `sensor_data_hourly`, `sensor_data_daily`

- [ ] Create TimescaleDB extension, RBAC tables, station tables, latest-reading table, alert/audit tables, hypertable, indexes, continuous aggregates, and refresh policies.
- [ ] Verify SQL uses `IF NOT EXISTS` where supported and stable aggregate refresh windows.

### Task 2: Backend API

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/db.py`
- Create: `backend/app/main.py`
- Create: `backend/app/repository.py`
- Create: `backend/app/schemas.py`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Test: `backend/tests/test_repository.py`

**Interfaces:**
- Produces: `resolution_source(resolution: str) -> tuple[str, str]`
- Produces: REST endpoints `/health`, `/api/stations`, `/api/stations/live`, `/api/overview`, `/api/stations/{station_id}/data`
- Produces: WebSocket endpoint `/ws/live`

- [ ] Write repository tests for resolution-to-source mapping.
- [ ] Run pytest and confirm the tests fail before implementation.
- [ ] Implement API code and repository query selection.
- [ ] Implement station CRUD and RBAC helper functions.
- [ ] Implement live station status classification.
- [ ] Implement WebSocket polling stream for live station snapshots.
- [ ] Run pytest and confirm tests pass.

### Task 3: FTP Worker

**Files:**
- Create: `worker/app/parser.py`
- Create: `worker/app/worker.py`
- Create: `worker/app/db.py`
- Create: `worker/requirements.txt`
- Create: `worker/Dockerfile`
- Test: `worker/tests/test_parser.py`

**Interfaces:**
- Produces: `parse_sensor_file(path: Path) -> list[SensorReading]`
- Consumes: database tables from Task 1

- [ ] Write parser tests for CSV and JSON formats.
- [ ] Run pytest and confirm parser tests fail before implementation.
- [ ] Implement parser and bulk insert worker.
- [ ] Update `latest_station_readings` and `stations.last_seen_at` after ingest.
- [ ] Run pytest and confirm parser tests pass.

### Task 4: Frontend Dashboard

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/src/api.js`
- Create: `frontend/src/EnvironmentChart.jsx`
- Create: `frontend/src/styles.css`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

**Interfaces:**
- Consumes: backend REST API
- Produces: dashboard UI with KPI counts, Leaflet map, live station table, station list, time filters, resolution selector, metric toggles, and Recharts line chart

- [ ] Implement frontend API client and dashboard components.
- [ ] Add Leaflet/react-leaflet dependencies and marker color states.
- [ ] Connect WebSocket live feed with REST/demo fallback.
- [ ] Build frontend in Docker or with local npm when dependencies are available.

### Task 5: Stack Wiring and Documentation

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `README.md`

**Interfaces:**
- Consumes: DB, backend, worker, frontend, FTP server images
- Produces: local setup instructions

- [ ] Wire TimescaleDB, backend, FTP server, worker, and frontend services.
- [ ] Use frontend nginx as the basic API gateway for `/api`, `/health`, and `/ws`.
- [ ] Document setup commands, FTP upload path, sample CSV/JSON, and scaling notes.
- [ ] Run syntax/test checks available in the environment.
