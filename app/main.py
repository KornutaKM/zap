import asyncio
from html import escape

from aiogram import Bot, CallbackQuery, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.catalog import get_children, get_node
from app.config import settings
from app.db import get_vehicle, init_db, save_vehicle
from app.domain import Vehicle, rank_offers
from app.providers import AutodocProvider, ExistProvider, MockProvider


class Garage(StatesGroup):
    brand = State()
    model = State()
    year = State()
    vin = State()


providers = [MockProvider(), ExistProvider(), AutodocProvider()]
dp = Dispatcher()

KNOWN_BRANDS = {
    "audi", "bmw", "chevrolet", "citroen", "ford", "geely", "haval", "honda",
    "hyundai", "jeep", "kia", "lada", "lexus", "mazda", "mercedes",
    "mercedes-benz", "mitsubishi", "nissan", "opel", "peugeot", "porsche",
    "renault", "skoda", "subaru", "suzuki", "tesla", "toyota", "volkswagen",
    "volvo", "ваз", "газ", "москвич", "chery", "exeed", "omoda", "jetour"
}

MULTIWORD_BRANDS = {
    ("land", "rover"): "Land Rover",
    ("alfa", "romeo"): "Alfa Romeo",
    ("mercedes", "benz"): "Mercedes-Benz",
}


