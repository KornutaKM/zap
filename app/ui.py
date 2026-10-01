from html import escape

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.catalog import get_children, get_node
from app.domain import Offer, Vehicle

BTN_SEARCH = "🔎 Найти запчасть"
BTN_CATALOG = "📚 Каталог"
BTN_SERVICE = "🛠 ТО и обслуживание"
BTN_GARAGE = "🚗 Мой автомобиль"
BTN_ADD_CAR = "🚗 Добавить автомобиль"
BTN_MODEL_CATALOG = "📚 Каталог по модели"
BTN_ARTICLE = "🔎 Найти по артикулу"
BTN_CANCEL = "Отмена"


def main_menu(has_vehicle: bool) -> ReplyKeyboardMarkup:
    if has_vehicle:
        rows = [
            [KeyboardButton(text=BTN_SEARCH), KeyboardButton(text=BTN_CATALOG)],
            [KeyboardButton(text=BTN_SERVICE), KeyboardButton(text=BTN_GARAGE)],
        ]
    else:
        rows = [
            [KeyboardButton(text=BTN_ADD_CAR)],
            [KeyboardButton(text=BTN_MODEL_CATALOG), KeyboardButton(text=BTN_ARTICLE)],
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
    return f"🚗 <b>{escape(vehicle.brand)} {escape(vehicle.model)}</b> · {vehicle.year}{vin_text}"


def offer_text(label: str, offer: Offer) -> str:
    price = f"{offer.price:,.0f}".replace(",", " ")
    return (
        f"<b>{label}</b>\n"
        f"{escape(offer.brand)} · <code>{escape(offer.article)}</code>\n"
        f"{price} ₽ · {offer.delivery_days} дн. · {escape(offer.provider)}"
    )
