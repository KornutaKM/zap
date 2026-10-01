import pytest

from app.operators import is_operator, parse_operator_user_ids


def test_operator_allowlist_parsing():
    ids = parse_operator_user_ids("123, 456;123")
    assert ids == frozenset({123, 456})
    assert is_operator(123, ids)
    assert not is_operator(999, ids)


def test_empty_operator_allowlist_disables_access():
    assert parse_operator_user_ids(None) == frozenset()
    assert parse_operator_user_ids("  ") == frozenset()


def test_operator_allowlist_rejects_invalid_ids():
    with pytest.raises(ValueError):
        parse_operator_user_ids("123,bad")
    with pytest.raises(ValueError):
        parse_operator_user_ids("-1")
