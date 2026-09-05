import pytest

from datetime import datetime, timedelta, timezone

from app.repository import can_modify_station, classify_station_status, resolution_source


def test_resolution_source_selects_raw_table_for_one_minute():
    table, bucket_column = resolution_source("1m")

    assert table == "sensor_data"
    assert bucket_column == "time"


def test_resolution_source_selects_hourly_aggregate():
    table, bucket_column = resolution_source("1h")

    assert table == "sensor_data_hourly"
    assert bucket_column == "bucket"


def test_resolution_source_rejects_unknown_resolution():
    with pytest.raises(ValueError, match="Unsupported resolution"):
        resolution_source("15m")


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


def test_classify_station_status_marks_dangerous_pm25_critical():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    status = classify_station_status(
        pm25=180,
        temperature=26,
        humidity=70,
        last_seen_at=now - timedelta(minutes=1),
        now=now,
    )

    assert status == "critical"


def test_classify_station_status_marks_threshold_breach_warning():
    now = datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc)

    status = classify_station_status(
        pm25=45,
        temperature=39,
        humidity=70,
        last_seen_at=now - timedelta(minutes=1),
        now=now,
    )

    assert status == "warning"


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
