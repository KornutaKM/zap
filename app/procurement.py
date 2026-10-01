from dataclasses import dataclass
from decimal import Decimal
from itertools import product

from app.domain import Offer, PartCandidate


@dataclass(frozen=True, slots=True)
class ProviderCommercialRule:
    shipping_fee: Decimal
    free_threshold: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseRequest:
    brand: str
    article: str
    title: str
    quantity: int = 1


@dataclass(frozen=True, slots=True)
class PurchaseChoice:
    request: PurchaseRequest
    offer: Offer

    @property
    def subtotal(self) -> Decimal:
        return self.offer.price * self.request.quantity


@dataclass(frozen=True, slots=True)
class PurchasePlan:
    mode: str
    title: str
    choices: tuple[PurchaseChoice, ...]
    item_total: Decimal
    shipping_total: Decimal
    grand_total: Decimal
    provider_count: int
    max_delivery_days: int


DEFAULT_SHIPPING = Decimal("500")


def _provider_shipping(
    provider: str,
    subtotal: Decimal,
    *,
    shipping_fee: Decimal = DEFAULT_SHIPPING,
    free_threshold: Decimal = Decimal("10000"),
    provider_rules: dict[str, ProviderCommercialRule] | None = None,
) -> Decimal:
    rule = None
    if provider_rules:
        rule = provider_rules.get(provider.casefold())

    effective_fee = rule.shipping_fee if rule else shipping_fee
    effective_threshold = rule.free_threshold if rule else free_threshold
    return (
        Decimal("0")
        if subtotal >= effective_threshold
        else effective_fee
    )


def _build_plan(
    title: str,
    mode: str,
    choices: list[PurchaseChoice],
    shipping_fee: Decimal,
    free_threshold: Decimal,
    provider_rules: dict[str, ProviderCommercialRule] | None,
) -> PurchasePlan:
    per_provider: dict[str, Decimal] = {}
    item_total = Decimal("0")
    max_days = 0

    for choice in choices:
        item_total += choice.subtotal
        max_days = max(max_days, choice.offer.delivery_days)
        per_provider[choice.offer.provider] = (
            per_provider.get(choice.offer.provider, Decimal("0"))
            + choice.subtotal
        )

    shipping_total = sum(
        (
            _provider_shipping(
                provider,
                subtotal,
                shipping_fee=shipping_fee,
                free_threshold=free_threshold,
                provider_rules=provider_rules,
            )
            for provider, subtotal in per_provider.items()
        ),
        start=Decimal("0"),
    )
    return PurchasePlan(
        mode=mode,
        title=title,
        choices=tuple(choices),
        item_total=item_total,
        shipping_total=shipping_total,
        grand_total=item_total + shipping_total,
        provider_count=len(per_provider),
        max_delivery_days=max_days,
    )


def optimize_purchase(
    requests: list[PurchaseRequest],
    candidates: dict[tuple[str, str], PartCandidate],
    *,
    shipping_fee: Decimal = DEFAULT_SHIPPING,
    free_threshold: Decimal = Decimal("10000"),
    combination_limit: int = 50000,
    provider_rules: dict[str, ProviderCommercialRule] | None = None,
) -> list[PurchasePlan]:
    option_lists: list[list[PurchaseChoice]] = []
    for request in requests:
        key = (request.brand.casefold(), request.article.casefold())
        candidate = candidates.get(key)
        if candidate is None:
            continue

        options = [
            PurchaseChoice(request=request, offer=offer)
            for offer in candidate.offers
            if offer.in_stock
        ]
        if options:
            option_lists.append(options)

    if not option_lists:
        return []

    cheapest_choices = [
        min(options, key=lambda item: (item.offer.price, item.offer.delivery_days))
        for options in option_lists
    ]
    fastest_choices = [
        min(options, key=lambda item: (item.offer.delivery_days, item.offer.price))
        for options in option_lists
    ]

    plans = [
        _build_plan(
            "Минимум цен по позициям",
            "cheapest_items",
            cheapest_choices,
            shipping_fee,
            free_threshold,
            provider_rules,
        ),
        _build_plan(
            "Самая быстрая сборка",
            "fastest",
            fastest_choices,
            shipping_fee,
            free_threshold,
            provider_rules,
        ),
    ]

    common_providers = set(choice.offer.provider for choice in option_lists[0])
    for options in option_lists[1:]:
        common_providers &= {choice.offer.provider for choice in options}

    if common_providers:
        single_store_plans = []
        for provider in common_providers:
            choices = [
                min(
                    (item for item in options if item.offer.provider == provider),
                    key=lambda item: (item.offer.price, item.offer.delivery_days),
                )
                for options in option_lists
            ]
            single_store_plans.append(
                _build_plan(
                    f"Всё в одном магазине: {provider}",
                    "single_store",
                    choices,
                    shipping_fee,
                    free_threshold,
                    provider_rules,
                )
            )
        plans.append(min(single_store_plans, key=lambda plan: plan.grand_total))

    combinations = 1
    for options in option_lists:
        combinations *= len(options)

    if combinations <= combination_limit:
        best = None
        for combo in product(*option_lists):
            plan = _build_plan(
                "Оптимальный заказ",
                "optimized",
                list(combo),
                shipping_fee,
                free_threshold,
                provider_rules,
            )
            score = (
                plan.grand_total,
                plan.provider_count,
                plan.max_delivery_days,
            )
            if best is None or score < best[0]:
                best = (score, plan)
        if best is not None:
            plans.append(best[1])

    unique: dict[tuple, PurchasePlan] = {}
    for plan in plans:
        signature = tuple(
            (item.request.article, item.offer.provider, item.offer.price)
            for item in plan.choices
        )
        unique.setdefault(signature, plan)

    return sorted(
        unique.values(),
        key=lambda plan: (
            plan.grand_total,
            plan.provider_count,
            plan.max_delivery_days,
        ),
    )



