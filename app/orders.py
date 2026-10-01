from dataclasses import dataclass
from decimal import Decimal

from app.db import (
    append_order_event,
    create_customer_order,
    get_customer_order,
    replace_order_totals,
    replace_supplier_group_totals,
    update_order_line_confirmation,
    update_order_status,
)
from app.domain import CustomerOrder, OrderLine, SupplierOrderGroup, Vehicle
from app.procurement import (
    ProviderCommercialRule,
    PurchasePlan,
    provider_shipping_estimate,
)


def _article_key(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


@dataclass(frozen=True, slots=True)
class OrderRevalidationResult:
    order: CustomerOrder
    missing_lines: tuple[str, ...]
    changed_lines: tuple[str, ...]
    confirmed_lines: int

    @property
    def is_ready(self) -> bool:
        return self.order.status == "ready"


def _valid_url(value: str | None) -> str | None:
    if value and value.startswith(("https://", "http://")):
        return value
    return None


async def create_order_from_plan(
    user_id: int,
    plan: PurchasePlan,
    *,
    vehicle_id: int | None,
    source_quote_id: int | None = None,
    shipping_fee: Decimal = Decimal("500"),
    free_threshold: Decimal = Decimal("10000"),
    provider_rules: dict[str, ProviderCommercialRule] | None = None,
) -> CustomerOrder:
    grouped: dict[str, list] = {}
    for choice in plan.choices:
        grouped.setdefault(choice.offer.provider, []).append(choice)

    groups: list[dict] = []
    shipping_total = Decimal("0")
    item_total = Decimal("0")

    for provider, choices in grouped.items():
        provider_item_total = sum(
            (choice.subtotal for choice in choices),
            start=Decimal("0"),
        )
        provider_shipping = provider_shipping_estimate(
            provider,
            provider_item_total,
            shipping_fee=shipping_fee,
            free_threshold=free_threshold,
            provider_rules=provider_rules,
        )
        item_total += provider_item_total
        shipping_total += provider_shipping

        first_url = next(
            (
                _valid_url(choice.offer.url)
                for choice in choices
                if _valid_url(choice.offer.url)
            ),
            None,
        )
        groups.append(
            {
                "provider": provider,
                "item_total": provider_item_total,
                "shipping_total": provider_shipping,
                "grand_total": provider_item_total + provider_shipping,
                "checkout_mode": "deeplink" if first_url else "unavailable",
                "checkout_url": first_url,
                "lines": [
                    {
                        "brand": choice.request.brand,
                        "article": choice.request.article,
                        "title": choice.request.title,
                        "quantity": choice.request.quantity,
                        "unit_price": choice.offer.price,
                        "delivery_days": choice.offer.delivery_days,
                        "offer_url": _valid_url(choice.offer.url),
                        "in_stock": choice.offer.in_stock,
                    }
                    for choice in choices
                ],
            }
        )

    return await create_customer_order(
        user_id,
        vehicle_id=vehicle_id,
        source_quote_id=source_quote_id,
        item_total=item_total,
        shipping_total=shipping_total,
        grand_total=item_total + shipping_total,
        groups=groups,
    )


async def revalidate_order(
    user_id: int,
    order_id: int,
    *,
    vehicle: Vehicle | None,
    search_service,
    shipping_fee: Decimal,
    free_threshold: Decimal,
    provider_rules: dict[str, ProviderCommercialRule] | None = None,
) -> OrderRevalidationResult | None:
    loaded = await get_customer_order(user_id, order_id)
    if loaded is None:
        return None

    order, groups, lines, _ = loaded
    lines_by_group: dict[int, list[OrderLine]] = {}
    for line in lines:
        lines_by_group.setdefault(line.group_id, []).append(line)

    missing: list[str] = []
    changed: list[str] = []
    confirmed = 0
    new_group_totals: dict[int, tuple[Decimal, Decimal, Decimal]] = {}

    for group in groups:
        provider_subtotal = Decimal("0")
        group_missing = False
        for line in lines_by_group.get(group.id, []):
            candidates = await search_service.parts(vehicle, line.article)
            requested_article = _article_key(line.article)
            requested_brand = line.brand.casefold()

            candidate = next(
                (
                    item for item in candidates
                    if _article_key(item.article) == requested_article
                    and item.brand.casefold() == requested_brand
                ),
                None,
            )
            if candidate is None:
                candidate = next(
                    (
                        item for item in candidates
                        if _article_key(item.article) == requested_article
                    ),
                    None,
                )

            offer = None
            if candidate is not None:
                offer = next(
                    (
                        item for item in candidate.offers
                        if item.provider.casefold() == group.provider.casefold()
                        and item.in_stock
                    ),
                    None,
                )

            if offer is None:
                group_missing = True
                missing.append(f"{line.brand} {line.article} · {group.provider}")
                await update_order_line_confirmation(
                    order_id,
                    line.id,
                    unit_price=line.unit_price,
                    delivery_days=line.delivery_days,
                    in_stock=False,
                    price_confirmed=False,
                    offer_url=line.offer_url,
                )
                continue

            price_changed = offer.price != line.unit_price
            if price_changed:
                changed.append(
                    f"{line.brand} {line.article}: "
                    f"{line.unit_price} → {offer.price} ₽ · {group.provider}"
                )

            await update_order_line_confirmation(
                order_id,
                line.id,
                unit_price=offer.price,
                delivery_days=offer.delivery_days,
                in_stock=True,
                price_confirmed=not price_changed,
                offer_url=_valid_url(offer.url),
            )
            provider_subtotal += offer.price * line.quantity
            confirmed += 1

        if not group_missing:
            shipping = provider_shipping_estimate(
                group.provider,
                provider_subtotal,
                shipping_fee=shipping_fee,
                free_threshold=free_threshold,
                provider_rules=provider_rules,
            )
            group_status = "price_changed" if changed else "validated"
            await replace_supplier_group_totals(
                order_id,
                group.id,
                item_total=provider_subtotal,
                shipping_total=shipping,
                grand_total=provider_subtotal + shipping,
                status=group_status,
            )
            new_group_totals[group.id] = (
                provider_subtotal,
                shipping,
                provider_subtotal + shipping,
            )
        else:
            await replace_supplier_group_totals(
                order_id,
                group.id,
                item_total=group.item_total,
                shipping_total=group.shipping_total,
                grand_total=group.grand_total,
                status="needs_attention",
            )

    if missing:
        updated = await update_order_status(
            user_id,
            order_id,
            "needs_attention",
            message="Не все позиции подтверждены у выбранных поставщиков.",
        )
    else:
        item_total = sum(
            (values[0] for values in new_group_totals.values()),
            start=Decimal("0"),
        )
        shipping_total = sum(
            (values[1] for values in new_group_totals.values()),
            start=Decimal("0"),
        )
        await replace_order_totals(
            user_id,
            order_id,
            item_total=item_total,
            shipping_total=shipping_total,
            grand_total=item_total + shipping_total,
        )
        target_status = "price_changed" if changed else "ready"
        updated = await update_order_status(
            user_id,
            order_id,
            target_status,
            message=(
                "Цены изменились после повторной проверки."
                if changed
                else "Все позиции и цены подтверждены."
            ),
        )

    if updated is None:
        return None

    await append_order_event(
        order_id,
        event_type="revalidation",
        message=(
            f"Проверено позиций: {confirmed}; "
            f"изменено цен: {len(changed)}; "
            f"недоступно: {len(missing)}."
        ),
        to_status=updated.status,
        payload={
            "confirmed": confirmed,
            "changed": len(changed),
            "missing": len(missing),
        },
    )
    return OrderRevalidationResult(
        order=updated,
        missing_lines=tuple(missing),
        changed_lines=tuple(changed),
        confirmed_lines=confirmed,
    )


async def confirm_revalidated_prices(
    user_id: int,
    order_id: int,
) -> CustomerOrder | None:
    loaded = await get_customer_order(user_id, order_id)
    if loaded is None:
        return None

    order, groups, lines, _ = loaded
    if order.status != "price_changed":
        return order

    if any(not line.in_stock for line in lines):
        return await update_order_status(
            user_id,
            order_id,
            "needs_attention",
            message="Нельзя подтвердить цены: часть позиций недоступна.",
        )

    for line in lines:
        await update_order_line_confirmation(
            order_id,
            line.id,
            unit_price=line.unit_price,
            delivery_days=line.delivery_days,
            in_stock=True,
            price_confirmed=True,
            offer_url=line.offer_url,
        )

    for group in groups:
        await replace_supplier_group_totals(
            order_id,
            group.id,
            item_total=group.item_total,
            shipping_total=group.shipping_total,
            grand_total=group.grand_total,
            status="ready",
        )

    updated = await update_order_status(
        user_id,
        order_id,
        "ready",
        message="Пользователь подтвердил обновлённые цены.",
    )
    return updated
