CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS roles (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS regions (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    parent_id BIGINT REFERENCES regions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

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

CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id BIGINT NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS user_regions (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    region_id BIGINT NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, region_id)
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

CREATE TABLE IF NOT EXISTS station_ftp_configs (
    station_id BIGINT PRIMARY KEY REFERENCES stations(id) ON DELETE CASCADE,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 21 CHECK (port BETWEEN 1 AND 65535),
    username TEXT NOT NULL,
    password_encrypted BYTEA NOT NULL,
    root_path TEXT NOT NULL DEFAULT '/data',
    timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ftp_files (
    id BIGSERIAL PRIMARY KEY,
    station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    remote_path TEXT NOT NULL,
    name TEXT NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('file', 'folder')),
    size_bytes BIGINT,
    modified_at TEXT,
    status TEXT NOT NULL DEFAULT 'discovered',
    error TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (station_id, remote_path)
);

ALTER TABLE stations ADD COLUMN IF NOT EXISTS region_id BIGINT REFERENCES regions(id) ON DELETE SET NULL;
ALTER TABLE stations ADD COLUMN IF NOT EXISTS last_seen_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS ftp_servers (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL DEFAULT 21 CHECK (port BETWEEN 1 AND 65535),
    username TEXT NOT NULL,
    password_encrypted BYTEA NOT NULL,
    root_path TEXT NOT NULL DEFAULT '/data',
    timeout_seconds INTEGER NOT NULL DEFAULT 5 CHECK (timeout_seconds BETWEEN 1 AND 120),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    legacy_station_id BIGINT UNIQUE REFERENCES stations(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS station_ftp_assignments (
    station_id BIGINT PRIMARY KEY REFERENCES stations(id) ON DELETE CASCADE,
    ftp_server_id BIGINT NOT NULL REFERENCES ftp_servers(id) ON DELETE CASCADE,
    root_path TEXT NOT NULL DEFAULT '/data',
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_station_ftp_assignments_server ON station_ftp_assignments (ftp_server_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_station_ftp_assignment_folder ON station_ftp_assignments (ftp_server_id, root_path) WHERE root_path <> '/data';

INSERT INTO ftp_servers (name, host, port, username, password_encrypted, root_path, timeout_seconds, legacy_station_id)
SELECT COALESCE(s.code, 'FTP station ' || c.station_id::text), c.host, c.port, c.username,
       c.password_encrypted, c.root_path, c.timeout_seconds, c.station_id
FROM station_ftp_configs c
LEFT JOIN stations s ON s.id = c.station_id
ON CONFLICT (legacy_station_id) DO NOTHING;

INSERT INTO station_ftp_assignments (station_id, ftp_server_id, root_path)
SELECT c.station_id, f.id, c.root_path
FROM station_ftp_configs c
JOIN ftp_servers f ON f.legacy_station_id = c.station_id
ON CONFLICT (station_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS sensor_data (
    time TIMESTAMPTZ NOT NULL,
    station_id BIGINT NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    pm25 DOUBLE PRECISION,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (station_id, time)
);

CREATE TABLE IF NOT EXISTS latest_station_readings (
    station_id BIGINT PRIMARY KEY REFERENCES stations(id) ON DELETE CASCADE,
    time TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    pm25 DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'online',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alert_configs (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT REFERENCES regions(id) ON DELETE CASCADE,
    station_id BIGINT REFERENCES stations(id) ON DELETE CASCADE,
    metric TEXT NOT NULL CHECK (metric IN ('pm25', 'temperature', 'humidity')),
    warning_min DOUBLE PRECISION,
    warning_max DOUBLE PRECISION,
    critical_min DOUBLE PRECISION,
    critical_max DOUBLE PRECISION,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by BIGINT REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (region_id IS NOT NULL OR station_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id BIGINT,
    before_data JSONB,
    after_data JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

SELECT create_hypertable(
    'sensor_data',
    'time',
    if_not_exists => TRUE,
    chunk_time_interval => INTERVAL '1 day'
);

CREATE INDEX IF NOT EXISTS idx_sensor_data_time ON sensor_data (time DESC);
CREATE INDEX IF NOT EXISTS idx_sensor_data_station_time ON sensor_data (station_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_stations_region ON stations (region_id);
CREATE INDEX IF NOT EXISTS idx_stations_last_seen ON stations (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_ftp_files_station_seen ON ftp_files (station_id, last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_configs_station ON alert_configs (station_id) WHERE station_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_alert_configs_region ON alert_configs (region_id) WHERE region_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_audit_logs_entity ON audit_logs (entity_type, entity_id, created_at DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    station_id,
    avg(temperature) AS temperature,
    avg(humidity) AS humidity,
    avg(wind_speed) AS wind_speed,
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
    avg(wind_speed) AS wind_speed,
    avg(pm25) AS pm25,
    count(*) AS samples,
    count(DISTINCT time_bucket('1 hour', time)) AS valid_hours
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

INSERT INTO roles (code, name, description)
VALUES
    ('super_admin', 'Super Admin', 'Full platform administration'),
    ('manager', 'Manager', 'Manage stations in assigned regions'),
    ('viewer', 'Viewer', 'Read-only access to assigned regions')
ON CONFLICT (code) DO NOTHING;

INSERT INTO regions (code, name)
VALUES
    ('VN-HN', 'Ha Noi'),
    ('VN-HCM', 'Ho Chi Minh City')
ON CONFLICT (code) DO NOTHING;

INSERT INTO stations (code, name, latitude, longitude, address, region_id)
VALUES
    ('HN001', 'Ha Noi Urban Station 001', 21.0278, 105.8342, 'Ha Noi', (SELECT id FROM regions WHERE code = 'VN-HN')),
    ('HCM001', 'Ho Chi Minh Urban Station 001', 10.8231, 106.6297, 'Ho Chi Minh City', (SELECT id FROM regions WHERE code = 'VN-HCM'))
ON CONFLICT (code) DO NOTHING;

INSERT INTO users (username, password_hash, full_name, role, status)
VALUES ('admin', crypt('admin@123', gen_salt('bf')), 'System Administrator', 'admin', 'active')
ON CONFLICT (username) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    full_name = EXCLUDED.full_name,
    role = EXCLUDED.role,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.code = 'super_admin'
WHERE u.username = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO user_regions (user_id, region_id)
SELECT u.id, rg.id
FROM users u
CROSS JOIN regions rg
WHERE u.username = 'admin'
ON CONFLICT DO NOTHING;

INSERT INTO alert_configs (region_id, metric, warning_max, critical_max, created_by)
SELECT rg.id, metric, warning_max, critical_max, u.id
FROM regions rg
CROSS JOIN users u
CROSS JOIN (
    VALUES
        ('pm25', 35.0, 150.0),
        ('temperature', 38.0, 42.0),
        ('humidity', 85.0, 95.0)
) AS thresholds(metric, warning_max, critical_max)
WHERE u.username = 'admin'
ON CONFLICT DO NOTHING;
