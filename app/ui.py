from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.catalog import get_children, get_node
from app.domain import FavoritePart, Offer, PartCandidate, SavedPurchaseQuote, SearchHistoryItem, ShoppingListItem, Vehicle
from app.procurement import PurchasePlan
from app.service_kits import BuiltKit, SERVICE_KITS
from app.vehicle_catalog import VehicleGeneration
from app.work_orders import WORK_PACKAGES
from app.vehicle_resolver import VehicleModification

BTN_SEARCH = "🔎 Найти запчасть"
BTN_CATALOG = "📚 Каталог"
BTN_SERVICE = "🛠 ТО и обслуживание"
BTN_GARAGE = "🚗 Мой автомобиль"
BTN_FAVORITES = "⭐ Избранное"
BTN_HISTORY = "🕘 История"
BTN_ALERTS = "🔔 Цены"
BTN_SHOPPING = "🛒 Закупка"
BTN_WORKS = "🧰 Работы"
BTN_QUOTES = "📄 Расчёты"
BTN_ADD_CAR = "🚗 Добавить автомобиль"
BTN_MODEL_CATALOG = "📚 Каталог по модели"
BTN_ARTICLE = "🔎 Найти по артикулу"
BTN_CANCEL = "Отмена"


def main_menu(has_vehicle: bool) -> ReplyKeyboardMarkup:
    if has_vehicle:
        rows = [
            [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_CATALOG)],
            [KeyboardButton(text=BTN_SERVICE), KeyboardButton(text=BTN_WORKS)],
            [KeyboardButton(text=BTN_GARAGE), KeyboardButton(text=BTN_SHOPPING)],
            [KeyboardButton(text=BTN_FAVORITES), KeyboardButton(text=BTN_HISTORY)],
            [KeyboardButton(text=BTN_QUOTES), KeyboardButton(text=BTN_ALERTS)],
        ]
    else:
        rows = [
            [KeyboardButton(text=BTN_ADD_CAR)],
            [KeyboardButton(text=BTN_MODEL_CATALOG), KeyboardButton(text=BTN_ARTICLE)],
            [KeyboardButton(text=BTN_SHOPPING), KeyboardButton(text=BTN_FAVORITES)],
            [KeyboardButton(text=BTN_HISTORY), KeyboardButton(text=BTN_QUOTES)],
            [KeyboardButton(text=BTN_ALERTS)],
        ]

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или напишите запрос",
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def catalog_keyboard(node_id: str) -> InlineKeyboardMarkup:
    node = get_node(node_id)
    if node is None:
        return InlineKeyboardMarkup(inline_keyboard=[])

    children = get_children(node_id)
    rows: list[list[InlineKeyboardButton]] = []

    # На верхнем уровне компактнее две кнопки в ряд.
    if node_id == "root":
        for i in range(0, len(children), 2):
            rows.append([
                InlineKeyboardButton(text=child.title, callback_data=f"cat:{child.id}")
                for child in children[i:i + 2]
            ])
    else:
        rows.extend(
            [[InlineKeyboardButton(text=child.title, callback_data=f"cat:{child.id}")]]
            for child in children
        )

    if node.parent:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=f"cat:{node.parent}")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def generation_keyboard(generations: list[VehicleGeneration]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{item.family} {item.code} · {item.years}",
                callback_data=f"vehgen:{item.key}",
            )
        ]
        for item in generations
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def parts_results_keyboard(
    candidates: list[PartCandidate],
    parent_id: str | None = None,
    *,
    page: int = 0,
    total_count: int | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{item.brand} · от {str(item.min_price)} ₽",
                callback_data=f"part:{index}",
            )
        ]
        for index, item in enumerate(candidates[:5])
    ]
    count = len(candidates) if total_count is None else total_count
    total_pages = max(1, (count + 4) // 5)
    if total_pages > 1:
        navigation: list[InlineKeyboardButton] = []
        if page > 0:
            navigation.append(
                InlineKeyboardButton(text="←", callback_data=f"page:{page - 1}")
            )
        navigation.append(
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="page:noop",
            )
        )
        if page + 1 < total_pages:
            navigation.append(
                InlineKeyboardButton(text="→", callback_data=f"page:{page + 1}")
            )
        rows.append(navigation)

    rows.append([
        InlineKeyboardButton(text="⭐ Рекоменд.", callback_data="sort:recommended"),
        InlineKeyboardButton(text="💰 Дешевле", callback_data="sort:price"),
        InlineKeyboardButton(text="🚚 Быстрее", callback_data="sort:speed"),
    ])
    rows.append([
        InlineKeyboardButton(text="🔎 Новый поиск", callback_data="action:search"),
        InlineKeyboardButton(text="📚 Каталог", callback_data="cat:root"),
    ])
    if parent_id:
        rows.append([InlineKeyboardButton(text="← К разделу", callback_data=f"cat:{parent_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def part_detail_keyboard(
    index: int,
    parent_id: str | None = None,
    candidate: PartCandidate | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🛒 В закупку", callback_data=f"shop:add:{index}"),
            InlineKeyboardButton(text="⭐ В избранное", callback_data=f"favorite:add:{index}"),
        ],
        [
            InlineKeyboardButton(text="🔔 Следить за ценой", callback_data=f"alert:add:{index}"),
            InlineKeyboardButton(text="📈 История цены", callback_data=f"pricehist:{index}"),
        ],
    ]

    if candidate is not None:
        seen_urls: set[str] = set()
        for offer in candidate.offers:
            if not offer.url or not offer.url.startswith(("https://", "http://")):
                continue
            if offer.url in seen_urls:
                continue
            seen_urls.add(offer.url)
            rows.append([
                InlineKeyboardButton(
                    text=f"↗ {offer.provider} · {offer.price:,.0f} ₽".replace(",", " "),
                    url=offer.url,
                )
            ])
            if len(seen_urls) >= 3:
                break

    rows.extend([
        [InlineKeyboardButton(text="← К вариантам", callback_data="partlist:back")],
        [
            InlineKeyboardButton(text="🔎 Новый поиск", callback_data="action:search"),
            InlineKeyboardButton(text="📚 Каталог", callback_data="cat:root"),
        ],
    ])
    if parent_id:
        rows.append([InlineKeyboardButton(text="← К разделу", callback_data=f"cat:{parent_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def results_keyboard(parent_id: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="🔎 Новый поиск", callback_data="action:search"),
            InlineKeyboardButton(text="📚 Каталог", callback_data="cat:root"),
        ]
    ]
    if parent_id:
        rows.append([InlineKeyboardButton(text="← К разделу", callback_data=f"cat:{parent_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vehicle_summary(vehicle: Vehicle) -> str:
    vin_text = f" · VIN …{escape(vehicle.vin[-4:])}" if vehicle.vin else ""
    year_text = f" · {vehicle.year}" if vehicle.year > 0 else ""
    return f"🚗 <b>{escape(vehicle.brand)} {escape(vehicle.model)}</b>{year_text}{vin_text}"


def offer_text(label: str, offer: Offer) -> str:
    price = f"{offer.price:,.0f}".replace(",", " ")
    return (
        f"<b>{label}</b>\n"
        f"{escape(offer.brand)} · <code>{escape(offer.article)}</code>\n"
        f"{price} ₽ · {offer.delivery_days} дн. · {escape(offer.provider)}"
    )


def fitment_badge(status: str) -> str:
    return {
        "confirmed": "✅ подтверждено",
        "probable": "🟡 вероятно",
        "unverified": "⚪ не проверено",
    }.get(status, "⚪ не проверено")


def candidate_text(index: int, candidate: PartCandidate) -> str:
    price = f"{candidate.min_price:,.0f}".replace(",", " ")
    return (
        f"<b>{index}. {escape(candidate.brand)}</b> · "
        f"<code>{escape(candidate.article)}</code>\n"
        f"{escape(candidate.title)}\n"
        f"{fitment_badge(candidate.fitment_status)}\n"
        f"от {price} ₽ · от {candidate.min_delivery_days} дн. · "
        f"{len(candidate.offers)} предлож."
    )


def candidate_detail_text(candidate: PartCandidate) -> str:
    header_price = f"{candidate.min_price:,.0f}".replace(",", " ")
    lines = [
        f"<b>{escape(candidate.brand)} · <code>{escape(candidate.article)}</code></b>",
        escape(candidate.title),
        f"Совместимость: <b>{fitment_badge(candidate.fitment_status)}</b>",
        f"Цена: от <b>{header_price} ₽</b>",
        f"Предложений: <b>{len(candidate.offers)}</b>",
    ]

    if candidate.oe_numbers:
        lines.append(
            "OE: " + ", ".join(
                f"<code>{escape(number)}</code>" for number in candidate.oe_numbers
            )
        )
    if candidate.fitment_reason:
        lines.append(escape(candidate.fitment_reason))

    lines.extend([
        "",
        "<b>Магазины</b>",
    ])

    for offer in candidate.offers[:8]:
        price = f"{offer.price:,.0f}".replace(",", " ")
        lines.append(
            f"• {escape(offer.provider)} — <b>{price} ₽</b> · {offer.delivery_days} дн."
        )

    return "\n".join(lines)


def service_kits_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=kit.title,
                callback_data=f"kit:{kit.id}",
            )
        ]
        for kit in SERVICE_KITS.values()
    ]
    rows.append([InlineKeyboardButton(text="📚 Отдельные позиции ТО", callback_data="cat:service")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def built_kit_text(built: BuiltKit) -> str:
    lines = [
        f"<b>{escape(built.kit.title)}</b>",
        escape(built.kit.description),
        "",
    ]

    for index, item in enumerate(built.items, start=1):
        candidate = item.candidate
        price = f"{candidate.min_price:,.0f}".replace(",", " ")
        lines.append(
            f"{index}. <b>{escape(candidate.brand)}</b> · "
            f"<code>{escape(candidate.article)}</code>\n"
            f"   {escape(item.query)} — от {price} ₽"
        )

    total = f"{built.total_price:,.0f}".replace(",", " ")
    lines.extend(
        [
            "",
            f"Ориентировочно: <b>{total} ₽</b>",
            f"Собрать можно от {built.max_delivery_days} дн.",
        ]
    )
    return "\n".join(lines)


def built_kit_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛠 Другой комплект", callback_data="action:kits")],
            [InlineKeyboardButton(text="📚 Каталог ТО", callback_data="cat:service")],
        ]
    )


def garage_keyboard(
    vehicles: list[Vehicle],
    active_id: int | None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for vehicle in vehicles:
        marker = "✅ " if vehicle.id == active_id else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{marker}{vehicle.brand} {vehicle.model} · {vehicle.year}",
                callback_data=f"garage:set:{vehicle.id}",
            )
        ])

    rows.append([InlineKeyboardButton(text="➕ Добавить автомобиль", callback_data="garage:add")])
    if active_id is not None:
        rows.append([
            InlineKeyboardButton(
                text="⚙️ Уточнить модификацию",
                callback_data=f"garage:resolve:{active_id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text="🗑 Удалить активный автомобиль",
                callback_data=f"garage:delete:{active_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def delete_vehicle_confirm_keyboard(vehicle_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=f"garage:confirmdel:{vehicle_id}",
                ),
                InlineKeyboardButton(text="Отмена", callback_data="garage:canceldelete"),
            ]
        ]
    )



