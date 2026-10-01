from decimal import Decimal

import pytest

from app.domain import Vehicle
from app.external_provider import (
    GenericHttpProvider,
    HttpProviderConfig,
    parse_offer_payload,
)


def test_parse_offer_payload_accepts_items():
    offers = parse_offer_payload(
        {
            "items": [
                {
                    "brand": "ATE",
                    "article": "123",
                    "title": "Pads",
                    "price": "100.50",
                    "delivery_days": 2,
                    "quality": 0.95,
                    "in_stock": True,
                }
            ]
        },
        "Partner API",
    )
    assert len(offers) == 1
    assert offers[0].price == Decimal("100.50")
    assert offers[0].provider == "Partner API"


def test_parse_offer_payload_skips_invalid_rows():
    offers = parse_offer_payload(
        {"items": [{"brand": "ATE"}, {"brand": "B", "article": "1", "price": "-1"}]},
        "Partner",
    )
    assert offers == []


def test_http_provider_requires_https_by_default():
    with pytest.raises(ValueError):
        GenericHttpProvider(
            HttpProviderConfig(
                name="Unsafe",
                base_url="http://example.test",
            )
        )


def test_provider_params_include_vehicle_modification():
    provider = GenericHttpProvider(
        HttpProviderConfig(
            name="Partner",
            base_url="https://example.test",
        )
    )
    vehicle = Vehicle(
        "BMW",
        "X3 G01",
        2020,
        vin="WBA00000000000000",
        generation_code="G01",
        engine="B47D20",
        drive="xDrive",
        modification_key="bmw_x3_g01_20d_xdrive",
    )
    params = provider._params(vehicle, "масляный фильтр")
    assert params["engine"] == "B47D20"
    assert params["generation"] == "G01"
    assert params["modification_key"] == "bmw_x3_g01_20d_xdrive"
