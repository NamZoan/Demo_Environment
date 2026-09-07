# IoT FTP Sensor Simulator

This module simulates outdoor environmental sensors. Each sensor creates one CSV file every 15 minutes and uploads it to its own FTP directory.

## Data Format

Each uploaded file contains one row with these columns:

```csv
sensor_id,timestamp,temperature,humidity,wind_speed,pm25
sensor_001,2026-09-05T10:30:00+00:00,31.2,72.5,12.4,34.8
```

Value ranges:

- `sensor_id`: `sensor_001` to `sensor_100`
- `timestamp`: ISO 8601 UTC timestamp
- `temperature`: `15.0` to `45.0`
- `humidity`: `30.0` to `95.0`
- `wind_speed`: `0.0` to `50.0`
- `pm25`: `5.0` to `150.0`

## Run With Docker Compose

```bash
cd iot-simulator
docker compose up --build
```

Services:

- `ftp-server`: FTP receiver using `fauria/vsftpd`
- `sensor-simulator`: one Python process running 100 async sensor loops

FTP credentials:

```text
host: localhost
port: 2121
user: station
password: stationpass
```

Inside Docker, uploaded files are stored under:

```text
/home/vsftpd/station/data/sensor_001/
/home/vsftpd/station/data/sensor_002/
...
/home/vsftpd/station/data/sensor_100/
```

Check logs:

```bash
docker compose logs -f sensor-simulator
docker compose logs -f ftp-server
```

Stop:

```bash
docker compose down
```

Delete uploaded FTP data:

```bash
docker compose down -v
```

## Run Python Simulator Against An Existing FTP Server

```bash
cd iot-simulator
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

FTP_HOST=localhost \
FTP_PORT=21 \
FTP_USER=station \
FTP_PASSWORD=stationpass \
REMOTE_BASE_DIR=/data \
SENSOR_COUNT=100 \
INTERVAL_SECONDS=900 \
python app/simulator.py
```

## Configuration

Environment variables:

```text
SENSOR_COUNT=100
INTERVAL_SECONDS=900
FTP_HOST=ftp-server
FTP_PORT=21
FTP_USER=station
FTP_PASSWORD=stationpass
REMOTE_BASE_DIR=/data
LOCAL_OUTBOX_DIR=/tmp/iot-outbox
UPLOAD_RETRIES=3
RETRY_BACKOFF_SECONDS=3
FTP_PASSIVE_MODE=true
LOG_LEVEL=INFO
```

## Error Handling

If FTP upload fails, the simulator:

1. Logs the sensor ID, filename, attempt number, and error.
2. Retries up to `UPLOAD_RETRIES`.
3. Keeps the local CSV file if all retries fail.
4. Tries again in the next 60-second cycle.
5. Deletes the local CSV only after successful upload.