def catalog_keyboard(node_id: str) -> InlineKeyboardMarkup:
    node = get_node(node_id)
    if node is None:
        return InlineKeyboardMarkup(inline_keyboard=[])

    rows = [
        [InlineKeyboardButton(text=child.title, callback_data=f"cat:{child.id}")]
        for child in get_children(node_id)
    ]

    if node.parent:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=f"cat:{node.parent}")])
    elif node_id != "root":
        rows.append([InlineKeyboardButton(text="← В начало", callback_data="cat:root")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def leaf_keyboard(parent_id: str | None) -> InlineKeyboardMarkup:
    rows = []
    if parent_id:
        rows.append([InlineKeyboardButton(text="← Назад", callback_data=f"cat:{parent_id}")])
    rows.append([InlineKeyboardButton(text="Каталог с начала", callback_data="cat:root")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_context_title(brand: str, model: str, year: int | None = None) -> str:
    year_text = f", {year}" if year else ""
    return f"{escape(brand)} {escape(model)}{year_text}"


async def store_catalog_context(
    state: FSMContext,
    brand: str,
    model: str,
    year: int | None,
    vin: str | None,
    source: str,
) -> None:
    await state.update_data(
        catalog_vehicle={
            "brand": brand,
            "model": model,
            "year": year,
            "vin": vin,
            "source": source,
        }
    )


async def show_catalog_root(message: Message, state: FSMContext, brand: str, model: str, year: int | None, vin: str | None, source: str) -> None:
    await store_catalog_context(state, brand, model, year, vin, source)
    warning = (
        "Каталог общий для модели. Точную применимость конкретного артикула "
        "нужно уточнить по году, модификации или VIN."
        if source == "temporary"
        else "Пока каталог и предложения демонстрационные; точную применимость подключим отдельным каталогом."
    )
    await message.answer(
        f"<b>{catalog_context_title(brand, model, year)}</b>\n"
        f"Выберите раздел запчастей.\n\n"
        f"<i>{warning}</i>",
        reply_markup=catalog_keyboard("root"),
    )


async def get_catalog_vehicle(state: FSMContext, user_id: int) -> tuple[Vehicle | None, str]:
    data = await state.get_data()
    ctx = data.get("catalog_vehicle")
    if ctx:
        vehicle = Vehicle(
            brand=ctx["brand"],
            model=ctx["model"],
            year=ctx.get("year") or 0,
            vin=ctx.get("vin"),
        )
        return vehicle, ctx.get("source", "temporary")

    vehicle = await get_vehicle(user_id)
    return vehicle, "garage" if vehicle else "none"


def parse_vehicle_text(text: str) -> tuple[str, str] | None:
    parts = text.strip().split()
    if len(parts) < 2:
        return None

    if len(parts) >= 3:
        pair = (parts[0].casefold().rstrip("-"), parts[1].casefold())
        multiword_brand = MULTIWORD_BRANDS.get(pair)
        if multiword_brand:
            return multiword_brand, " ".join(parts[2:])

    first = parts[0].casefold()
    if first not in KNOWN_BRANDS:
        return None
    return parts[0], " ".join(parts[1:])


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "<b>Автозапчасти — MVP</b>\n\n"
        "Можно работать двумя способами:\n"
        "• добавить автомобиль: /garage\n"
        "• открыть каталог: /catalog\n"
        "• написать модель прямо сообщением, например <code>BMW X3 G01</code>\n"
        "• написать название детали или артикул.\n\n"
        "<i>Пока используются демонстрационные цены и каталог.</i>"
    )


@dp.message(Command("garage"))
async def garage(message: Message, state: FSMContext):
    current = await get_vehicle(message.from_user.id)
    if current:
        vin = current.vin or "не указан"
        await message.answer(
            f"<b>Сейчас:</b> {escape(current.brand)} {escape(current.model)}, {current.year}\n"
            f"VIN: <code>{escape(vin)}</code>\n\n"
            "Открыть каталог: /catalog\n"
            "Чтобы заменить авто: /garage_add"
        )
        return
    await state.set_state(Garage.brand)
    await message.answer("Марка? Например: BMW")


@dp.message(Command("garage_add"))
async def garage_add(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Garage.brand)
    await message.answer("Марка?")


@dp.message(Garage.brand)
async def garage_brand(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer("Введите марку текстом.")
        return
    await state.update_data(brand=value)
    await state.set_state(Garage.model)
    await message.answer("Модель? Например: X3 G01")


@dp.message(Garage.model)
async def garage_model(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите модель.")
        return
    await state.update_data(model=value)
    await state.set_state(Garage.year)
    await message.answer("Год выпуска?")


@dp.message(Garage.year)
async def garage_year(message: Message, state: FSMContext):
    try:
        year = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите год числом.")
        return
    if not 1950 <= year <= 2030:
        await message.answer("Проверьте год.")
        return
    await state.update_data(year=year)
    await state.set_state(Garage.vin)
    await message.answer("VIN (17 символов) или - чтобы пропустить.")


@dp.message(Garage.vin)
async def garage_vin(message: Message, state: FSMContext):
    raw = (message.text or "").strip().upper()
    vin = None if raw == "-" else raw
    if vin and len(vin) != 17:
        await message.answer("VIN должен содержать 17 символов, либо отправь -")
        return

    data = await state.get_data()
    vehicle = await save_vehicle(
        message.from_user.id,
        data["brand"],
        data["model"],
        data["year"],
        vin,
    )
    await state.clear()
    await message.answer(
        f"Сохранено: <b>{escape(vehicle.brand)} {escape(vehicle.model)}, {vehicle.year}</b>.\n"
        "Открыть каталог можно командой /catalog или просто написать нужную деталь."
    )


@dp.message(Command("catalog"))
async def catalog_command(message: Message, state: FSMContext):
    await state.clear()
    command_parts = (message.text or "").split(maxsplit=1)

    if len(command_parts) == 2 and command_parts[1].strip():
        parsed = parse_vehicle_text(command_parts[1])
        if parsed is None:
            await message.answer(
                "После /catalog укажите марку и модель, например:\n"
                "<code>/catalog BMW X3 G01</code>"
            )
            return
        brand, model = parsed
        await show_catalog_root(message, state, brand, model, None, None, "temporary")
        return

    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await message.answer(
            "В гараже пока нет автомобиля.\n\n"
            "Можно добавить его через /garage или сразу открыть общий каталог модели:\n"
            "<code>/catalog BMW X3 G01</code>"
        )
        return

    await show_catalog_root(
        message,
        state,
        vehicle.brand,
        vehicle.model,
        vehicle.year,
        vehicle.vin,
        "garage",
    )


@dp.callback_query(F.data.startswith("cat:"))
async def catalog_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    node_id = (callback.data or "").split(":", 1)[1]
    node = get_node(node_id)
    if node is None:
        await callback.message.answer("Раздел каталога не найден.")
        return

    vehicle, source = await get_catalog_vehicle(state, callback.from_user.id)
    if vehicle is None:
        await callback.message.answer("Сначала выберите автомобиль через /catalog или /garage.")
        return

    year = vehicle.year or None
    vehicle_title = catalog_context_title(vehicle.brand, vehicle.model, year)

    if node.children:
        await callback.message.edit_text(
            f"<b>{vehicle_title}</b>\n"
            f"Раздел: <b>{escape(node.title)}</b>\n\n"
            "Выберите подгруппу:",
            reply_markup=catalog_keyboard(node.id),
        )
        return

    if not node.query:
        await callback.message.edit_text(
            "Для этого раздела пока нет поискового запроса.",
            reply_markup=leaf_keyboard(node.parent),
        )
        return

    offers = []
    for provider in providers:
        offers.extend(await provider.search(vehicle, node.query))
    ranked = rank_offers(offers)

    if not ranked:
        body = "Предложений пока нет."
    else:
        body = (
            offer_text("Лучший баланс", ranked["best"]) + "\n\n"
            + offer_text("Самый дешёвый", ranked["cheapest"]) + "\n\n"
            + offer_text("Самый быстрый", ranked["fastest"])
        )

    compatibility_note = (
        "Общий каталог модели: точная совместимость пока не подтверждена."
        if source == "temporary"
        else "Данные демонстрационные; проверку применимости по VIN подключим следующим этапом."
    )

    await callback.message.edit_text(
        f"<b>{vehicle_title}</b>\n"
        f"Категория: <b>{escape(node.title)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{compatibility_note}</i>",
        reply_markup=leaf_keyboard(node.parent),
    )


def offer_text(label, offer):
    return (
        f"<b>{label}</b>\n"
        f"{escape(offer.brand)} · <code>{escape(offer.article)}</code>\n"
        f"{offer.price:,.0f} ₽ · {offer.delivery_days} дн. · {escape(offer.provider)}"
    ).replace(",", " ")


@dp.message(F.text)
async def search(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    parsed_vehicle = parse_vehicle_text(text)
    if parsed_vehicle is not None:
        await state.clear()
        brand, model = parsed_vehicle
        await show_catalog_root(message, state, brand, model, None, None, "temporary")
        return

    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await message.answer(
            "Не вижу сохранённого автомобиля.\n"
            "Добавь его через /garage или просто напиши марку и модель, например:\n"
            "<code>BMW X3 G01</code>"
        )
        return

    offers = []
    for provider in providers:
        offers.extend(await provider.search(vehicle, text))
    ranked = rank_offers(offers)
    if not ranked:
        await message.answer("Пока предложений нет.")
        return

    await message.answer(
        f"Запрос: <b>{escape(text)}</b>\n\n"
        + offer_text("Лучший баланс", ranked["best"]) + "\n\n"
        + offer_text("Самый дешёвый", ranked["cheapest"]) + "\n\n"
        + offer_text("Самый быстрый", ranked["fastest"]) + "\n\n"
        + "<i>Это демонстрационные данные.</i>"
    )


async def main():
    await init_db()
    bot = Bot(
        settings().bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
