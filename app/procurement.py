from dataclasses import dataclass
from decimal import Decimal
from itertools import product

from app.domain import Offer, PartCandidate


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
    subtotal: Decimal,
    *,
    shipping_fee: Decimal = DEFAULT_SHIPPING,
    free_threshold: Decimal = Decimal("10000"),
) -> Decimal:
    return Decimal("0") if subtotal >= free_threshold else shipping_fee


def _build_plan(
    title: str,
    mode: str,
    choices: list[PurchaseChoice],
    shipping_fee: Decimal,
    free_threshold: Decimal,
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
                subtotal,
                shipping_fee=shipping_fee,
                free_threshold=free_threshold,
            )
            for subtotal in per_provider.values()
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
        ),
        _build_plan(
            "Самая быстрая сборка",
            "fastest",
            fastest_choices,
            shipping_fee,
            free_threshold,
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
