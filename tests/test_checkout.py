import asyncio
from decimal import Decimal

import pytest

from app.checkout import (
    CheckoutDelivery,
    CheckoutLine,
    CheckoutRecipient,
    CheckoutRegistry,
    CheckoutRequest,
    DeeplinkCheckoutAdapter,
    GenericHttpCheckoutAdapter,
    HttpCheckoutConfig,
    build_checkout_payload,
    parse_checkout_extra_payload,
)


def request(url="https://shop.example/item"):
    return CheckoutRequest(
        order_id=1,
        group_id=2,
        provider="Store",
        total=Decimal("1000"),
        lines=(CheckoutLine("ATE", "123", "Pads", 1, Decimal("1000")),),
        fallback_url=url,
    )


def test_deeplink_checkout_requires_valid_url():
    result = asyncio.run(DeeplinkCheckoutAdapter().create_checkout(request()))
    assert result.status == "manual_required"
    assert result.checkout_url == "https://shop.example/item"

    failed = asyncio.run(
        DeeplinkCheckoutAdapter().create_checkout(request("javascript:alert(1)"))
    )
    assert failed.status == "failed"


def test_registry_falls_back_to_deeplink():
    registry = CheckoutRegistry()
    assert isinstance(registry.for_provider("Unknown"), DeeplinkCheckoutAdapter)


def test_http_checkout_requires_https():
    with pytest.raises(ValueError):
        GenericHttpCheckoutAdapter(
            HttpCheckoutConfig(
                provider_name="Store",
                base_url="http://example.test",
            )
        )



def test_checkout_provider_context_must_be_json_object():
    assert parse_checkout_extra_payload('{"warehouse":"msk"}') == {
        "warehouse": "msk"
    }
    with pytest.raises(ValueError):
        parse_checkout_extra_payload('["not", "object"]')


def test_deeplink_cancel_never_claims_remote_cancellation():
    result = asyncio.run(
        DeeplinkCheckoutAdapter().cancel_checkout("external-1")
    )
    assert result.status == "unknown"
    assert result.error



def test_http_checkout_refuses_missing_delivery_before_network():
    adapter = GenericHttpCheckoutAdapter(
        HttpCheckoutConfig(
            provider_name="Store",
            base_url="https://example.test",
        )
    )
    result = asyncio.run(adapter.create_checkout(request()))
    assert result.status == "failed"
    assert result.error == "delivery_required"



def test_checkout_payload_contains_delivery_and_isolates_provider_context():
    req = CheckoutRequest(
        order_id=10,
        group_id=20,
        provider="Store",
        total=Decimal("1500"),
        lines=(CheckoutLine("ATE", "123", "Pads", 1, Decimal("1000")),),
        recipient=CheckoutRecipient(
            full_name="Иван Иванов",
            phone="+79991234567",
            email="ivan@example.com",
        ),
        delivery=CheckoutDelivery(
            country="Россия",
            city="Москва",
            address_line1="ул. Примерная, 1",
            postal_code="101000",
        ),
    )
    payload = build_checkout_payload(
        req,
        extra_payload={
            "warehouse": "msk",
            "total": "cannot override root total",
        },
    )
    assert payload["idempotency_key"] == "zap:10:20"
    assert payload["total"] == "1500"
    assert payload["recipient"]["phone"] == "+79991234567"
    assert payload["delivery_address"]["city"] == "Москва"
    assert payload["provider_context"]["warehouse"] == "msk"
    assert payload["provider_context"]["total"] == "cannot override root total"
    assert payload["total"] != payload["provider_context"]["total"]
