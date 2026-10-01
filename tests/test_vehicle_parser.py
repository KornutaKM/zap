from app.vehicle_parser import parse_vehicle_text


def test_single_word_brand():
    assert parse_vehicle_text("BMW X3 G01") == ("BMW", "X3 G01")


def test_multiword_brand():
    assert parse_vehicle_text("Land Rover Discovery 5") == ("Land Rover", "Discovery 5")


def test_unknown_phrase_is_not_vehicle():
    assert parse_vehicle_text("передние тормозные колодки") is None


def test_brand_requires_model():
    assert parse_vehicle_text("BMW") is None