def history_keyboard(items: list[SearchHistoryItem]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{item.query[:42]}",
                callback_data=f"history:run:{item.id}",
            )
        ]
        for item in items[:10]
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def favorites_keyboard(items: list[FavoritePart]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:20]:
        rows.append([
            InlineKeyboardButton(
                text=f"{item.brand} · {item.article}",
                callback_data=f"favorite:open:{item.id}",
            ),
            InlineKeyboardButton(
                text="✕",
                callback_data=f"favorite:delete:{item.id}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def modification_keyboard(
    vehicle_id: int,
    modifications: list[VehicleModification],
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=item.label,
                callback_data=f"mod:{vehicle_id}:{item.key}",
            )
        ]
        for item in modifications
    ]
    rows.append([
        InlineKeyboardButton(text="← В гараж", callback_data="garage:canceldelete")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def vehicle_modification_text(vehicle: Vehicle) -> str:
    if not vehicle.modification_key:
        return "Модификация не уточнена"

    bits = [
        vehicle.generation_code,
        vehicle.engine,
        vehicle.fuel,
        vehicle.drive,
        f"{vehicle.power_hp} л.с." if vehicle.power_hp else None,
    ]
    return " · ".join(escape(bit) for bit in bits if bit)



def price_alerts_keyboard(alerts) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for alert in alerts[:20]:
        target = f"{alert.target_price:,.0f}".replace(",", " ")
        rows.append([
            InlineKeyboardButton(
                text=f"{alert.brand} {alert.article} ≤ {target} ₽",
                callback_data=f"alert:noop:{alert.id}",
            ),
            InlineKeyboardButton(
                text="✕",
                callback_data=f"alert:delete:{alert.id}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def price_alert_target_keyboard(index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="−5%", callback_data=f"alert:set:{index}:5"),
                InlineKeyboardButton(text="−10%", callback_data=f"alert:set:{index}:10"),
                InlineKeyboardButton(text="−20%", callback_data=f"alert:set:{index}:20"),
            ],
            [
                InlineKeyboardButton(
                    text="Текущая цена",
                    callback_data=f"alert:set:{index}:0",
                )
            ],
            [InlineKeyboardButton(text="Отмена", callback_data=f"part:{index}")],
        ]
    )



def shopping_list_keyboard(items: list[ShoppingListItem]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in items[:20]:
        rows.append([
            InlineKeyboardButton(text="−", callback_data=f"shop:qty:{item.id}:-1"),
            InlineKeyboardButton(
                text=f"{item.brand} {item.article} × {item.quantity}",
                callback_data=f"shop:item:{item.id}",
            ),
            InlineKeyboardButton(text="+", callback_data=f"shop:qty:{item.id}:1"),
            InlineKeyboardButton(text="✕", callback_data=f"shop:del:{item.id}"),
        ])

    if items:
        rows.append([
            InlineKeyboardButton(text="🧮 Рассчитать заказ", callback_data="shop:optimize")
        ])
        rows.append([
            InlineKeyboardButton(text="🗑 Очистить список", callback_data="shop:clear")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def shopping_list_text(items: list[ShoppingListItem]) -> str:
    if not items:
        return "<b>Список закупки пуст</b>\nДобавляйте детали из карточек."

    lines = ["<b>Список закупки</b>", ""]
    for index, item in enumerate(items, start=1):
        lines.append(
            f"{index}. <b>{escape(item.brand)}</b> · "
            f"<code>{escape(item.article)}</code> × {item.quantity}\n"
            f"   {escape(item.title)}"
        )
    lines.extend([
        "",
        "Нажмите «Рассчитать заказ», чтобы обновить цены и сравнить магазины.",
    ])
    return "\n".join(lines)


def purchase_plan_text(plan: PurchasePlan, index: int) -> str:
    item_total = f"{plan.item_total:,.0f}".replace(",", " ")
    shipping = f"{plan.shipping_total:,.0f}".replace(",", " ")
    total = f"{plan.grand_total:,.0f}".replace(",", " ")

    lines = [
        f"<b>{index}. {escape(plan.title)}</b>",
        f"Детали: {item_total} ₽ · доставка: {shipping} ₽",
        f"Итого: <b>{total} ₽</b>",
        f"Магазинов: {plan.provider_count} · срок до {plan.max_delivery_days} дн.",
        "",
    ]
    for choice in plan.choices:
        price = f"{choice.offer.price:,.0f}".replace(",", " ")
        lines.append(
            f"• {escape(choice.request.brand)} "
            f"<code>{escape(choice.request.article)}</code> × {choice.request.quantity}\n"
            f"  {escape(choice.offer.provider)} · {price} ₽ · "
            f"{choice.offer.delivery_days} дн."
        )
    return "\n".join(lines)


def purchase_plan_keyboard(
    plan: PurchasePlan,
    plan_index: int | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    seen: set[str] = set()
    for choice in plan.choices:
        url = choice.offer.url
        if not url or not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        rows.append([
            InlineKeyboardButton(
                text=f"↗ {choice.offer.provider} · {choice.request.article}",
                url=url,
            )
        ])
        if len(rows) >= 8:
            break

    if plan_index is not None:
        rows.append([
            InlineKeyboardButton(
                text="💾 Сохранить расчёт",
                callback_data=f"quote:save:{plan_index}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="← К списку", callback_data="shop:back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def purchase_plans_keyboard(plans: list[PurchasePlan]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=f"{index + 1}. {plan.title}",
                callback_data=f"shop:plan:{index}",
            )
        ]
        for index, plan in enumerate(plans[:5])
    ]
    rows.append([InlineKeyboardButton(text="← К списку", callback_data="shop:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def work_packages_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=package.title,
                callback_data=f"work:pkg:{package.id}",
            )
        ]
        for package in WORK_PACKAGES.values()
    ]
    rows.append([
        InlineKeyboardButton(
            text="✍️ Свой список работ",
            callback_data="work:custom",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)



def quotes_keyboard(quotes: list[SavedPurchaseQuote]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for quote in quotes[:20]:
        total = f"{quote.grand_total:,.0f}".replace(",", " ")
        rows.append([
            InlineKeyboardButton(
                text=f"#{quote.id} · {quote.title[:28]} · {total} ₽",
                callback_data=f"quote:open:{quote.id}",
            ),
            InlineKeyboardButton(
                text="✕",
                callback_data=f"quote:delete:{quote.id}",
            ),
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def saved_quote_keyboard(
    quote_id: int,
    plan: PurchasePlan,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    seen: set[str] = set()
    for choice in plan.choices:
        url = choice.offer.url
        if not url or not url.startswith(("https://", "http://")) or url in seen:
            continue
        seen.add(url)
        rows.append([
            InlineKeyboardButton(
                text=f"↗ {choice.offer.provider} · {choice.request.article}",
                url=url,
            )
        ])
        if len(rows) >= 8:
            break

    rows.append([
        InlineKeyboardButton(text="🗑 Удалить расчёт", callback_data=f"quote:delete:{quote_id}")
    ])
    rows.append([
        InlineKeyboardButton(text="← К расчётам", callback_data="quote:list")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)
