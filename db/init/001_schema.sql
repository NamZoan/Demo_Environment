CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT NOT NULL DEFAULT 'operator',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS stations (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    address TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pm25 DOUBLE PRECISION,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (station_id, time)
);

SELECT create_hypertable(
    'sensor_data',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_sensor_data_time ON sensor_data (time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_station_time ON sensor_data (station_id, time DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    station_id,
    avg(temperature) AS temperature,
    avg(humidity) AS humidity,
    avg(pm25) AS pm25,
    count(*) AS samples
FROM sensor_data
GROUP BY bucket, station_id
WITH NO DATA;

CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    station_id,
    avg(temperature) AS temperature,
    avg(humidity) AS humidity,
    avg(pm25) AS pm25,
    count(*) AS samples
FROM sensor_data
GROUP BY bucket, station_id
WITH NO DATA;

CREATE INDEX IF NOT EXISTS idx_sensor_data_hourly_station_bucket
    ON sensor_data_hourly (station_id, bucket DESC);

CREATE INDEX IF NOT EXISTS idx_sensor_data_daily_station_bucket
    ON sensor_data_daily (station_id, bucket DESC);

SELECT add_continuous_aggregate_policy(
    'sensor_data_hourly',
    start_offset => INTERVAL '3 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '15 minutes',
    if_not_exists => TRUE
);

SELECT add_continuous_aggregate_policy(
    'sensor_data_daily',
    start_offset => INTERVAL '90 days',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);

INSERT INTO stations (code, name, latitude, longitude, address)
VALUES
    ('HN001', 'Ha Noi Urban Station 001', 21.0278, 105.8342, 'Ha Noi'),
    ('HCM001', 'Ho Chi Minh Urban Station 001', 10.8231, 106.6297, 'Ho Chi Minh City')
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (username, password_hash, full_name, role, status)
VALUES ('admin', crypt('admin@123', gen_salt('bf')), 'System Administrator', 'admin', 'active')
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    status = EXCLUDED.status,
    updated_at = now();
