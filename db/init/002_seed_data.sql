INSERT INTO regions (code, name)
SELECT code, name
FROM (
    VALUES
        ('VN-DN', 'Da Nang'),
        ('VN-CT', 'Can Tho'),
        ('VN-HP', 'Hai Phong')
) AS items(code, name)
ON CONFLICT (code) DO NOTHING;

INSERT INTO stations (code, name, latitude, longitude, address, status, region_id, metadata, last_seen_at)
SELECT
    'ENV-' || lpad(series::text, 4, '0') AS code,
    'Tram quan trac ' || regions.name || ' ' || lpad(series::text, 4, '0') AS name,
    round((8.6 + mod(series * 37, 1450)::numeric / 100)::numeric, 5)::double precision AS latitude,
    round((102.2 + mod(series * 29, 780)::numeric / 100)::numeric, 5)::double precision AS longitude,
    regions.name AS address,
    CASE
        WHEN mod(series, 23) = 0 THEN 'maintenance'
        WHEN mod(series, 17) = 0 THEN 'offline'
        ELSE 'active'
    END AS status,
    regions.id AS region_id,
    jsonb_build_object(
        'type',
        CASE mod(series, 4)
            WHEN 0 THEN 'Không khí xung quanh'
            WHEN 1 THEN 'Nước mặt'
            WHEN 2 THEN 'Nước thải'
            ELSE 'Khí thải'
        END,
        'datalogger',
        'DL-' || lpad((mod(series, 800) + 1)::text, 3, '0')
    ) AS metadata,
    now() - make_interval(mins => mod(series, 80)) AS last_seen_at
FROM generate_series(1, 2000) AS series
JOIN LATERAL (
    SELECT id, name
    FROM regions
    ORDER BY id
    OFFSET mod(series, (SELECT count(*) FROM regions))
    LIMIT 1
) regions ON TRUE
ON CONFLICT (code) DO UPDATE SET
    name = EXCLUDED.name,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    address = EXCLUDED.address,
    status = EXCLUDED.status,
    region_id = EXCLUDED.region_id,
    metadata = EXCLUDED.metadata,
    last_seen_at = EXCLUDED.last_seen_at,
    updated_at = now();

INSERT INTO sensor_data (station_id, time, temperature, humidity, pm25)
SELECT
    stations.id,
    now() - make_interval(hours => points.step),
    round((24 + mod(stations.id, 16) + sin(points.step / 3.0) * 2)::numeric, 2)::double precision,
    round((52 + mod(stations.id + points.step, 42))::numeric, 2)::double precision,
    round((12 + mod(stations.id + points.step, 95))::numeric, 2)::double precision
FROM stations
CROSS JOIN generate_series(0, 23) AS points(step)
WHERE stations.code LIKE 'ENV-%'
ON CONFLICT (station_id, time) DO UPDATE SET
    temperature = EXCLUDED.temperature,
    humidity = EXCLUDED.humidity,
    pm25 = EXCLUDED.pm25,
    received_at = now();

INSERT INTO latest_station_readings (station_id, time, temperature, humidity, pm25, status)
SELECT DISTINCT ON (sensor_data.station_id)
    sensor_data.station_id,
    sensor_data.time,
    sensor_data.temperature,
    sensor_data.humidity,
    sensor_data.pm25,
    'online'
FROM sensor_data
JOIN stations ON stations.id = sensor_data.station_id
WHERE stations.code LIKE 'ENV-%'
ORDER BY sensor_data.station_id, sensor_data.time DESC
ON CONFLICT (station_id) DO UPDATE SET
    time = EXCLUDED.time,
    temperature = EXCLUDED.temperature,
    humidity = EXCLUDED.humidity,
    pm25 = EXCLUDED.pm25,
    status = EXCLUDED.status,
    updated_at = now();

CALL refresh_continuous_aggregate('sensor_data_hourly', now() - INTERVAL '2 days', now());
CALL refresh_continuous_aggregate('sensor_data_daily', now() - INTERVAL '7 days', now());
