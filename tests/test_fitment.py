import asyncio

from app.domain import Vehicle
from app.fitment import DemoFitmentCatalog


def test_precise_vehicle_confirms_fitment():
    catalog = DemoFitmentCatalog()
    vehicle = Vehicle(
        "BMW",
        "X3 G01",
        2020,
        generation_code="G01",
        engine="B47D20",
        fuel="дизель",
        drive="xDrive",
        power_hp=190,
        modification_key="bmw_x3_g01_20d_xdrive",
    )
    result = asyncio.run(catalog.resolve(vehicle, "масляный фильтр"))
    assert result.status == "confirmed"
    assert result.oe_numbers
    assert any(item.article == "HU816X" for item in result.crosses)


def test_unresolved_modification_is_probable():
    catalog = DemoFitmentCatalog()
    vehicle = Vehicle("BMW", "X3 G01", 2020, generation_code="G01")
    result = asyncio.run(catalog.resolve(vehicle, "передние колодки"))
    assert result.status == "probable"


def test_missing_vehicle_is_unverified():
    catalog = DemoFitmentCatalog()
    result = asyncio.run(catalog.resolve(None, "масляный фильтр"))
    assert result.status == "unverified"
