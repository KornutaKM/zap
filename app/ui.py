from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.catalog import get_children, get_node
from app.domain import FavoritePart, Offer, PartCandidate, SearchHistoryItem, Vehicle
from app.service_kits import BuiltKit, SERVICE_KITS
from app.vehicle_catalog import VehicleGeneration
from app.vehicle_resolver import VehicleModification

BTN_SEARCH = "🔎 Найти запчасть"
BTN_CATALOG = "📚 Каталог"
BTN_SERVICE = "🛠 ТО и обслуживание"
BTN_GARAGE = "🚗 Мой автомобиль"
BTN_FAVORITES = "⭐ Избранное"
BTN_HISTORY = "🕘 История"
BTN_ADD_CAR = "🚗 Добавить автомобиль"
BTN_MODEL_CATALOG = "📚 Каталог по модели"
BTN_ARTICLE = "🔎 Найти по артикулу"
BTN_CANCEL = "Отмена"


def main_menu(has_vehicle: bool) -> ReplyKeyboardMarkup:
    if has_vehicle:
        rows = [
            [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_CATALOG)],
            [KeyboardButton(text=BTN_SERVICE), KeyboardButton(text=BTN_GARAGE)],
            [KeyboardButton(text=BTN_FAVORITES), KeyboardButton(text=BTN_HISTORY)],
        ]
    else:
        rows = [
            [KeyboardButton(text=BTN_ADD_CAR)],
            [KeyboardButton(text=BTN_MODEL_CATALOG), KeyboardButton(text=BTN_ARTICLE)],
            [KeyboardButton(text=BTN_FAVORITES), KeyboardButton(text=BTN_HISTORY)],
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


def part_detail_keyboard(index: int, parent_id: str | None = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="⭐ В избранное", callback_data=f"favorite:add:{index}")],
        [InlineKeyboardButton(text="← К вариантам", callback_data="partlist:back")],
        [
            InlineKeyboardButton(text="🔎 Новый поиск", callback_data="action:search"),
            InlineKeyboardButton(text="📚 Каталог", callback_data="cat:root"),
        ],
    ]
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


def candidate_text(index: int, candidate: PartCandidate) -> str:
    price = f"{candidate.min_price:,.0f}".replace(",", " ")
    return (
        f"<b>{index}. {escape(candidate.brand)}</b> · "
        f"<code>{escape(candidate.article)}</code>\n"
        f"{escape(candidate.title)}\n"
        f"от {price} ₽ · от {candidate.min_delivery_days} дн. · "
        f"{len(candidate.offers)} предлож."
    )


def candidate_detail_text(candidate: PartCandidate) -> str:
    header_price = f"{candidate.min_price:,.0f}".replace(",", " ")
    lines = [
        f"<b>{escape(candidate.brand)} · <code>{escape(candidate.article)}</code></b>",
        escape(candidate.title),
        f"Цена: от <b>{header_price} ₽</b>",
        f"Предложений: <b>{len(candidate.offers)}</b>",
        "",
        "<b>Магазины</b>",
    ]

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
