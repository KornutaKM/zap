import pytest

from app.external_fitment import (
    GenericHttpFitmentCatalog,
    HttpFitmentConfig,
    parse_fitment_payload,
)


def test_parse_fitment_payload():
    result = parse_fitment_payload(
        {
            "status": "confirmed",
            "oe_numbers": ["34 11 6 889 570"],
            "crosses": [
                {"brand": "ATE", "article": "13.0460-7184.2"},
                {"brand": "TRW", "article": "GDB1956"},
            ],
            "reason": "Matched by vehicle modification",
        }
    )
    assert result.confirmed
    assert len(result.crosses) == 2
    assert result.oe_numbers == ("34 11 6 889 570",)


def test_invalid_status_falls_back_to_unverified():
    result = parse_fitment_payload({"status": "magic"})
    assert result.status == "unverified"


def test_fitment_adapter_requires_https():
    with pytest.raises(ValueError):
        GenericHttpFitmentCatalog(
            HttpFitmentConfig(base_url="http://example.test")
        )
