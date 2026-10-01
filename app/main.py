import asyncio
from decimal import Decimal
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message

from app.catalog import get_node
from app.config import settings
from app.db import add_favorite, create_price_alert, delete_price_alert, delete_vehicle, get_search_history_item, get_vehicle, init_db, list_favorites, list_price_alerts, list_recent_searches, list_vehicles, record_search, remove_favorite, save_vehicle, set_active_vehicle, set_vehicle_modification, update_price_alert, update_vehicle_from_resolution
from app.domain import Vehicle
from app.external_fitment import GenericHttpFitmentCatalog, HttpFitmentConfig
from app.external_provider import GenericHttpProvider, HttpProviderConfig
from app.external_vehicle import GenericHttpVehicleResolver, HttpVehicleResolverConfig
from app.fitment import DemoFitmentCatalog
from app.price_alerts import check_all_price_alerts
from app.providers import AutodocProvider, ExistProvider, MockProvider
from app.query_parser import parse_search_query
from app.runtime import run_bot
from app.ui import (
    BTN_ADD_CAR,
    BTN_ALERTS,
    BTN_ARTICLE,
    BTN_CANCEL,
    BTN_CATALOG,
    BTN_FAVORITES,
    BTN_GARAGE,
    BTN_HISTORY,
    BTN_MODEL_CATALOG,
    BTN_SEARCH,
    BTN_SERVICE,
    built_kit_keyboard,
    built_kit_text,
    cancel_menu,
    catalog_keyboard,
    delete_vehicle_confirm_keyboard,
    favorites_keyboard,
    garage_keyboard,
    generation_keyboard,
    history_keyboard,
    main_menu,
    modification_keyboard,
    candidate_detail_text,
    candidate_text,
    part_detail_keyboard,
    parts_results_keyboard,
    price_alerts_keyboard,
    service_kits_keyboard,
    vehicle_modification_text,
    vehicle_summary,
)
from app.search_service import PartsSearchService, deserialize_candidate, serialize_candidate
from app.service_kits import build_service_kit, get_service_kit
from app.vehicle_catalog import find_generations, get_generation
from app.vehicle_parser import parse_vehicle_text
from app.vehicle_resolution import NullVehicleResolver, merge_vehicle_resolution
from app.vehicle_resolver import find_modifications, get_modification, vehicle_is_precise


class Garage(StatesGroup):
    brand = State()
    model = State()
    year = State()
    vin = State()


class SearchFlow(StatesGroup):
    query = State()


class CatalogFlow(StatesGroup):
    vehicle = State()


app_settings = settings()
providers = [ExistProvider(), AutodocProvider()]

if app_settings.demo_provider_enabled:
    providers.insert(0, MockProvider())

if app_settings.external_provider_enabled and app_settings.external_provider_base_url:
    providers.append(
        GenericHttpProvider(
            HttpProviderConfig(
                name=app_settings.external_provider_name,
                base_url=app_settings.external_provider_base_url,
                search_path=app_settings.external_provider_search_path,
                api_key=app_settings.external_provider_api_key,
                api_key_header=app_settings.external_provider_api_key_header,
                auth_scheme=app_settings.external_provider_auth_scheme,
                allow_http=app_settings.external_provider_allow_http,
            )
        )
    )

fitment_catalog = None
if app_settings.fitment_api_enabled and app_settings.fitment_api_base_url:
    fitment_catalog = GenericHttpFitmentCatalog(
        HttpFitmentConfig(
            base_url=app_settings.fitment_api_base_url,
            resolve_path=app_settings.fitment_api_resolve_path,
            api_key=app_settings.fitment_api_key,
            api_key_header=app_settings.fitment_api_key_header,
            auth_scheme=app_settings.fitment_api_auth_scheme,
            allow_http=app_settings.fitment_api_allow_http,
        )
    )
elif app_settings.demo_fitment_enabled:
    fitment_catalog = DemoFitmentCatalog()

search_service = PartsSearchService(
    providers,
    cache_ttl_seconds=app_settings.search_cache_ttl_seconds,
    provider_timeout_seconds=app_settings.provider_timeout_seconds,
    fitment_catalog=fitment_catalog,
)

