from app.query_parser import parse_search_query


def test_price_preference():
    parsed = parse_search_query("передние колодки подешевле")
    assert parsed.sort_mode == "price"
    assert parsed.part_query == "передние колодки"


def test_speed_preference():
    parsed = parse_search_query("амортизаторы срочно")
    assert parsed.sort_mode == "speed"
    assert parsed.part_query == "амортизаторы"


def test_default_preference():
    parsed = parse_search_query("хороший масляный фильтр")
    assert parsed.sort_mode == "recommended"


def test_whitespace_is_normalized():
    parsed = parse_search_query("  масляный   фильтр  ")
    assert parsed.raw == "масляный фильтр"
