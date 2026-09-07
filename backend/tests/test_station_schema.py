import pytest
from pydantic import ValidationError

from app.schemas import StationCreate, StationUpdate


def test_station_create_accepts_valid_coordinates():
    station = StationCreate(code="HN-001", name="Ha Noi", latitude=21.0278, longitude=105.8342)

    assert station.latitude == 21.0278
    assert station.longitude == 105.8342


@pytest.mark.parametrize(
    ("field", "value"),
    [("latitude", 91), ("latitude", -91), ("longitude", 181), ("longitude", -181)],
)
def test_station_create_rejects_coordinates_outside_earth(field, value):
    with pytest.raises(ValidationError):
        StationCreate(code="HN-001", name="Ha Noi", **{field: value})


def test_station_update_applies_the_same_coordinate_bounds():
    with pytest.raises(ValidationError):
        StationUpdate(latitude=90.1)
    with pytest.raises(ValidationError):
        StationUpdate(longitude=-180.1)
