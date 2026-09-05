import pytest

from app.repository import resolution_source


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