vehicle_resolver = NullVehicleResolver()
if app_settings.vehicle_api_enabled and app_settings.vehicle_api_base_url:
    vehicle_resolver = GenericHttpVehicleResolver(
        HttpVehicleResolverConfig(
            base_url=app_settings.vehicle_api_base_url,
            vin_path=app_settings.vehicle_api_vin_path,
            api_key=app_settings.vehicle_api_key,
            api_key_header=app_settings.vehicle_api_key_header,
            auth_scheme=app_settings.vehicle_api_auth_scheme,
            allow_http=app_settings.vehicle_api_allow_http,
        )
    )

dp = Dispatcher()


async def set_catalog_context(
    state: FSMContext,
    brand: str,
    model: str,
    year: int | None,
    vin: str | None,
    source: str,
    vehicle_details: Vehicle | None = None,
) -> None:
    details = vehicle_details
    await state.update_data(
        catalog_vehicle={
            "brand": brand,
            "model": model,
            "year": year,
            "vin": vin,
            "source": source,
            "id": details.id if details else None,
            "generation_code": details.generation_code if details else None,
            "engine": details.engine if details else None,
            "fuel": details.fuel if details else None,
            "drive": details.drive if details else None,
            "power_hp": details.power_hp if details else None,
            "modification_key": details.modification_key if details else None,
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
                id=ctx.get("id"),
                generation_code=ctx.get("generation_code"),
                engine=ctx.get("engine"),
                fuel=ctx.get("fuel"),
                drive=ctx.get("drive"),
                power_hp=ctx.get("power_hp"),
                modification_key=ctx.get("modification_key"),
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
    saved_vehicle = await get_vehicle(message.from_user.id) if source == "garage" else None
    await set_catalog_context(
        state,
        brand,
        model,
        year,
        vin,
        source,
        vehicle_details=saved_vehicle,
    )
    year_text = f" · {year}" if year else ""
    note = (
        "Общий каталог модели. Перед покупкой конкретной детали нужно уточнить "
        "год, двигатель или VIN."
        if source == "temporary"
        else (
            "Модификация уточнена: применимость можно проверять по двигателю и приводу."
            if saved_vehicle and vehicle_is_precise(saved_vehicle)
            else "Модификация пока не уточнена. Для точной применимости выберите её в гараже."
        )
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


async def send_search_results(
    message: Message,
    state: FSMContext,
    vehicle: Vehicle | None,
    query: str,
    parent_id: str | None = None,
    compatibility_note: str | None = None,
) -> None:
    parsed_query = parse_search_query(query)
    recommended = await search_service.parts(vehicle, parsed_query.part_query)
    if not recommended:
        await message.answer(
            "По этому запросу предложений пока нет.",
            reply_markup=main_menu(vehicle is not None),
        )
        return

    candidates = list(recommended)
    sort_label = "рекомендуемые"
    if parsed_query.sort_mode == "price":
        candidates.sort(key=lambda item: (item.min_price, item.min_delivery_days))
        sort_label = "сначала дешевле"
    elif parsed_query.sort_mode == "speed":
        candidates.sort(key=lambda item: (item.min_delivery_days, item.min_price))
        sort_label = "сначала быстрее"

    visible = candidates[:5]
    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_parts_recommended=[
            serialize_candidate(item) for item in recommended[:20]
        ],
        last_query=parsed_query.raw,
        last_parent_id=parent_id,
        last_vehicle=(
            {
                "brand": vehicle.brand,
                "model": vehicle.model,
                "year": vehicle.year,
                "vin": vehicle.vin,
            }
            if vehicle
            else None
        ),
        last_compatibility_note=compatibility_note,
    )

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(index + 1, candidate)
        for index, candidate in enumerate(visible)
    )
    note = compatibility_note or "Данные и цены пока демонстрационные."

    await message.answer(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(parsed_query.raw)}</b>\n"
        f"Сортировка: <b>{escape(sort_label)}</b>\n"
        f"Найдено вариантов: <b>{len(candidates)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(visible, parent_id),
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
    vehicles = await list_vehicles(message.from_user.id)
    current = await get_vehicle(message.from_user.id)

    if vehicles and current:
        await message.answer(
            "<b>Мои автомобили</b>\n"
            f"Активный: {vehicle_modification_text(current)}\n\n"
            "Выберите другой автомобиль, уточните модификацию или добавьте новый.",
            reply_markup=garage_keyboard(vehicles, current.id),
        )
        return

    await state.set_state(Garage.brand)
    await message.answer("Марка автомобиля? Например: <code>BMW</code>", reply_markup=cancel_menu())


@dp.callback_query(F.data == "garage:add")
async def garage_add_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return
    await state.clear()
    await state.set_state(Garage.brand)
    await callback.message.answer(
        "Марка нового автомобиля? Например: <code>BMW</code>",
        reply_markup=cancel_menu(),
    )


@dp.callback_query(F.data.startswith("garage:set:"))
async def garage_set_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    vehicle_id = int((callback.data or "").rsplit(":", 1)[1])
    vehicle = await set_active_vehicle(callback.from_user.id, vehicle_id)
    if vehicle is None:
        await callback.message.answer("Автомобиль не найден.")
        return

    await state.clear()
    vehicles = await list_vehicles(callback.from_user.id)
    await callback.message.edit_text(
        f"Активный автомобиль:\n{vehicle_summary(vehicle)}",
        reply_markup=garage_keyboard(vehicles, vehicle.id),
    )


@dp.callback_query(F.data.startswith("garage:resolve:"))
async def garage_resolve_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    vehicle_id = int((callback.data or "").rsplit(":", 1)[1])
    vehicles = await list_vehicles(callback.from_user.id)
    vehicle = next((item for item in vehicles if item.id == vehicle_id), None)
    if vehicle is None:
        await callback.message.answer("Автомобиль не найден.")
        return

    modifications = find_modifications(vehicle)
    if not modifications:
        await callback.message.answer(
            "Для этой модели в demo-resolver пока нет списка модификаций. "
            "Позже этот шаг будет получать данные из внешнего каталога применимости."
        )
        return

    await callback.message.edit_text(
        f"{vehicle_summary(vehicle)}\n"
        f"Сейчас: <b>{vehicle_modification_text(vehicle)}</b>\n\n"
        "Выберите точную модификацию:",
        reply_markup=modification_keyboard(vehicle_id, modifications),
    )


@dp.callback_query(F.data.startswith("mod:"))
async def garage_modification_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    parts = (callback.data or "").split(":", 2)
    if len(parts) != 3:
        await callback.message.answer("Некорректная модификация.")
        return

    vehicle_id = int(parts[1])
    modification = get_modification(parts[2])
    if modification is None:
        await callback.message.answer("Модификация не найдена.")
        return

    vehicle = await set_vehicle_modification(
        callback.from_user.id,
        vehicle_id,
        generation_code=modification.generation_code,
        engine_code=modification.engine,
        fuel=modification.fuel,
        drive=modification.drive,
        power_hp=modification.power_hp,
        modification_key=modification.key,
    )
    if vehicle is None:
        await callback.message.answer("Автомобиль не найден.")
        return

    await state.clear()
    vehicles = await list_vehicles(callback.from_user.id)
    await callback.message.edit_text(
        f"Модификация сохранена.\n\n"
        f"{vehicle_summary(vehicle)}\n"
        f"<b>{vehicle_modification_text(vehicle)}</b>",
        reply_markup=garage_keyboard(vehicles, vehicle.id),
    )


@dp.callback_query(F.data.startswith("garage:delete:"))
async def garage_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    vehicle_id = int((callback.data or "").rsplit(":", 1)[1])
    await callback.message.edit_text(
        "Удалить активный автомобиль из гаража?",
        reply_markup=delete_vehicle_confirm_keyboard(vehicle_id),
    )


@dp.callback_query(F.data.startswith("garage:confirmdel:"))
async def garage_confirm_delete_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    vehicle_id = int((callback.data or "").rsplit(":", 1)[1])
    await delete_vehicle(callback.from_user.id, vehicle_id)
    await state.clear()

    vehicles = await list_vehicles(callback.from_user.id)
    current = await get_vehicle(callback.from_user.id)
    if not vehicles or current is None:
        await callback.message.edit_text("Гараж пуст.")
        await callback.message.answer(
            "Можно добавить автомобиль.",
            reply_markup=main_menu(False),
        )
        return

    await callback.message.edit_text(
        "<b>Мои автомобили</b>\nВыберите активный автомобиль:",
        reply_markup=garage_keyboard(vehicles, current.id),
    )


@dp.callback_query(F.data == "garage:canceldelete")
async def garage_cancel_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    vehicles = await list_vehicles(callback.from_user.id)
    current = await get_vehicle(callback.from_user.id)
    await callback.message.edit_text(
        "<b>Мои автомобили</b>\nВыберите активный автомобиль:",
        reply_markup=garage_keyboard(vehicles, current.id if current else None),
    )


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

    vin_note = ""
    if vin:
        resolution = await vehicle_resolver.resolve_vin(vin)
        if resolution.resolved:
            merged = merge_vehicle_resolution(vehicle, resolution)
            updated = await update_vehicle_from_resolution(
                message.from_user.id,
                merged,
            )
            if updated is not None:
                vehicle = updated
            vin_note = (
                f"\n\nVIN распознан: <b>{escape(resolution.source or 'внешний каталог')}</b>."
            )
        elif resolution.status != "unavailable":
            vin_note = f"\n\nVIN не уточнил модификацию: {escape(resolution.reason)}"

    await state.clear()

    modifications = find_modifications(vehicle)
    extra = (
        "\n\nДля этой модели найдено несколько модификаций. "
        "Откройте «Мой автомобиль» → «Уточнить модификацию»."
        if len(modifications) > 1 and not vehicle_is_precise(vehicle)
        else ""
    )
    await message.answer(
        "Автомобиль сохранён.\n\n"
        f"{vehicle_summary(vehicle)}\n"
        f"{vehicle_modification_text(vehicle)}"
        f"{vin_note}"
        f"{extra}\n\n"
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
        vehicle_details=vehicle,
    )
    await message.answer(
        f"{vehicle_summary(vehicle)}\n\n"
        "<b>ТО и обслуживание</b>\n"
        "Выберите готовый комплект или откройте отдельные позиции:",
        reply_markup=service_kits_keyboard(),
    )


@dp.callback_query(F.data == "action:kits")
async def service_kits_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    vehicle, _ = await get_catalog_vehicle(state, callback.from_user.id)
    if vehicle is None:
        await callback.message.answer("Сначала выберите автомобиль.")
        return

    await callback.message.edit_text(
        f"{vehicle_summary(vehicle)}\n\n"
        "<b>ТО и обслуживание</b>\n"
        "Выберите комплект:",
        reply_markup=service_kits_keyboard(),
    )


@dp.callback_query(F.data.startswith("kit:"))
async def service_kit_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    kit_id = (callback.data or "").split(":", 1)[1]
    kit = get_service_kit(kit_id)
    if kit is None:
        await callback.message.answer("Комплект не найден.")
        return

    vehicle, source = await get_catalog_vehicle(state, callback.from_user.id)
    if vehicle is None:
        await callback.message.answer("Сначала выберите автомобиль.")
        return

    built = await build_service_kit(search_service, vehicle, kit)
    note = (
        "Комплект демонстрационный. Совместимость по VIN пока не проверяется."
        if source == "garage"
        else "Комплект общий для модели; точную применимость нужно уточнить."
    )

    await callback.message.edit_text(
        f"{vehicle_summary(vehicle)}\n\n"
        f"{built_kit_text(built)}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=built_kit_keyboard(),
    )


@dp.message(F.text == BTN_HISTORY)
async def history_button(message: Message):
    items = await list_recent_searches(message.from_user.id)
    if not items:
        await message.answer(
            "История поиска пока пуста.",
            reply_markup=main_menu((await get_vehicle(message.from_user.id)) is not None),
        )
        return

    lines = ["<b>Последние запросы</b>", ""]
    for item in items:
        suffix = f" · {escape(item.vehicle_label)}" if item.vehicle_label else ""
        lines.append(f"• {escape(item.query)}{suffix}")

    await message.answer(
        "\n".join(lines),
        reply_markup=history_keyboard(items),
    )


@dp.callback_query(F.data.startswith("history:run:"))
async def history_run_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    history_id = int((callback.data or "").rsplit(":", 1)[1])
    item = await get_search_history_item(callback.from_user.id, history_id)
    if item is None:
        await callback.message.answer("Запрос в истории не найден.")
        return

    vehicle = await get_vehicle(callback.from_user.id)
    note = None if vehicle else "Совместимость с автомобилем не проверялась."
    await record_search(callback.from_user.id, item.query, vehicle)
    await send_search_results(
        callback.message,
        state,
        vehicle,
        item.query,
        compatibility_note=note,
    )


@dp.message(F.text == BTN_FAVORITES)
async def favorites_button(message: Message):
    items = await list_favorites(message.from_user.id)
    if not items:
        await message.answer(
            "Избранных деталей пока нет.",
            reply_markup=main_menu((await get_vehicle(message.from_user.id)) is not None),
        )
        return

    await message.answer(
        "<b>Избранные детали</b>\n"
        "Откройте деталь, чтобы снова проверить предложения.",
        reply_markup=favorites_keyboard(items),
    )


@dp.callback_query(F.data.startswith("favorite:add:"))
async def favorite_add_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    index = int((callback.data or "").rsplit(":", 1)[1])
    data = await state.get_data()
    items = data.get("last_parts") or []
    if index < 0 or index >= len(items):
        await callback.message.answer("Эта выдача устарела.")
        return

    candidate = deserialize_candidate(items[index])
    await add_favorite(
        callback.from_user.id,
        candidate.brand,
        candidate.article,
        candidate.title,
    )
    await callback.answer("Добавлено в избранное", show_alert=False)


@dp.callback_query(F.data.startswith("favorite:open:"))
async def favorite_open_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    favorite_id = int((callback.data or "").rsplit(":", 1)[1])
    items = await list_favorites(callback.from_user.id)
    favorite = next((item for item in items if item.id == favorite_id), None)
    if favorite is None:
        await callback.message.answer("Избранная деталь не найдена.")
        return

    vehicle = await get_vehicle(callback.from_user.id)
    note = None if vehicle else "Совместимость с автомобилем не проверялась."
    await record_search(callback.from_user.id, favorite.article, vehicle)
    await send_search_results(
        callback.message,
        state,
        vehicle,
        favorite.article,
        compatibility_note=note,
    )


@dp.callback_query(F.data.startswith("favorite:delete:"))
async def favorite_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    favorite_id = int((callback.data or "").rsplit(":", 1)[1])
    await remove_favorite(callback.from_user.id, favorite_id)
    items = await list_favorites(callback.from_user.id)

    if not items:
        await callback.message.edit_text("Избранных деталей больше нет.")
        return

    await callback.message.edit_text(
        "<b>Избранные детали</b>\n"
        "Откройте деталь, чтобы снова проверить предложения.",
        reply_markup=favorites_keyboard(items),
    )


@dp.message(F.text == BTN_ALERTS)
async def price_alerts_button(message: Message):
    alerts = await list_price_alerts(message.from_user.id)
    if not alerts:
        await message.answer(
            "Активных уведомлений о цене пока нет.\n"
            "Откройте карточку детали и нажмите «🔔 Следить».",
            reply_markup=main_menu((await get_vehicle(message.from_user.id)) is not None),
        )
        return

    await message.answer(
        "<b>Отслеживание цен</b>\n"
        "Бот уведомит, когда цена станет не выше указанного порога.",
        reply_markup=price_alerts_keyboard(alerts),
    )


@dp.callback_query(F.data.startswith("alert:add:"))
async def price_alert_add_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    index = int((callback.data or "").rsplit(":", 1)[1])
    data = await state.get_data()
    items = data.get("last_parts") or []
    if index < 0 or index >= len(items):
        await callback.answer("Эта выдача устарела", show_alert=True)
        return

    candidate = deserialize_candidate(items[index])
    vehicle, _ = await get_catalog_vehicle(state, callback.from_user.id)
    current_price = candidate.min_price
    drop = Decimal(str(app_settings.price_alert_drop_percent)) / Decimal("100")
    target_price = (current_price * (Decimal("1") - drop)).quantize(Decimal("1"))

    alert = await create_price_alert(
        callback.from_user.id,
        vehicle_id=vehicle.id if vehicle else None,
        brand=candidate.brand,
        article=candidate.article,
        title=candidate.title,
        target_price=target_price,
        last_price=current_price,
    )
    target = f"{alert.target_price:,.0f}".replace(",", " ")
    await callback.answer(
        f"Сообщу при цене ≤ {target} ₽",
        show_alert=True,
    )


@dp.callback_query(F.data.startswith("alert:delete:"))
async def price_alert_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    alert_id = int((callback.data or "").rsplit(":", 1)[1])
    await delete_price_alert(callback.from_user.id, alert_id)
    alerts = await list_price_alerts(callback.from_user.id)
    if not alerts:
        await callback.message.edit_text("Активных уведомлений о цене больше нет.")
        return

    await callback.message.edit_text(
        "<b>Отслеживание цен</b>\n"
        "Бот уведомит, когда цена станет не выше указанного порога.",
        reply_markup=price_alerts_keyboard(alerts),
    )


@dp.callback_query(F.data.startswith("alert:noop:"))
async def price_alert_noop_callback(callback: CallbackQuery):
    await callback.answer("Уведомление активно")


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
    await state.set_state(None)
    await state.update_data(search_without_vehicle=False)

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
    search_vehicle = None if without_vehicle else vehicle
    await record_search(message.from_user.id, query, search_vehicle)
    await send_search_results(
        message,
        state,
        search_vehicle,
        query,
        compatibility_note=note,
    )
    saved_vehicle = await get_vehicle(message.from_user.id)
    await message.answer("Что дальше?", reply_markup=main_menu(saved_vehicle is not None))


@dp.callback_query(F.data.startswith("sort:"))
async def sort_parts_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    mode = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    raw_items = data.get("last_parts_recommended") or data.get("last_parts") or []
    if not raw_items:
        await callback.message.answer("Эта выдача устарела. Выполните поиск ещё раз.")
        return

    candidates = [deserialize_candidate(item) for item in raw_items]
    if mode == "price":
        candidates.sort(key=lambda item: (item.min_price, item.min_delivery_days))
        sort_label = "сначала дешевле"
    elif mode == "speed":
        candidates.sort(key=lambda item: (item.min_delivery_days, item.min_price))
        sort_label = "сначала быстрее"
    else:
        sort_label = "рекомендуемые"

    visible = candidates[:5]
    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible]
    )

    query = data.get("last_query") or "запчасть"
    parent_id = data.get("last_parent_id")
    vehicle_data = data.get("last_vehicle")
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."

    vehicle = None
    if vehicle_data:
        vehicle = Vehicle(
            vehicle_data["brand"],
            vehicle_data["model"],
            vehicle_data["year"],
            vehicle_data.get("vin"),
        )

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(index + 1, candidate)
        for index, candidate in enumerate(visible)
    )

    await callback.message.edit_text(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n"
        f"Сортировка: <b>{escape(sort_label)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(visible, parent_id),
    )


