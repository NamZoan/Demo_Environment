# Environment Monitoring Web System Design

## Goal

Build a local Docker stack for an environmental monitoring web system handling 2,000 outdoor stations that upload 1-minute sensor readings through FTP, around 2.88 million rows per day.

## Architecture

The stack contains TimescaleDB, a FastAPI backend, an FTP server, a Python FTP worker, and a React dashboard. Stations upload CSV or JSON files to the FTP server. The worker polls the incoming folder, parses files, bulk inserts records into TimescaleDB, then moves files to archive or error folders. The API reads raw 1-minute data or TimescaleDB continuous aggregate views for hourly and daily resolutions.

## Data Model

`stations` stores station identity, location, status, and metadata. `sensor_data` stores `time`, `station_id`, `temperature`, `humidity`, and `pm25`, with a primary key on `(station_id, time)` and a hypertable partitioned by `time`. Continuous aggregates compute 1-hour and 1-day averages.

## Backend API

FastAPI exposes:

- `GET /health`
- `GET /api/stations`
- `GET /api/stations/{station_id}/data?start_time=&end_time=&resolution=1m|1h|1d`

The data endpoint validates the requested resolution and selects the raw table or aggregate view. Query parameters use ISO timestamps.

## FTP Worker

The worker supports:

- CSV files with columns: `station_code,time,temperature,humidity,pm25`
- JSON files as either a single object or an array of objects with the same keys
- bulk insert using PostgreSQL `COPY`
- idempotent upsert semantics through a temporary table plus `ON CONFLICT (station_id, time) DO UPDATE`

Files are moved from `/ftp/incoming` to `/ftp/archive` after success and `/ftp/error` after failure.

## Frontend

React + Vite renders a dashboard with station selector, time inputs, resolution selector, metric toggles, and a Recharts line chart for temperature, humidity, and PM2.5.

## Operational Notes

FTP file ingestion can become disk I/O bound when 2,000 files arrive every minute. Production deployments should mount the FTP incoming folder on RAM disk or migrate ingestion to MQTT plus a message queue when the system grows.