def serialize_purchase_plan(plan: PurchasePlan) -> dict:
    return {
        "mode": plan.mode,
        "title": plan.title,
        "item_total": str(plan.item_total),
        "shipping_total": str(plan.shipping_total),
        "grand_total": str(plan.grand_total),
        "provider_count": plan.provider_count,
        "max_delivery_days": plan.max_delivery_days,
        "choices": [
            {
                "request": {
                    "brand": choice.request.brand,
                    "article": choice.request.article,
                    "title": choice.request.title,
                    "quantity": choice.request.quantity,
                },
                "offer": {
                    "provider": choice.offer.provider,
                    "brand": choice.offer.brand,
                    "article": choice.offer.article,
                    "title": choice.offer.title,
                    "price": str(choice.offer.price),
                    "delivery_days": choice.offer.delivery_days,
                    "quality": choice.offer.quality,
                    "url": choice.offer.url,
                    "in_stock": choice.offer.in_stock,
                },
            }
            for choice in plan.choices
        ],
    }


def deserialize_purchase_plan(data: dict) -> PurchasePlan:
    choices = []
    for item in data["choices"]:
        request_data = item["request"]
        offer_data = item["offer"]
        request = PurchaseRequest(
            brand=request_data["brand"],
            article=request_data["article"],
            title=request_data["title"],
            quantity=int(request_data["quantity"]),
        )
        offer = Offer(
            provider=offer_data["provider"],
            brand=offer_data["brand"],
            article=offer_data["article"],
            title=offer_data["title"],
            price=Decimal(offer_data["price"]),
            delivery_days=int(offer_data["delivery_days"]),
            quality=float(offer_data["quality"]),
            url=offer_data.get("url"),
            in_stock=bool(offer_data.get("in_stock", True)),
        )
        choices.append(PurchaseChoice(request=request, offer=offer))

    return PurchasePlan(
        mode=data["mode"],
        title=data["title"],
        choices=tuple(choices),
        item_total=Decimal(data["item_total"]),
        shipping_total=Decimal(data["shipping_total"]),
        grand_total=Decimal(data["grand_total"]),
        provider_count=int(data["provider_count"]),
        max_delivery_days=int(data["max_delivery_days"]),
    )



@dataclass(frozen=True, slots=True)
class PurchasePlanComparison:
    saved_total: Decimal
    current_total: Decimal
    delta: Decimal
    delta_percent: Decimal
    saved_provider_count: int
    current_provider_count: int
    saved_max_delivery_days: int
    current_max_delivery_days: int


def requests_from_plan(plan: PurchasePlan) -> list[PurchaseRequest]:
    result: list[PurchaseRequest] = []
    seen: set[tuple[str, str]] = set()
    for choice in plan.choices:
        key = (
            choice.request.brand.casefold(),
            choice.request.article.casefold(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(choice.request)
    return result


def compare_purchase_plans(
    saved: PurchasePlan,
    current: PurchasePlan,
) -> PurchasePlanComparison:
    delta = current.grand_total - saved.grand_total
    delta_percent = (
        (delta / saved.grand_total) * Decimal("100")
        if saved.grand_total
        else Decimal("0")
    )
    return PurchasePlanComparison(
        saved_total=saved.grand_total,
        current_total=current.grand_total,
        delta=delta,
        delta_percent=delta_percent,
        saved_provider_count=saved.provider_count,
        current_provider_count=current.provider_count,
        saved_max_delivery_days=saved.max_delivery_days,
        current_max_delivery_days=current.max_delivery_days,
    )
