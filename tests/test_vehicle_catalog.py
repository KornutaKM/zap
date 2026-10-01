from app.vehicle_catalog import find_generations, get_generation


def test_bmw_x3_has_multiple_generations():
    result = find_generations("BMW", "X3")
    assert [item.code for item in result] == ["E83", "F25", "G01", "G45"]


def test_vw_alias_resolves():
    result = find_generations("VW", "Tiguan")
    assert len(result) == 3
    assert result[0].brand == "Volkswagen"


def test_generation_lookup():
    item = get_generation("bmw_x3_g01")
    assert item is not None
    assert item.display_model == "X3 G01"


def test_unknown_model_falls_back_to_free_catalog():
    assert find_generations("Volvo", "XC90") == []
