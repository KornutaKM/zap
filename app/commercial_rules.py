import json
from decimal import Decimal, InvalidOperation

from app.procurement import ProviderCommercialRule


def parse_provider_rules(raw: str | None) -> dict[str, ProviderCommercialRule]:
    if not raw or not raw.strip():
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("PROCUREMENT_PROVIDER_RULES_JSON must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise ValueError("PROCUREMENT_PROVIDER_RULES_JSON must be a JSON object")

    result: dict[str, ProviderCommercialRule] = {}
    for provider, rule in payload.items():
        if not isinstance(provider, str) or not isinstance(rule, dict):
            raise ValueError("Each provider rule must be an object")

        try:
            shipping_fee = Decimal(str(rule.get("shipping_fee", "0")))
            free_threshold = Decimal(str(rule.get("free_threshold", "0")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid commercial rule for {provider}") from exc

        if shipping_fee < 0 or free_threshold < 0:
            raise ValueError(f"Commercial rule values must be non-negative for {provider}")

        result[provider.casefold()] = ProviderCommercialRule(
            shipping_fee=shipping_fee,
            free_threshold=free_threshold,
        )
    return result
