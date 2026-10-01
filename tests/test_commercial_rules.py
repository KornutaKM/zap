from decimal import Decimal

import pytest

from app.commercial_rules import parse_provider_rules


def test_parse_provider_rules_casefolds_provider_names():
    rules = parse_provider_rules(
        '{"Exist":{"shipping_fee":"350","free_threshold":"7000"}}'
    )
    assert rules["exist"].shipping_fee == Decimal("350")
    assert rules["exist"].free_threshold == Decimal("7000")


def test_provider_rules_reject_invalid_json():
    with pytest.raises(ValueError):
        parse_provider_rules("not-json")


def test_empty_rules_are_allowed():
    assert parse_provider_rules("") == {}
