from app.domain import Vehicle
from app.external_vehicle import (
    GenericHttpVehicleResolver,
    HttpVehicleResolverConfig,
    parse_vehicle_payload,
)
from app.vehicle_resolution import VehicleResolution, merge_vehicle_resolution


def test_parse_resolved_vehicle_payload():
    result = parse_vehicle_payload(
        {
            "status": "resolved",
            "brand": "BMW",
            "model": "X3 G01",
            "year": 2020,
            "generation_code": "G01",
            "engine": "B47D20",
            "fuel": "diesel",
            "drive": "xDrive",
            "power_hp": 190,
            "modification_key": "bmw_x3_g01_20d_xdrive",
            "source": "partner-catalog",
        },
        "WBA00000000000000",
    )
    assert result.resolved
    assert result.vehicle is not None
    assert result.vehicle.engine == "B47D20"
    assert result.vehicle.power_hp == 190


def test_invalid_payload_is_not_resolved():
    result = parse_vehicle_payload({"brand": "BMW"}, "WBA00000000000000")
    assert not result.resolved


def test_merge_resolution_keeps_database_id_and_vin():
    saved = Vehicle("BMW", "X3", 2020, vin="WBA00000000000000", id=7)
    resolved = Vehicle(
        "BMW",
        "X3 G01",
        2020,
        generation_code="G01",
        engine="B47D20",
        modification_key="key",
    )
    merged = merge_vehicle_resolution(
        saved,
        VehicleResolution(status="resolved", vehicle=resolved, source="api"),
    )
    assert merged.id == 7
    assert merged.vin == "WBA00000000000000"
    assert merged.engine == "B47D20"


def test_vehicle_resolver_requires_https():
    import pytest

    with pytest.raises(ValueError):
        GenericHttpVehicleResolver(
            HttpVehicleResolverConfig(base_url="http://example.test")
        )
