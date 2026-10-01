from app.domain import Vehicle
from app.vehicle_resolver import (
    apply_modification,
    find_modifications,
    get_modification,
    vehicle_is_precise,
)


def test_bmw_x3_2020_has_multiple_modifications():
    vehicle = Vehicle("BMW", "X3 G01", 2020)
    result = find_modifications(vehicle)
    assert len(result) >= 3
    assert {item.generation_code for item in result} == {"G01"}


def test_apply_modification_marks_vehicle_precise():
    vehicle = Vehicle("BMW", "X3 G01", 2020, id=10)
    mod = get_modification("bmw_x3_g01_20d_xdrive")
    assert mod is not None

    updated = apply_modification(vehicle, mod)
    assert updated.id == 10
    assert updated.engine == "B47D20"
    assert updated.drive == "xDrive"
    assert vehicle_is_precise(updated)


def test_unknown_vehicle_has_no_demo_modifications():
    assert find_modifications(Vehicle("Volvo", "XC90", 2020)) == []
