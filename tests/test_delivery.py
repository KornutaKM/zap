import pytest

from app.delivery import (
    DeliveryInput,
    delivery_snapshot_is_complete,
    normalize_phone,
    validate_delivery_input,
)


def valid_input(**overrides):
    values = dict(
        full_name="Иван Иванов",
        phone="+7 (999) 123-45-67",
        country="Россия",
        city="Москва",
        address_line1="ул. Примерная, 1",
        postal_code="101000",
        email="ivan@example.com",
    )
    values.update(overrides)
    return DeliveryInput(**values)


def test_delivery_input_normalizes_phone_and_spaces():
    result = validate_delivery_input(
        valid_input(full_name="  Иван   Иванов  ")
    )
    assert result.full_name == "Иван Иванов"
    assert result.phone == "+79991234567"


def test_delivery_input_rejects_bad_email():
    with pytest.raises(ValueError):
        validate_delivery_input(valid_input(email="bad"))


def test_phone_requires_reasonable_digit_count():
    with pytest.raises(ValueError):
        normalize_phone("123")


def test_delivery_snapshot_completeness():
    assert delivery_snapshot_is_complete({
        "full_name": "User",
        "phone": "12345678",
        "country": "Country",
        "city": "City",
        "address_line1": "Address",
    })
    assert not delivery_snapshot_is_complete({"full_name": "User"})
