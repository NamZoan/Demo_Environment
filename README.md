# Environment Monitoring Stack

Dockerized reference stack for 2,000 environmental monitoring stations sending 1-minute data through FTP.

## Services

- TimescaleDB on `localhost:5432`
- FastAPI backend on `http://localhost:8000`
- FTP server on `localhost:21`
- FTP worker polling uploaded CSV/JSON files
- IoT simulators publishing two sensor CSV files per FTP every 15 minutes
- React dashboard on `http://localhost:3000`

## Run

```bash
docker compose up --build
```

Open:

```text
http://localhost:3000
```

API health:

```bash
curl http://localhost:8000/health
```

## Database

The schema is initialized from:

```text
db/init/001_schema.sql
```

It creates:

- `users`
- `stations`
- `sensor_data` as a TimescaleDB hypertable
- `sensor_data_hourly` continuous aggregate
- `sensor_data_daily` continuous aggregate
- automatic refresh policies for hourly and daily aggregates

Default internal login for local development:

```text
username: admin
password: admin@123
```

The password is seeded through PostgreSQL `pgcrypto` with `crypt(..., gen_salt('bf'))`; change it before production use.

## FTP Input Format

FTP credentials for local development:

```text
user: station
password: stationpass
```

Legacy CSV:

```csv
station_code,time,temperature,humidity,pm25
HN001,2026-09-05T00:01:00Z,30.5,70.2,18.4
```

IoT simulator CSV:

```csv
sensor_id,timestamp,temperature,humidity,wind_speed,pm25
sensor_001,2026-09-05T08:00:00+00:00,31.2,68.5,12.4,42.8
```

JSON:

```json
[
  {
    "station_code": "HN001",
    "time": "2026-09-05T00:01:00Z",
    "temperature": 30.5,
    "humidity": 70.2,
    "wind_speed": 12.4,
    "pm25": 18.4
  }
]
```

Inside the worker container, files move through:

```text
/ftp/data -> /ftp/archive
/ftp/data -> /ftp/error
```

The simulator uploads each file into `/data/sensor_001/` through `/data/sensor_100/`.
The worker scans those folders recursively, creates missing `sensor_###` stations, writes `sensor_data`, and updates `latest_station_readings`.

## API

List stations:

```bash
curl http://localhost:8000/api/stations
```

Fetch station data:

```bash
curl "http://localhost:8000/api/stations/1/data?start_time=2026-09-05T00:00:00Z&end_time=2026-09-06T00:00:00Z&resolution=1h"
```

Supported resolutions:

- `1m`: raw 1-minute data from `sensor_data`
- `1h`: hourly averages from `sensor_data_hourly`
- `1d`: daily averages from `sensor_data_daily`

## Production Notes

At 2,000 station files per minute, FTP-based ingestion can become disk I/O bound. For a production FTP deployment, mount the incoming directory on RAM disk and archive asynchronously to durable storage. As the platform grows, move telemetry ingestion to MQTT plus a message queue so writes are streamed and backpressure can be controlled.