@dp.callback_query(F.data.startswith("part:"))
async def part_detail_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    try:
        index = int((callback.data or "").split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.message.answer("Не удалось открыть карточку детали.")
        return

    data = await state.get_data()
    items = data.get("last_parts") or []
    if index < 0 or index >= len(items):
        await callback.message.answer("Эта выдача устарела. Выполните поиск ещё раз.")
        return

    candidate = deserialize_candidate(items[index])
    parent_id = data.get("last_parent_id")
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."

    await callback.message.edit_text(
        f"{candidate_detail_text(candidate)}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=part_detail_keyboard(index, parent_id),
    )


@dp.callback_query(F.data == "partlist:back")
async def part_list_back_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    data = await state.get_data()
    raw_items = data.get("last_parts") or []
    if not raw_items:
        await callback.message.answer("Эта выдача устарела. Выполните поиск ещё раз.")
        return

    candidates = [deserialize_candidate(item) for item in raw_items]
    query = data.get("last_query") or "запчасть"
    parent_id = data.get("last_parent_id")
    vehicle_data = data.get("last_vehicle")
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."

    vehicle = None
    if vehicle_data:
        vehicle = Vehicle(
            vehicle_data["brand"],
            vehicle_data["model"],
            vehicle_data["year"],
            vehicle_data.get("vin"),
        )

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(index + 1, candidate)
        for index, candidate in enumerate(candidates)
    )

    await callback.message.edit_text(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(candidates, parent_id),
    )


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

    candidates = await search_service.parts(vehicle, node.query)
    if not candidates:
        await callback.message.edit_text(
            "Предложений пока нет.",
            reply_markup=catalog_keyboard(node.parent or "root"),
        )
        return

    visible = candidates[:5]
    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_parts_recommended=[serialize_candidate(item) for item in visible],
        last_query=node.query,
        last_parent_id=node.parent,
        last_vehicle={
            "brand": vehicle.brand,
            "model": vehicle.model,
            "year": vehicle.year,
            "vin": vehicle.vin,
        },
        last_compatibility_note=compatibility_note,
    )

    body = "\n\n".join(
        candidate_text(index + 1, candidate)
        for index, candidate in enumerate(visible)
    )
    year_text = f" · {vehicle.year}" if vehicle.year else ""

    await callback.message.edit_text(
        f"🚗 <b>{escape(vehicle.brand)} {escape(vehicle.model)}</b>{year_text}\n"
        f"Категория: <b>{escape(node.title)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(compatibility_note)}</i>",
        reply_markup=parts_results_keyboard(visible, node.parent),
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
    await record_search(message.from_user.id, text, vehicle)
    await send_search_results(message, state, vehicle, text, compatibility_note=note)
    saved_vehicle = await get_vehicle(message.from_user.id)
    await message.answer("Что дальше?", reply_markup=main_menu(saved_vehicle is not None))


async def price_alert_worker(bot: Bot) -> None:
    interval = max(60, app_settings.price_alert_interval_seconds)
    while True:
        await asyncio.sleep(interval)
        try:
            hits = await check_all_price_alerts(search_service)
        except Exception:
            continue

        for hit in hits:
            price = f"{hit.current_price:,.0f}".replace(",", " ")
            target = f"{hit.alert.target_price:,.0f}".replace(",", " ")
            try:
                await bot.send_message(
                    hit.alert.telegram_user_id,
                    "<b>Цена снизилась</b>\n\n"
                    f"{escape(hit.alert.brand)} · "
                    f"<code>{escape(hit.alert.article)}</code>\n"
                    f"{escape(hit.alert.title)}\n\n"
                    f"Сейчас: <b>{price} ₽</b>\n"
                    f"Ваш порог: {target} ₽",
                )
                await update_price_alert(
                    hit.alert.id,
                    last_price=hit.current_price,
                    triggered=True,
                )
            except Exception:
                continue


async def main():
    await init_db()
    bot = Bot(
        app_settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="catalog", description="Каталог запчастей"),
            BotCommand(command="search", description="Найти запчасть"),
            BotCommand(command="garage", description="Мой автомобиль"),
            BotCommand(command="garage_add", description="Добавить автомобиль"),
        ]
    )
    alert_task = None
    if app_settings.price_alerts_enabled:
        alert_task = asyncio.create_task(price_alert_worker(bot))

    try:
        await run_bot(bot, dp, app_settings)
    finally:
        if alert_task is not None:
            alert_task.cancel()
            try:
                await alert_task
            except asyncio.CancelledError:
                pass


if __name__ == "__main__":
    asyncio.run(main())
