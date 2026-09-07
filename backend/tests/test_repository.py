import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.repository import (
    MAX_INTERACTIVE_POINTS_DEFAULT,
    aqi_level,
    can_modify_station,
    choose_effective_resolution,
    classify_station_status,
    downsample_interval_seconds,
    estimated_candidate_points,
    fetch_analytics_heatmap,
    fetch_analytics_scatter,
    fetch_analytics_series,
    fetch_live_stations,
    fetch_station_data,
    metric_column,
    query_meta,
    resolution_source,
    station_data_source,
    station_downsample_source,
    validate_interactive_query_range,
)
from app.schemas import StationDataResponse


def test_resolution_source_selects_raw_table_for_one_minute():
    table, bucket_column = resolution_source("1m")

    assert table == "sensor_data"
    assert bucket_column == "time"


def test_resolution_source_selects_raw_table_for_fifteen_minutes():
    table, bucket_column = resolution_source("15m")

    assert table == "sensor_data"
    assert bucket_column == "time"


def test_resolution_source_selects_hourly_aggregate():
    table, bucket_column = resolution_source("1h")

    assert table == "sensor_data_hourly"
    assert bucket_column == "bucket"


def test_resolution_source_rejects_unknown_resolution():
    with pytest.raises(ValueError, match="Unsupported resolution"):
        resolution_source("5m")


def test_metric_column_rejects_unsafe_metrics():
    assert metric_column("pm25") == "pm25"
    with pytest.raises(ValueError, match="Unsupported metric"):
        metric_column("pm25;drop table")


def test_aqi_level_classifies_pm25_thresholds():
    assert aqi_level(20) == "good"
    assert aqi_level(80) == "moderate"
    assert aqi_level(180) == "unhealthy"


def test_choose_effective_resolution_keeps_one_minute_for_24_hours():
    start = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)

    effective, note = choose_effective_resolution("1m", start, end)

    assert effective == "1m"
    assert note is None


def test_choose_effective_resolution_upgrades_one_minute_after_48_hours():
    start = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=7)

    effective, note = choose_effective_resolution("1m", start, end)

    assert effective == "1h"
    assert note == "Switched from 1m to 1h because the selected range is longer than 48 hours."


def test_choose_effective_resolution_upgrades_one_minute_after_90_days():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=120)

    effective, note = choose_effective_resolution("1m", start, end)

    assert effective == "1d"
    assert note == "Switched from 1m to 1d because the selected range is longer than 90 days."


def test_choose_effective_resolution_upgrades_one_hour_after_90_days():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=120)

    effective, note = choose_effective_resolution("1h", start, end)

    assert effective == "1d"
    assert note == "Switched from 1h to 1d because the selected range is longer than 90 days."


def test_choose_effective_resolution_upgrades_fifteen_minutes_after_90_days():
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    end = start + timedelta(days=120)

    effective, note = choose_effective_resolution("15m", start, end)

    assert effective == "1d"
    assert note == "Switched from 15m to 1d because the selected range is longer than 90 days."


def test_validate_interactive_query_range_rejects_bad_ranges_and_points():
    start = datetime(2026, 9, 5, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="start_time must be before end_time"):
        validate_interactive_query_range(start, start, MAX_INTERACTIVE_POINTS_DEFAULT)

    with pytest.raises(ValueError, match="max_points must be between 100 and 5000"):
        validate_interactive_query_range(start, start + timedelta(hours=1), 99)

    with pytest.raises(ValueError, match="max_points must be between 100 and 5000"):
        validate_interactive_query_range(start, start + timedelta(hours=1), 5001)

    with pytest.raises(ValueError, match="Interactive time range must not exceed 5 years"):
        validate_interactive_query_range(start, start + timedelta(days=365 * 5 + 1), MAX_INTERACTIVE_POINTS_DEFAULT)


def test_downsample_interval_seconds_scales_by_effective_resolution():
    assert estimated_candidate_points(
        datetime(2026, 9, 1, tzinfo=timezone.utc),
        datetime(2026, 9, 2, tzinfo=timezone.utc),
        "1m",
    ) == 1441

    assert downsample_interval_seconds(candidate_points=1441, max_points=1000, resolution="1m") == 120
    assert downsample_interval_seconds(candidate_points=2400, max_points=1000, resolution="1h") == 10800


def test_query_meta_includes_required_fields():
    meta = query_meta("1m", "1h", 1000, 168, False, "Switched from 1m to 1h because the selected range is longer than 48 hours.")

    assert meta == {
        "requested_resolution": "1m",
        "effective_resolution": "1h",
        "max_points": 1000,
        "returned_points": 168,
        "downsampled": False,
        "resolution_note": "Switched from 1m to 1h because the selected range is longer than 48 hours.",
    }


