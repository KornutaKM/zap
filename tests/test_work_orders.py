from app.work_orders import get_work_package, parse_work_text


def test_custom_front_brakes_expands_to_two_positions():
    parts = parse_work_text("Нужно заменить передние тормоза")
    queries = {item.query for item in parts}
    assert "передние тормозные колодки" in queries
    assert "передние тормозные диски" in queries
    disc = next(item for item in parts if "диски" in item.query)
    assert disc.quantity == 2


def test_custom_service_deduplicates_oil_filter():
    parts = parse_work_text("замена масла и масляный фильтр")
    assert [item.query for item in parts].count("масляный фильтр") == 1


def test_front_brake_package_exists():
    package = get_work_package("front_brakes")
    assert package is not None
    assert len(package.parts) == 2
