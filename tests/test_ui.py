from app.domain import Vehicle
from app.ui import vehicle_summary


def test_vehicle_summary_omits_unknown_year():
    text = vehicle_summary(Vehicle("BMW", "X3 G01", 0, None))
    assert "· 0" not in text
    assert "BMW X3 G01" in text


def test_vehicle_summary_masks_vin():
    text = vehicle_summary(Vehicle("BMW", "X3 G01", 2020, "WBA12345678901234"))
    assert "2020" in text
    assert "…1234" in text
    assert "WBA12345678901234" not in text
