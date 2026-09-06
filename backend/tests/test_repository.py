import pytest

from datetime import datetime, timedelta, timezone

from app.repository import (
    MAX_INTERACTIVE_POINTS_DEFAULT,
    can_modify_station,
    choose_effective_resolution,
    classify_station_status,
    query_meta,
    resolution_source,
    validate_interactive_query_range,
)


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