def test_station_data_source_selects_hourly_continuous_aggregate():
    query, bucket_column = station_data_source("1h")

    assert bucket_column == "bucket"
    assert "FROM sensor_data_hourly" in query
    assert "time_bucket('1 hour', time)" not in query
    assert "valid_hours" in query


def test_station_data_source_aggregates_raw_data_into_fifteen_minute_buckets():
    query, bucket_column = station_data_source("15m")

    assert bucket_column == "bucket"
    assert "time_bucket('15 minutes', time)" in query
    assert "avg(temperature) AS temperature" in query


def test_station_data_source_selects_daily_continuous_aggregate():
    query, bucket_column = station_data_source("1d")

    assert bucket_column == "bucket"
    assert "FROM sensor_data_daily" in query
    assert "time_bucket('1 day'" not in query
    assert "valid_hours" in query


def test_schema_daily_continuous_aggregate_defines_valid_hours():
    schema = Path("db/init/001_schema.sql").read_text(encoding="utf-8")

    daily_view = schema.split("CREATE MATERIALIZED VIEW IF NOT EXISTS sensor_data_daily", 1)[1].split(
        "CREATE INDEX IF NOT EXISTS idx_sensor_data_hourly_station_bucket", 1
    )[0]
    assert "count(*) AS samples" in daily_view
    assert "count(DISTINCT time_bucket('1 hour', time)) AS valid_hours" in daily_view


def test_station_data_response_serializes_valid_hours():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    payload = StationDataResponse.model_validate(
        {
            "meta": query_meta("1d", "1d", 1000, 1, False, None),
            "points": [
                {
                    "time": row_time,
                    "temperature": 30.5,
                    "humidity": 72.0,
                    "wind_speed": 2.1,
                    "pm25": 41.2,
                    "samples": 24,
                    "valid_hours": 18,
                }
            ],
        }
    )

    assert payload.model_dump()["points"][0]["valid_hours"] == 18


def test_station_downsample_source_aligns_buckets_to_requested_start_time():
    query, bucket_column = station_downsample_source("1m")

    assert bucket_column == "bucket"
    assert "extract(epoch from time) - extract(epoch from $2::timestamptz)" in query
    assert "+ extract(epoch from $2::timestamptz)" in query


@pytest.mark.parametrize("resolution", ["1h", "1d"])
def test_station_downsample_source_weights_continuous_aggregate_values(resolution):
    query, _bucket_column = station_downsample_source(resolution)

    assert "sum(temperature * samples) / nullif(sum(samples), 0) AS temperature" in query
    assert "sum(humidity * samples) / nullif(sum(samples), 0) AS humidity" in query
    assert "sum(wind_speed * samples) / nullif(sum(samples), 0) AS wind_speed" in query
    assert "sum(pm25 * samples) / nullif(sum(samples), 0) AS pm25" in query


def test_station_downsample_source_supports_fifteen_minute_buckets():
    query, bucket_column = station_downsample_source("15m")

    assert bucket_column == "bucket"
    assert "avg(temperature) AS temperature" in query
    assert "FROM sensor_data" in query


class FakeStationDataConnection:
    def __init__(self, region_id, rows=None, total_points=None):
        self.region_id = region_id
        self.rows = rows or []
        self.total_points = total_points
        self.fetch_calls = []

    async def fetchrow(self, query, *args):
        if "SELECT region_id FROM stations" in query:
            return {"region_id": self.region_id}
        if "count" in query.lower():
            return {"total_points": self.total_points}
        return None

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows


class FakeAnalyticsConnection:
    def __init__(self, rows, region_id=20):
        self.rows = rows
        self.region_id = region_id
        self.fetch_calls = []
        self.fetchrow_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        if "SELECT region_id FROM stations" in query:
            return {"region_id": self.region_id}
        return None

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return self.rows


def test_fetch_station_data_returns_meta_and_points_envelope():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    connection = FakeStationDataConnection(
        region_id=20,
        rows=[
            {
                "time": row_time,
                "temperature": 30.5,
                "humidity": 72.0,
                "wind_speed": 2.1,
                "pm25": 41.2,
                "samples": None,
                "valid_hours": None,
            }
        ],
    )
    user = {"roles": ["super_admin"], "region_ids": []}

    payload = asyncio.run(
        fetch_station_data(
            connection,
            station_id=100,
            start_time=row_time,
            end_time=row_time + timedelta(hours=1),
            resolution="1m",
            user=user,
            max_points=1000,
        )
    )

    assert payload["meta"]["requested_resolution"] == "1m"
    assert payload["meta"]["effective_resolution"] == "1m"
    assert payload["meta"]["returned_points"] == 1
    assert payload["meta"]["downsampled"] is False
    assert payload["points"][0]["time"] == row_time
    assert payload["points"][0]["pm25"] == 41.2


