import asyncio
from html import escape

from aiogram import Bot, CallbackQuery, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, Message

from app.catalog import get_node
from app.config import settings
from app.db import get_vehicle, init_db, save_vehicle
from app.domain import Vehicle
from app.providers import AutodocProvider, ExistProvider, MockProvider
from app.ui import (
    BTN_ADD_CAR,
    BTN_ARTICLE,
    BTN_CANCEL,
    BTN_CATALOG,
    BTN_GARAGE,
    BTN_MODEL_CATALOG,
    BTN_SEARCH,
    BTN_SERVICE,
    cancel_menu,
    catalog_keyboard,
    generation_keyboard,
    main_menu,
    candidate_detail_text,
    candidate_text,
    part_detail_keyboard,
    parts_results_keyboard,
    results_keyboard,
    vehicle_summary,
)
from app.search_service import PartsSearchService, deserialize_candidate, serialize_candidate
from app.vehicle_catalog import find_generations, get_generation
from app.vehicle_parser import parse_vehicle_text


class Garage(StatesGroup):
    brand = State()
    model = State()
    year = State()
    vin = State()


class SearchFlow(StatesGroup):
    query = State()


class CatalogFlow(StatesGroup):
    vehicle = State()


providers = [MockProvider(), ExistProvider(), AutodocProvider()]
search_service = PartsSearchService(providers)
dp = Dispatcher()


