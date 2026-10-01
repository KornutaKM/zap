import asyncio
from decimal import Decimal

import pytest

from app.checkout import (
    CheckoutLine,
    CheckoutRegistry,
    CheckoutRequest,
    DeeplinkCheckoutAdapter,
    GenericHttpCheckoutAdapter,
    HttpCheckoutConfig,
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