def test_fetch_station_data_downsamples_when_candidate_count_exceeds_max_points():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    connection = FakeStationDataConnection(
        region_id=20,
        rows=[
            {
                "bucket": row_time,
                "temperature": 30.5,
                "humidity": 72.0,
                "wind_speed": 2.1,
                "pm25": 41.2,
                "samples": 2,
                "valid_hours": None,
            }
        ],
    )

    payload = asyncio.run(
        fetch_station_data(
            connection,
            station_id=100,
            start_time=row_time,
            end_time=row_time + timedelta(hours=24),
            resolution="1m",
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=100,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "extract(epoch from time) - extract(epoch from $2::timestamptz)" in query
    assert args[3] == 900
    assert payload["meta"]["downsampled"] is True
    assert payload["meta"]["returned_points"] == 1
    assert payload["meta"]["resolution_note"] == "Returned 100 representative points from 1441 available points."


def test_fetch_station_data_returns_requested_page_and_total_pages():
    row_time = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    connection = FakeStationDataConnection(
        region_id=20,
        total_points=250,
        rows=[
            {
                "bucket": row_time,
                "temperature": 30.5,
                "humidity": 72.0,
                "wind_speed": 2.1,
                "pm25": 41.2,
                "samples": 1,
                "valid_hours": None,
                "total_points": 250,
            }
        ],
    )

    payload = asyncio.run(
        fetch_station_data(
            connection,
            station_id=100,
            start_time=row_time,
            end_time=row_time + timedelta(hours=24),
            resolution="15m",
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=1000,
            page=2,
            page_size=100,
        )
    )

    assert payload["meta"]["page"] == 2
    assert payload["meta"]["page_size"] == 100
    assert payload["meta"]["total_points"] == 250
    assert payload["meta"]["total_pages"] == 3
    assert connection.fetch_calls[0][1][-2:] == (100, 100)


def test_fetch_analytics_series_returns_envelope_and_uses_effective_resolution():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection(
        [
            {
                "time": row_time,
                "station_id": 1,
                "station_code": "AQ-001",
                "station_name": "Station 1",
                "value": 42.0,
            }
        ]
    )

    payload = asyncio.run(
        fetch_analytics_series(
            connection,
            station_ids=[1],
            metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(days=7),
            resolution="1m",
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=1000,
        )
    )

    query, _args = connection.fetch_calls[0]
    assert "FROM sensor_data_hourly data" in query
    assert payload["meta"]["requested_resolution"] == "1m"
    assert payload["meta"]["effective_resolution"] == "1h"
    assert payload["points"][0]["aqi_level"] is not None


@pytest.mark.parametrize("resolution", ["1h", "1d"])
def test_analytics_series_downsampling_weights_continuous_aggregate_values(resolution):
    row_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([])

    asyncio.run(
        fetch_analytics_series(
            connection,
            station_ids=[1],
            metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(days=120),
            resolution=resolution,
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=100,
        )
    )

    query, _args = connection.fetch_calls[0]
    assert "sum(data.pm25 * data.samples) / nullif(sum(data.samples), 0) AS value" in query


def test_analytics_series_rejects_out_of_region_station():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([], region_id=30)

    with pytest.raises(PermissionError, match="outside assigned regions"):
        asyncio.run(
            fetch_analytics_series(
                connection,
                station_ids=[1],
                metric="pm25",
                start_time=row_time,
                end_time=row_time + timedelta(hours=1),
                resolution="1h",
                user={"roles": ["viewer"], "region_ids": [20]},
                max_points=1000,
            )
        )

    assert connection.fetch_calls == []


def test_fetch_analytics_scatter_returns_envelope_and_downsamples_pairs():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([{"time": row_time, "station_id": 1, "x": 30.0, "y": 42.0}])

    payload = asyncio.run(
        fetch_analytics_scatter(
            connection,
            station_id=1,
            x_metric="temperature",
            y_metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(hours=24),
            resolution="1m",
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=100,
        )
    )

    query, args = connection.fetch_calls[0]
    assert "avg(temperature) AS x" in query
    assert "avg(pm25) AS y" in query
    assert args[3] == 900
    assert payload["meta"]["downsampled"] is True
    assert payload["points"][0]["x"] == 30.0
    assert payload["points"][0]["y"] == 42.0


@pytest.mark.parametrize("resolution", ["1h", "1d"])
def test_analytics_scatter_downsampling_weights_continuous_aggregate_values(resolution):
    row_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([])

    asyncio.run(
        fetch_analytics_scatter(
            connection,
            station_id=1,
            x_metric="temperature",
            y_metric="pm25",
            start_time=row_time,
            end_time=row_time + timedelta(days=120),
            resolution=resolution,
            user={"roles": ["super_admin"], "region_ids": []},
            max_points=100,
        )
    )

    query, _args = connection.fetch_calls[0]
    assert "sum(temperature * samples) / nullif(sum(samples), 0) AS x" in query
    assert "sum(pm25 * samples) / nullif(sum(samples), 0) AS y" in query


def test_analytics_scatter_rejects_out_of_region_station():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([], region_id=30)

    with pytest.raises(PermissionError, match="outside assigned regions"):
        asyncio.run(
            fetch_analytics_scatter(
                connection,
                station_id=1,
                x_metric="temperature",
                y_metric="pm25",
                start_time=row_time,
                end_time=row_time + timedelta(hours=1),
                resolution="1h",
                user={"roles": ["viewer"], "region_ids": [20]},
                max_points=1000,
            )
        )

    assert connection.fetch_calls == []


def test_analytics_heatmap_rejects_out_of_region_station():
    row_time = datetime(2026, 9, 1, tzinfo=timezone.utc)
    connection = FakeAnalyticsConnection([], region_id=30)

    with pytest.raises(PermissionError, match="outside assigned regions"):
        asyncio.run(
            fetch_analytics_heatmap(
                connection,
                station_id=1,
                metric="pm25",
                start_time=row_time,
                end_time=row_time + timedelta(hours=1),
                user={"roles": ["viewer"], "region_ids": [20]},
            )
        )

    assert connection.fetch_calls == []


def test_classify_station_status_marks_stale_station_offline():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    status = classify_station_status(
        pm25=10,
        temperature=26,
        humidity=70,
        last_seen_at=now - timedelta(minutes=31),
        now=now,
    )

    assert status == "offline"


def test_classify_station_status_marks_dangerous_pm25_critical_with_qcvn_threshold():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    status = classify_station_status(
        pm25=180,
        temperature=26,
        humidity=70,
        last_seen_at=now - timedelta(minutes=1),
        now=now,
        thresholds={"pm25": {"warning_max": 35.0, "critical_max": 150.0}},
    )

    assert status == "critical"


def test_classify_station_status_marks_threshold_breach_warning_with_qcvn_threshold():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    status = classify_station_status(
        pm25=45,
        temperature=39,
        humidity=70,
        last_seen_at=now - timedelta(minutes=1),
        now=now,
        thresholds={
            "pm25": {"warning_max": 35.0, "critical_max": 150.0},
            "temperature": {"warning_max": 38.0, "critical_max": 42.0},
        },
    )

    assert status == "warning"


def test_classify_station_status_uses_configured_min_and_max_thresholds():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)
    thresholds = {
        "pm25": {"warning_max": 100.0, "critical_max": 120.0},
        "temperature": {"warning_min": 5.0, "critical_min": 0.0},
    }

    assert (
        classify_station_status(
            pm25=80,
            temperature=20,
            humidity=70,
            last_seen_at=now - timedelta(minutes=1),
            now=now,
            thresholds=thresholds,
        )
        == "online"
    )
    assert (
        classify_station_status(
            pm25=80,
            temperature=-1,
            humidity=70,
            last_seen_at=now - timedelta(minutes=1),
            now=now,
            thresholds=thresholds,
        )
        == "critical"
    )


class FakeLiveStationsConnection:
    def __init__(self, station_rows, config_rows):
        self.station_rows = station_rows
        self.config_rows = config_rows
        self.fetch_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        if "FROM alert_configs" in query:
            return self.config_rows
        return self.station_rows


def test_fetch_live_stations_uses_only_station_qcvn_config():
    now = datetime.now(timezone.utc)
    connection = FakeLiveStationsConnection(
        station_rows=[
            {
                "id": 1,
                "code": "A",
                "name": "Station A",
                "latitude": 10.0,
                "longitude": 106.0,
                "address": "A",
                "station_status": "active",
                "metadata": {},
                "region_id": 10,
                "last_seen_at": now - timedelta(minutes=1),
                "time": now - timedelta(minutes=1),
                "temperature": 25.0,
                "humidity": 70.0,
                "wind_speed": 2.0,
                "pm25": 80.0,
            },
            {
                "id": 2,
                "code": "B",
                "name": "Station B",
                "latitude": 10.0,
                "longitude": 106.0,
                "address": "B",
                "station_status": "active",
                "metadata": {},
                "region_id": 10,
                "last_seen_at": now - timedelta(minutes=1),
                "time": now - timedelta(minutes=1),
                "temperature": 25.0,
                "humidity": 70.0,
                "wind_speed": 2.0,
                "pm25": 70.0,
            },
        ],
        config_rows=[
            {
                "station_id": None,
                "region_id": 10,
                "metric": "pm25",
                "warning_min": None,
                "warning_max": 60.0,
                "critical_min": None,
                "critical_max": 100.0,
            },
            {
                "station_id": 1,
                "region_id": None,
                "metric": "pm25",
                "warning_min": None,
                "warning_max": 100.0,
                "critical_min": None,
                "critical_max": 120.0,
            },
        ],
    )

    stations = asyncio.run(fetch_live_stations(connection, {"roles": ["super_admin"], "region_ids": []}))

    assert [query for query, _args in connection.fetch_calls if "FROM alert_configs" in query]
    assert stations[0]["live_status"] == "online"
    assert stations[0]["qcvn_thresholds"]["pm25"]["warning_max"] == 100.0
    assert stations[1]["live_status"] == "online"
    assert stations[1]["qcvn_thresholds"] == {}


def test_fetch_live_stations_applies_one_qcvn_to_multiple_assigned_stations():
    now = datetime.now(timezone.utc)
    connection = FakeLiveStationsConnection(
        station_rows=[
            {"id": 1, "code": "A", "name": "Station A", "latitude": 10.0, "longitude": 106.0, "address": "A", "station_status": "active", "metadata": {}, "region_id": 10, "last_seen_at": now, "time": now, "temperature": 25.0, "humidity": 70.0, "wind_speed": 2.0, "pm25": 80.0},
            {"id": 2, "code": "B", "name": "Station B", "latitude": 10.0, "longitude": 106.0, "address": "B", "station_status": "active", "metadata": {}, "region_id": 10, "last_seen_at": now, "time": now, "temperature": 25.0, "humidity": 70.0, "wind_speed": 2.0, "pm25": 80.0},
        ],
        config_rows=[
            {"station_id": 1, "region_id": None, "metric": "pm25", "warning_min": None, "warning_max": 35.0, "critical_min": None, "critical_max": 150.0},
            {"station_id": 2, "region_id": None, "metric": "pm25", "warning_min": None, "warning_max": 35.0, "critical_min": None, "critical_max": 150.0},
        ],
    )

    stations = asyncio.run(fetch_live_stations(connection, {"roles": ["super_admin"], "region_ids": []}))

    assert stations[0]["qcvn_thresholds"]["pm25"]["warning_max"] == 35.0
    assert stations[1]["qcvn_thresholds"]["pm25"]["warning_max"] == 35.0


def test_fetch_live_stations_does_not_alert_unconfigured_station():
    now = datetime.now(timezone.utc)
    connection = FakeLiveStationsConnection(
        station_rows=[
            {
                "id": 3,
                "code": "C",
                "name": "Station C",
                "latitude": 10.0,
                "longitude": 106.0,
                "address": "C",
                "station_status": "active",
                "metadata": {},
                "region_id": 99,
                "last_seen_at": now - timedelta(minutes=1),
                "time": now - timedelta(minutes=1),
                "temperature": 45.0,
                "humidity": 99.0,
                "wind_speed": 2.0,
                "pm25": 180.0,
            },
        ],
        config_rows=[],
    )

    stations = asyncio.run(fetch_live_stations(connection, {"roles": ["super_admin"], "region_ids": []}))

    assert stations[0]["live_status"] == "online"
    assert stations[0]["qcvn_thresholds"] == {}


def test_manager_can_modify_station_only_inside_assigned_region():
    manager = {"roles": ["manager"], "region_ids": [10, 11]}

    assert can_modify_station(manager, station_region_id=10) is True
    assert can_modify_station(manager, station_region_id=12) is False


def test_viewer_cannot_modify_station_even_inside_assigned_region():
    viewer = {"roles": ["viewer"], "region_ids": [10]}

    assert can_modify_station(viewer, station_region_id=10) is False


def test_super_admin_can_modify_any_station():
    admin = {"roles": ["super_admin"], "region_ids": []}

    assert can_modify_station(admin, station_region_id=999) is True