async def set_catalog_context(
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


async def get_catalog_vehicle(
    state: FSMContext,
    user_id: int,
) -> tuple[Vehicle | None, str]:
    data = await state.get_data()
    ctx = data.get("catalog_vehicle")
    if ctx:
        return (
            Vehicle(
                brand=ctx["brand"],
                model=ctx["model"],
                year=ctx.get("year") or 0,
                vin=ctx.get("vin"),
            ),
            ctx.get("source", "temporary"),
        )

    vehicle = await get_vehicle(user_id)
    return vehicle, "garage" if vehicle else "none"


async def show_catalog_root(
    message: Message,
    state: FSMContext,
    brand: str,
    model: str,
    year: int | None,
    vin: str | None,
    source: str,
) -> None:
    await set_catalog_context(state, brand, model, year, vin, source)
    year_text = f" · {year}" if year else ""
    note = (
        "Общий каталог модели. Перед покупкой конкретной детали нужно уточнить "
        "год, двигатель или VIN."
        if source == "temporary"
        else "Каталог пока демонстрационный. Точную применимость по VIN подключим следующим этапом."
    )

    await message.answer(
        f"🚗 <b>{escape(brand)} {escape(model)}</b>{year_text}\n\n"
        "<b>Каталог запчастей</b>\n"
        "Выберите раздел:",
        reply_markup=catalog_keyboard("root"),
    )
    await message.answer(
        f"<i>{note}</i>",
        reply_markup=main_menu(source == "garage"),
    )


async def open_model_catalog(
    message: Message,
    state: FSMContext,
    brand: str,
    model: str,
) -> None:
    generations = find_generations(brand, model)
    await state.clear()

    if len(generations) > 1:
        await message.answer(
            f"Нашёл несколько поколений <b>{escape(brand)} {escape(model)}</b>.\n"
            "Выберите нужное:",
            reply_markup=generation_keyboard(generations),
        )
        return

    await show_catalog_root(message, state, brand, model, None, None, "temporary")


async def open_catalog_for_saved_vehicle(message: Message, state: FSMContext) -> None:
    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await state.set_state(CatalogFlow.vehicle)
        await message.answer(
            "Напишите марку и модель автомобиля.\n"
            "Например: <code>BMW X3 G01</code>",
            reply_markup=cancel_menu(),
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


async def search_offers(vehicle: Vehicle | None, query: str):
    provider_vehicle = vehicle or Vehicle("Автомобиль", "не выбран", 0, None)
    offers = []
    for provider in providers:
        offers.extend(await provider.search(provider_vehicle, query))
    return rank_offers(offers)


async def send_search_results(
    message: Message,
    vehicle: Vehicle | None,
    query: str,
    parent_id: str | None = None,
    compatibility_note: str | None = None,
) -> None:
    ranked = await search_offers(vehicle, query)
    if not ranked:
        await message.answer(
            "По этому запросу предложений пока нет.",
            reply_markup=main_menu(vehicle is not None),
        )
        return

    body = (
        offer_text("⭐ Лучший баланс", ranked["best"]) + "\n\n"
        + offer_text("💰 Самый дешёвый", ranked["cheapest"]) + "\n\n"
        + offer_text("🚚 Самый быстрый", ranked["fastest"])
    )
    note = compatibility_note or "Данные и цены пока демонстрационные."

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    await message.answer(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=results_keyboard(parent_id),
    )


async def start_search(
    message: Message,
    state: FSMContext,
    article_only: bool = False,
    user_id: int | None = None,
) -> None:
    resolved_user_id = user_id if user_id is not None else message.from_user.id
    vehicle, _ = await get_catalog_vehicle(state, resolved_user_id)
    if vehicle is None and not article_only:
        await message.answer(
            "Сначала выберите автомобиль. Можно добавить его в гараж или открыть каталог по модели.",
            reply_markup=main_menu(False),
        )
        return

    if vehicle is None and article_only:
        await state.update_data(search_without_vehicle=True)

    await state.set_state(SearchFlow.query)
    prompt = (
        "Введите артикул детали.\nНапример: <code>GDB1956</code>"
        if article_only
        else "Что нужно найти?\nНапример: <code>передние колодки</code> или <code>масляный фильтр</code>"
    )
    await message.answer(prompt, reply_markup=cancel_menu())


@dp.message(CommandStart())
@dp.message(Command("menu"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    vehicle = await get_vehicle(message.from_user.id)

    if vehicle:
        await message.answer(
            "<b>Zap — подбор автозапчастей</b>\n\n"
            f"{vehicle_summary(vehicle)}\n\n"
            "Выберите действие или просто напишите название детали.",
            reply_markup=main_menu(True),
        )
    else:
        await message.answer(
            "<b>Zap — подбор автозапчастей</b>\n\n"
            "Добавьте автомобиль, откройте каталог по модели "
            "или найдите деталь по известному артикулу.",
            reply_markup=main_menu(False),
        )


@dp.message(F.text == BTN_CANCEL)
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    vehicle = await get_vehicle(message.from_user.id)
    await message.answer(
        "Отменено.",
        reply_markup=main_menu(vehicle is not None),
    )


@dp.message(Command("garage"))
@dp.message(F.text == BTN_GARAGE)
async def garage(message: Message, state: FSMContext):
    current = await get_vehicle(message.from_user.id)
    if current:
        vin = f"…{current.vin[-4:]}" if current.vin else "не указан"
        await message.answer(
            f"{vehicle_summary(current)}\n"
            f"VIN: <code>{escape(vin)}</code>\n\n"
            "Чтобы заменить автомобиль, используйте /garage_add.",
            reply_markup=main_menu(True),
        )
        return

    await state.set_state(Garage.brand)
    await message.answer("Марка автомобиля? Например: <code>BMW</code>", reply_markup=cancel_menu())


@dp.message(Command("garage_add"))
@dp.message(F.text == BTN_ADD_CAR)
async def garage_add(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(Garage.brand)
    await message.answer("Марка автомобиля? Например: <code>BMW</code>", reply_markup=cancel_menu())


@dp.message(Garage.brand)
async def garage_brand(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if len(value) < 2:
        await message.answer("Введите марку текстом.")
        return
    await state.update_data(brand=value)
    await state.set_state(Garage.model)
    await message.answer("Модель? Например: <code>X3 G01</code>")


@dp.message(Garage.model)
async def garage_model(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите модель автомобиля.")
        return
    await state.update_data(model=value)
    await state.set_state(Garage.year)
    await message.answer("Год выпуска? Например: <code>2020</code>")


@dp.message(Garage.year)
async def garage_year(message: Message, state: FSMContext):
    try:
        year = int((message.text or "").strip())
    except ValueError:
        await message.answer("Введите год числом.")
        return

    if not 1950 <= year <= 2030:
        await message.answer("Проверьте год выпуска.")
        return

    await state.update_data(year=year)
    await state.set_state(Garage.vin)
    await message.answer(
        "VIN из 17 символов. Если пока не хотите указывать VIN — отправьте <code>-</code>."
    )


@dp.message(Garage.vin)
async def garage_vin(message: Message, state: FSMContext):
    raw = (message.text or "").strip().upper()
    vin = None if raw == "-" else raw

    if vin and len(vin) != 17:
        await message.answer("VIN должен содержать 17 символов. Либо отправьте <code>-</code>.")
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
        "Автомобиль сохранён.\n\n"
        f"{vehicle_summary(vehicle)}\n\n"
        "Теперь можно открыть каталог или сразу написать нужную деталь.",
        reply_markup=main_menu(True),
    )


@dp.message(Command("catalog"))
@dp.message(F.text == BTN_CATALOG)
async def catalog_command(message: Message, state: FSMContext):
    if (message.text or "").startswith("/catalog "):
        await state.clear()
        raw = (message.text or "").split(maxsplit=1)[1]
        parsed = parse_vehicle_text(raw)
        if parsed is None:
            await message.answer(
                "Укажите марку и модель, например: <code>/catalog BMW X3 G01</code>"
            )
            return
        brand, model = parsed
        await open_model_catalog(message, state, brand, model)
        return

    await open_catalog_for_saved_vehicle(message, state)


@dp.message(F.text == BTN_MODEL_CATALOG)
async def catalog_by_model_button(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CatalogFlow.vehicle)
    await message.answer(
        "Напишите марку и модель.\nНапример: <code>BMW X3 G01</code>",
        reply_markup=cancel_menu(),
    )


@dp.message(CatalogFlow.vehicle)
async def catalog_vehicle_input(message: Message, state: FSMContext):
    parsed = parse_vehicle_text(message.text or "")
    if parsed is None:
        await message.answer(
            "Не удалось распознать автомобиль. Попробуйте в формате "
            "<code>BMW X3 G01</code> или <code>Toyota Camry XV70</code>."
        )
        return

    brand, model = parsed
    await open_model_catalog(message, state, brand, model)


@dp.message(F.text == BTN_SERVICE)
async def service_shortcut(message: Message, state: FSMContext):
    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await message.answer("Сначала добавьте автомобиль.", reply_markup=main_menu(False))
        return

    await set_catalog_context(
        state,
        vehicle.brand,
        vehicle.model,
        vehicle.year,
        vehicle.vin,
        "garage",
    )
    node = get_node("service")
    await message.answer(
        f"{vehicle_summary(vehicle)}\n\n"
        f"<b>{escape(node.title)}</b>\nВыберите позицию:",
        reply_markup=catalog_keyboard("service"),
    )


@dp.message(Command("search"))
@dp.message(F.text == BTN_SEARCH)
async def search_button(message: Message, state: FSMContext):
    await start_search(message, state)


@dp.message(F.text == BTN_ARTICLE)
async def article_button(message: Message, state: FSMContext):
    await start_search(message, state, article_only=True)


@dp.message(SearchFlow.query)
async def search_query(message: Message, state: FSMContext):
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите название детали или артикул.")
        return

    search_data = await state.get_data()
    vehicle, source = await get_catalog_vehicle(state, message.from_user.id)
    without_vehicle = bool(search_data.get("search_without_vehicle"))
    await state.clear()

    if vehicle is None and not without_vehicle:
        await message.answer("Автомобиль не найден.", reply_markup=main_menu(False))
        return

    note = (
        "Совместимость с автомобилем не проверялась."
        if without_vehicle
        else (
            "Общий каталог модели: точная совместимость пока не подтверждена."
            if source == "temporary"
            else None
        )
    )
    await send_search_results(
        message,
        None if without_vehicle else vehicle,
        query,
        compatibility_note=note,
    )
    saved_vehicle = await get_vehicle(message.from_user.id)
    await message.answer("Что дальше?", reply_markup=main_menu(saved_vehicle is not None))


@dp.callback_query(F.data == "action:search")
async def callback_new_search(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message:
        vehicle, _ = await get_catalog_vehicle(state, callback.from_user.id)
        await start_search(
            callback.message,
            state,
            article_only=vehicle is None,
            user_id=callback.from_user.id,
        )


@dp.callback_query(F.data.startswith("vehgen:"))
async def vehicle_generation_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    key = (callback.data or "").split(":", 1)[1]
    generation = get_generation(key)
    if generation is None:
        await callback.message.answer("Поколение автомобиля не найдено.")
        return

    await state.clear()
    await show_catalog_root(
        callback.message,
        state,
        generation.brand,
        generation.display_model,
        None,
        None,
        "temporary",
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
        await callback.message.answer("Сначала выберите автомобиль.", reply_markup=main_menu(False))
        return

    if node.children:
        year_text = f" · {vehicle.year}" if vehicle.year else ""
        await callback.message.edit_text(
            f"🚗 <b>{escape(vehicle.brand)} {escape(vehicle.model)}</b>{year_text}\n\n"
            f"<b>{escape(node.title)}</b>\n"
            "Выберите подгруппу:",
            reply_markup=catalog_keyboard(node.id),
        )
        return

    if not node.query:
        await callback.message.answer("Для этого раздела пока нет поискового запроса.")
        return

    compatibility_note = (
        "Общий каталог модели: точная совместимость пока не подтверждена."
        if source == "temporary"
        else "Применимость пока демонстрационная; в следующем этапе подключим проверку по VIN."
    )

    ranked = await search_offers(vehicle, node.query)
    if not ranked:
        await callback.message.edit_text(
            "Предложений пока нет.",
            reply_markup=results_keyboard(node.parent),
        )
        return

    body = (
        offer_text("⭐ Лучший баланс", ranked["best"]) + "\n\n"
        + offer_text("💰 Самый дешёвый", ranked["cheapest"]) + "\n\n"
        + offer_text("🚚 Самый быстрый", ranked["fastest"])
    )
    year_text = f" · {vehicle.year}" if vehicle.year else ""

    await callback.message.edit_text(
        f"🚗 <b>{escape(vehicle.brand)} {escape(vehicle.model)}</b>{year_text}\n"
        f"Категория: <b>{escape(node.title)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(compatibility_note)}</i>",
        reply_markup=results_keyboard(node.parent),
    )


@dp.message(F.text)
async def free_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return

    parsed_vehicle = parse_vehicle_text(text)
    if parsed_vehicle is not None:
        brand, model = parsed_vehicle
        await open_model_catalog(message, state, brand, model)
        return

    vehicle, source = await get_catalog_vehicle(state, message.from_user.id)
    if vehicle is None:
        await message.answer(
            "Сначала укажите автомобиль или откройте каталог по модели.",
            reply_markup=main_menu(False),
        )
        return

    note = (
        "Общий каталог модели: точная совместимость пока не подтверждена."
        if source == "temporary"
        else None
    )
    await send_search_results(message, vehicle, text, compatibility_note=note)
    saved_vehicle = await get_vehicle(message.from_user.id)
    await message.answer("Что дальше?", reply_markup=main_menu(saved_vehicle is not None))


async def main():
    await init_db()
    bot = Bot(
        settings().bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="catalog", description="Каталог запчастей"),
            BotCommand(command="search", description="Найти запчасть"),
            BotCommand(command="garage", description="Мой автомобиль"),
            BotCommand(command="garage_add", description="Добавить или заменить автомобиль"),
        ]
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
