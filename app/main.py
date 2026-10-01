import asyncio
import logging
from decimal import Decimal
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BotCommand, CallbackQuery, Message

from app.bootstrap import build_app_services
from app.catalog import get_node
from app.config import settings
from app.db import add_favorite, add_shopping_item, change_shopping_quantity, clear_shopping_list, create_price_alert, delete_price_alert, delete_purchase_quote, delete_vehicle, get_purchase_quote, get_search_history_item, get_vehicle, get_vehicle_by_id, init_db, list_favorites, list_price_alerts, list_price_history, list_purchase_quotes, list_recent_searches, list_shopping_items, list_vehicles, record_price_observations, record_search, remove_favorite, remove_shopping_item, save_purchase_quote, save_vehicle, set_active_vehicle, set_vehicle_modification, update_vehicle_from_resolution
from app.domain import Vehicle
from app.alert_worker import price_alert_loop
from app.health import readiness
from app.middleware import RateLimitMiddleware
from app.observability import configure_logging, log_event
from app.commercial_rules import parse_provider_rules
from app.price_history import summarize_price_history
from app.procurement import PurchaseRequest, compare_purchase_plans, deserialize_purchase_plan, optimize_purchase, requests_from_plan, serialize_purchase_plan
from app.query_parser import parse_search_query
from app.rate_limit import build_rate_limiter
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
    BTN_QUOTES,
    BTN_SEARCH,
    BTN_SERVICE,
    BTN_SHOPPING,
    BTN_WORKS,
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
    price_alert_target_keyboard,
    price_alerts_keyboard,
    quote_refresh_keyboard,
    quotes_keyboard,
    purchase_comparison_text,
    purchase_plan_keyboard,
    purchase_plan_text,
    purchase_plans_keyboard,
    saved_quote_keyboard,
    service_kits_keyboard,
    shopping_list_keyboard,
    shopping_list_text,
    vehicle_modification_text,
    vehicle_summary,
    work_packages_keyboard,
)
from app.search_service import deserialize_candidate, serialize_candidate
from app.service_kits import build_service_kit, get_service_kit
from app.vehicle_catalog import find_generations, get_generation
from app.vehicle_parser import parse_vehicle_text
from app.vehicle_resolution import merge_vehicle_resolution
from app.vehicle_resolver import find_modifications, get_modification, vehicle_is_precise
from app.work_orders import WorkPart, get_work_package, parse_work_text


class Garage(StatesGroup):
    brand = State()
    model = State()
    year = State()
    vin = State()


class SearchFlow(StatesGroup):
    query = State()


class CatalogFlow(StatesGroup):
    vehicle = State()


class WorkFlow(StatesGroup):
    text = State()


app_settings = settings()
configure_logging(app_settings.log_level)
logger = logging.getLogger("zap.main")

services = build_app_services(app_settings)
providers = services.providers
fitment_catalog = services.fitment_catalog
search_service = services.search_service
vehicle_resolver = services.vehicle_resolver
provider_commercial_rules = parse_provider_rules(
    app_settings.procurement_provider_rules_json
)

dp = Dispatcher()

rate_limiter = build_rate_limiter(
    app_settings.rate_limit_backend,
    limit=app_settings.rate_limit_requests,
    window_seconds=app_settings.rate_limit_window_seconds,
    redis_url=app_settings.redis_url,
)
dp.message.middleware(RateLimitMiddleware(rate_limiter))
dp.callback_query.middleware(RateLimitMiddleware(rate_limiter))


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


def sort_part_candidates(candidates, mode: str):
    ordered = list(candidates)
    if mode == "price":
        ordered.sort(key=lambda item: (item.min_price, item.min_delivery_days))
        return ordered, "сначала дешевле"
    if mode == "speed":
        ordered.sort(key=lambda item: (item.min_delivery_days, item.min_price))
        return ordered, "сначала быстрее"
    return ordered, "рекомендуемые"


def vehicle_state_payload(vehicle: Vehicle | None):
    if vehicle is None:
        return None
    return {
        "brand": vehicle.brand,
        "model": vehicle.model,
        "year": vehicle.year,
        "vin": vehicle.vin,
        "id": vehicle.id,
        "generation_code": vehicle.generation_code,
        "engine": vehicle.engine,
        "fuel": vehicle.fuel,
        "drive": vehicle.drive,
        "power_hp": vehicle.power_hp,
        "modification_key": vehicle.modification_key,
    }


def vehicle_from_state(payload):
    if not payload:
        return None
    return Vehicle(
        brand=payload["brand"],
        model=payload["model"],
        year=payload["year"],
        vin=payload.get("vin"),
        id=payload.get("id"),
        generation_code=payload.get("generation_code"),
        engine=payload.get("engine"),
        fuel=payload.get("fuel"),
        drive=payload.get("drive"),
        power_hp=payload.get("power_hp"),
        modification_key=payload.get("modification_key"),
    )


async def record_candidate_prices(candidates) -> None:
    offers = [
        offer
        for candidate in candidates
        for offer in candidate.offers
        if offer.in_stock
    ]
    if offers:
        try:
            await record_price_observations(offers)
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "price_history_write_failed",
                "failed to persist price observations",
                error=type(exc).__name__,
                offers=len(offers),
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
    if recommended:
        await record_candidate_prices(recommended)
    if not recommended:
        await message.answer(
            "По этому запросу предложений пока нет.",
            reply_markup=main_menu(vehicle is not None),
        )
        return

    stored = list(recommended[:20])
    candidates, sort_label = sort_part_candidates(stored, parsed_query.sort_mode)
    visible = candidates[:5]

    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_parts_recommended=[serialize_candidate(item) for item in stored],
        last_query=parsed_query.raw,
        last_parent_id=parent_id,
        last_vehicle=vehicle_state_payload(vehicle),
        last_compatibility_note=compatibility_note,
        last_sort_mode=parsed_query.sort_mode,
        last_page=0,
        last_total_found=len(recommended),
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
        f"Найдено вариантов: <b>{len(recommended)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(
            visible,
            parent_id,
            page=0,
            total_count=len(candidates),
        ),
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


@dp.message(Command("status"))
async def provider_status_command(message: Message):
    icons = {
        "healthy": "✅",
        "degraded": "🟡",
        "open": "🔴",
    }
    ready, infra = await readiness(app_settings)
    db_status = infra["database"]["status"]
    redis_status = infra["redis"]["status"]

    lines = [
        "<b>Состояние Zap</b>",
        "",
        f"{'✅' if ready else '🔴'} infrastructure — "
        f"DB {escape(str(db_status))} · Redis {escape(str(redis_status))}",
        f"cache: <code>{escape(app_settings.search_cache_backend)}</code> · "
        f"worker: <code>{escape(app_settings.price_alert_worker_mode)}</code>",
        "",
        "<b>Источники</b>",
        "",
    ]
    for item in search_service.provider_statuses():
        state = str(item["state"])
        latency = item["last_latency_ms"]
        latency_text = f"{latency} мс" if latency is not None else "нет данных"
        retry = item["retry_after_seconds"]
        retry_text = f" · retry {retry} сек." if state == "open" else ""
        lines.append(
            f"{icons.get(state, '⚪')} <b>{escape(str(item['name']))}</b> — "
            f"{escape(state)} · {latency_text}{retry_text}\n"
            f"успехов {item['successes']} · ошибок {item['failures']}"
        )

    await message.answer("\n".join(lines))


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


async def _add_work_parts_to_shopping(
    user_id: int,
    vehicle: Vehicle,
    parts: list[WorkPart] | tuple[WorkPart, ...],
) -> tuple[list[str], list[str]]:
    added: list[str] = []
    missing: list[str] = []

    searches = await asyncio.gather(
        *(search_service.parts(vehicle, item.query) for item in parts)
    )
    for work_part, candidates in zip(parts, searches, strict=True):
        if not candidates:
            missing.append(work_part.label or work_part.query)
            continue

        candidate = candidates[0]
        await add_shopping_item(
            user_id,
            vehicle_id=vehicle.id,
            brand=candidate.brand,
            article=candidate.article,
            title=candidate.title,
            quantity=work_part.quantity,
        )
        added.append(
            f"{work_part.label or candidate.title}: "
            f"{candidate.brand} {candidate.article} × {work_part.quantity}"
        )

    return added, missing


@dp.message(Command("works"))
@dp.message(F.text == BTN_WORKS)
async def works_button(message: Message, state: FSMContext):
    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await message.answer(
            "Для подбора по работам сначала добавьте автомобиль.",
            reply_markup=main_menu(False),
        )
        return

    await state.clear()
    await message.answer(
        f"{vehicle_summary(vehicle)}\n\n"
        "<b>Что планируем делать?</b>\n"
        "Выберите типовой пакет или напишите свой список работ.",
        reply_markup=work_packages_keyboard(),
    )


@dp.callback_query(F.data.startswith("work:pkg:"))
async def work_package_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    package_id = (callback.data or "").rsplit(":", 1)[1]
    package = get_work_package(package_id)
    if package is None:
        await callback.message.answer("Пакет работ не найден.")
        return

    vehicle = await get_vehicle(callback.from_user.id)
    if vehicle is None:
        await callback.message.answer("Сначала добавьте автомобиль.")
        return

    added, missing = await _add_work_parts_to_shopping(
        callback.from_user.id,
        vehicle,
        package.parts,
    )
    items = await list_shopping_items(callback.from_user.id)

    lines = [
        f"<b>{escape(package.title)}</b>",
        escape(package.description),
        "",
        f"Добавлено позиций: <b>{len(added)}</b>",
    ]
    if added:
        lines.extend([""] + [f"• {escape(item)}" for item in added])
    if missing:
        lines.extend([
            "",
            "Не удалось подобрать: " + ", ".join(escape(item) for item in missing),
        ])
    lines.extend(["", "Позиции добавлены в список закупки."])

    await state.clear()
    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=shopping_list_keyboard(items),
    )


@dp.callback_query(F.data == "work:custom")
async def custom_work_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    vehicle = await get_vehicle(callback.from_user.id)
    if vehicle is None:
        await callback.message.answer("Сначала добавьте автомобиль.")
        return

    await state.set_state(WorkFlow.text)
    await callback.message.answer(
        "Напишите список работ одной фразой. Например:\n"
        "<code>замена масла, салонный фильтр, передние тормоза</code>",
        reply_markup=cancel_menu(),
    )


@dp.message(WorkFlow.text, F.text)
async def custom_work_text(message: Message, state: FSMContext):
    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await state.clear()
        await message.answer("Автомобиль не найден.", reply_markup=main_menu(False))
        return

    parts = parse_work_text(message.text or "")
    if not parts:
        await message.answer(
            "Не смог разложить этот список на известные позиции. "
            "Попробуйте, например: <code>замена масла, передние тормоза</code>."
        )
        return

    added, missing = await _add_work_parts_to_shopping(
        message.from_user.id,
        vehicle,
        parts,
    )
    items = await list_shopping_items(message.from_user.id)
    await state.clear()

    lines = [
        "<b>Список работ разобран</b>",
        f"Добавлено позиций: <b>{len(added)}</b>",
    ]
    if added:
        lines.extend([""] + [f"• {escape(item)}" for item in added])
    if missing:
        lines.extend([
            "",
            "Не удалось подобрать: " + ", ".join(escape(item) for item in missing),
        ])

    await message.answer(
        "\n".join(lines),
        reply_markup=shopping_list_keyboard(items),
    )


def _article_key(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


async def _refresh_shopping_candidate(item):
    vehicle = None
    if item.vehicle_id is not None:
        vehicle = await get_vehicle_by_id(item.telegram_user_id, item.vehicle_id)
    if vehicle is None:
        vehicle = await get_vehicle(item.telegram_user_id)

    candidates = await search_service.parts(vehicle, item.article)
    if candidates:
        await record_candidate_prices(candidates)
    requested_article = _article_key(item.article)
    requested_brand = item.brand.casefold()

    exact = next(
        (
            candidate
            for candidate in candidates
            if _article_key(candidate.article) == requested_article
            and candidate.brand.casefold() == requested_brand
        ),
        None,
    )
    if exact is not None:
        return exact

    return next(
        (
            candidate
            for candidate in candidates
            if _article_key(candidate.article) == requested_article
        ),
        None,
    )


async def show_shopping_list(message: Message, user_id: int) -> None:
    items = await list_shopping_items(user_id)
    await message.answer(
        shopping_list_text(items),
        reply_markup=shopping_list_keyboard(items),
    )


@dp.message(Command("shopping"))
@dp.message(F.text == BTN_SHOPPING)
async def shopping_list_button(message: Message):
    await show_shopping_list(message, message.from_user.id)


@dp.callback_query(F.data.startswith("shop:add:"))
async def shopping_add_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    try:
        index = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректная позиция", show_alert=True)
        return

    data = await state.get_data()
    raw_items = data.get("last_parts") or []
    if index < 0 or index >= len(raw_items):
        await callback.answer("Эта выдача устарела", show_alert=True)
        return

    candidate = deserialize_candidate(raw_items[index])
    vehicle = vehicle_from_state(data.get("last_vehicle"))
    if vehicle is None:
        vehicle, _ = await get_catalog_vehicle(state, callback.from_user.id)

    item = await add_shopping_item(
        callback.from_user.id,
        vehicle_id=vehicle.id if vehicle else None,
        brand=candidate.brand,
        article=candidate.article,
        title=candidate.title,
        quantity=1,
    )
    await callback.answer(
        f"В закупке: {item.brand} {item.article} × {item.quantity}",
        show_alert=False,
    )


@dp.callback_query(F.data.startswith("shop:qty:"))
async def shopping_quantity_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        return
    try:
        item_id = int(parts[2])
        delta = int(parts[3])
    except ValueError:
        return

    await change_shopping_quantity(callback.from_user.id, item_id, delta)
    items = await list_shopping_items(callback.from_user.id)
    await callback.message.edit_text(
        shopping_list_text(items),
        reply_markup=shopping_list_keyboard(items),
    )


@dp.callback_query(F.data.startswith("shop:del:"))
async def shopping_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    try:
        item_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    await remove_shopping_item(callback.from_user.id, item_id)
    items = await list_shopping_items(callback.from_user.id)
    await callback.message.edit_text(
        shopping_list_text(items),
        reply_markup=shopping_list_keyboard(items),
    )


@dp.callback_query(F.data == "shop:clear")
async def shopping_clear_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return
    await clear_shopping_list(callback.from_user.id)
    await callback.message.edit_text(
        shopping_list_text([]),
        reply_markup=shopping_list_keyboard([]),
    )


@dp.callback_query(F.data == "shop:back")
async def shopping_back_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return
    items = await list_shopping_items(callback.from_user.id)
    await callback.message.edit_text(
        shopping_list_text(items),
        reply_markup=shopping_list_keyboard(items),
    )


@dp.callback_query(F.data.startswith("shop:item:"))
async def shopping_item_callback(callback: CallbackQuery):
    await callback.answer("Позиция находится в списке закупки.")


@dp.callback_query(F.data == "shop:optimize")
async def shopping_optimize_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    items = await list_shopping_items(callback.from_user.id)
    if not items:
        await callback.message.edit_text("Список закупки пуст.")
        return

    refreshed = await asyncio.gather(
        *(_refresh_shopping_candidate(item) for item in items)
    )

    requests = [
        PurchaseRequest(
            brand=item.brand,
            article=item.article,
            title=item.title,
            quantity=item.quantity,
        )
        for item in items
    ]
    candidate_map = {}
    missing = []
    for item, candidate in zip(items, refreshed, strict=True):
        if candidate is None:
            missing.append(f"{item.brand} {item.article}")
            continue
        candidate_map[(item.brand.casefold(), item.article.casefold())] = candidate

    plans = optimize_purchase(
        requests,
        candidate_map,
        shipping_fee=app_settings.procurement_shipping_fee,
        free_threshold=app_settings.procurement_free_shipping_threshold,
        provider_rules=provider_commercial_rules,
    )
    if not plans:
        await callback.message.edit_text(
            "Не удалось получить актуальные предложения для списка. "
            "Попробуйте позже."
        )
        return

    vehicle_ids = {item.vehicle_id for item in items if item.vehicle_id is not None}
    purchase_vehicle_id = (
        next(iter(vehicle_ids))
        if len(vehicle_ids) == 1
        else None
    )
    await state.update_data(
        last_purchase_plans=[serialize_purchase_plan(plan) for plan in plans[:5]],
        last_purchase_vehicle_id=purchase_vehicle_id,
    )

    lines = ["<b>Варианты закупки</b>", ""]
    for index, plan in enumerate(plans[:5], start=1):
        total = f"{plan.grand_total:,.0f}".replace(",", " ")
        lines.append(
            f"{index}. {escape(plan.title)} — <b>{total} ₽</b> · "
            f"{plan.provider_count} магаз."
        )
    if missing:
        lines.extend([
            "",
            "Не удалось обновить: " + ", ".join(escape(item) for item in missing),
        ])

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=purchase_plans_keyboard(plans[:5]),
    )


@dp.callback_query(F.data.startswith("shop:plan:"))
async def shopping_plan_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    try:
        index = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    data = await state.get_data()
    raw_plans = data.get("last_purchase_plans") or []
    if index < 0 or index >= len(raw_plans):
        await callback.message.answer("Расчёт устарел. Выполните его ещё раз.")
        return

    plan = deserialize_purchase_plan(raw_plans[index])
    await callback.message.edit_text(
        purchase_plan_text(plan, index + 1),
        reply_markup=purchase_plan_keyboard(plan, index),
    )


@dp.message(Command("quotes"))
@dp.message(F.text == BTN_QUOTES)
async def quotes_button(message: Message):
    quotes = await list_purchase_quotes(message.from_user.id)
    if not quotes:
        await message.answer(
            "Сохранённых расчётов пока нет.\n"
            "Откройте план закупки и нажмите «💾 Сохранить расчёт».",
            reply_markup=main_menu((await get_vehicle(message.from_user.id)) is not None),
        )
        return

    await message.answer(
        "<b>Сохранённые расчёты</b>\n"
        "Это snapshot цены и состава на момент сохранения.",
        reply_markup=quotes_keyboard(quotes),
    )


@dp.callback_query(F.data == "quote:list")
async def quote_list_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return
    quotes = await list_purchase_quotes(callback.from_user.id)
    if not quotes:
        await callback.message.edit_text("Сохранённых расчётов больше нет.")
        return
    await callback.message.edit_text(
        "<b>Сохранённые расчёты</b>\n"
        "Это snapshot цены и состава на момент сохранения.",
        reply_markup=quotes_keyboard(quotes),
    )


@dp.callback_query(F.data.startswith("quote:save:"))
async def quote_save_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    try:
        index = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        await callback.answer("Некорректный расчёт", show_alert=True)
        return

    data = await state.get_data()
    raw_plans = data.get("last_purchase_plans") or []
    if index < 0 or index >= len(raw_plans):
        await callback.answer("Расчёт устарел", show_alert=True)
        return

    plan_data = raw_plans[index]
    plan = deserialize_purchase_plan(plan_data)
    vehicle_id = data.get("last_purchase_vehicle_id")
    if vehicle_id is None:
        vehicle = await get_vehicle(callback.from_user.id)
        vehicle_id = vehicle.id if vehicle else None

    quote = await save_purchase_quote(
        callback.from_user.id,
        vehicle_id=vehicle_id,
        title=plan.title,
        grand_total=plan.grand_total,
        provider_count=plan.provider_count,
        max_delivery_days=plan.max_delivery_days,
        snapshot=plan_data,
    )
    await callback.answer(f"Расчёт #{quote.id} сохранён", show_alert=False)


@dp.callback_query(F.data.startswith("quote:open:"))
async def quote_open_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    try:
        quote_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    loaded = await get_purchase_quote(callback.from_user.id, quote_id)
    if loaded is None:
        await callback.message.answer("Расчёт не найден.")
        return

    quote, snapshot = loaded
    try:
        plan = deserialize_purchase_plan(snapshot)
    except (KeyError, TypeError, ValueError):
        await callback.message.answer("Snapshot расчёта повреждён.")
        return

    created = quote.created_at[:16].replace("T", " ") if quote.created_at else "—"
    await callback.message.edit_text(
        f"<b>Сохранённый расчёт #{quote.id}</b>\n"
        f"Создан: {escape(created)}\n\n"
        f"{purchase_plan_text(plan, 1)}",
        reply_markup=saved_quote_keyboard(quote.id, plan),
    )


@dp.callback_query(F.data.startswith("quote:refresh:"))
async def quote_refresh_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    try:
        quote_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    loaded = await get_purchase_quote(callback.from_user.id, quote_id)
    if loaded is None:
        await callback.message.answer("Расчёт не найден.")
        return

    quote, snapshot = loaded
    try:
        saved_plan = deserialize_purchase_plan(snapshot)
    except (KeyError, TypeError, ValueError):
        await callback.message.answer("Snapshot расчёта повреждён.")
        return

    requests = requests_from_plan(saved_plan)
    if not requests:
        await callback.message.answer("В сохранённом расчёте нет позиций.")
        return

    vehicle = None
    if quote.vehicle_id is not None:
        vehicle = await get_vehicle_by_id(callback.from_user.id, quote.vehicle_id)
    if vehicle is None:
        vehicle = await get_vehicle(callback.from_user.id)

    searches = await asyncio.gather(
        *(search_service.parts(vehicle, request.article) for request in requests)
    )

    candidate_map = {}
    missing: list[str] = []
    for request, candidates in zip(requests, searches, strict=True):
        if candidates:
            await record_candidate_prices(candidates)

        requested_article = _article_key(request.article)
        requested_brand = request.brand.casefold()
        candidate = next(
            (
                item
                for item in candidates
                if _article_key(item.article) == requested_article
                and item.brand.casefold() == requested_brand
            ),
            None,
        )
        if candidate is None:
            candidate = next(
                (
                    item
                    for item in candidates
                    if _article_key(item.article) == requested_article
                ),
                None,
            )

        if candidate is None:
            missing.append(f"{request.brand} {request.article}")
            continue
        candidate_map[(request.brand.casefold(), request.article.casefold())] = candidate

    if missing:
        await callback.message.edit_text(
            "<b>Не удалось корректно пересчитать весь заказ</b>\n\n"
            "Нет актуальных предложений для: "
            + ", ".join(escape(item) for item in missing)
            + "\n\nСравнение суммы не выполняется, чтобы не показать "
            "ложное снижение цены.",
            reply_markup=saved_quote_keyboard(quote.id, saved_plan),
        )
        return

    current_plans = optimize_purchase(
        requests,
        candidate_map,
        shipping_fee=app_settings.procurement_shipping_fee,
        free_threshold=app_settings.procurement_free_shipping_threshold,
        provider_rules=provider_commercial_rules,
    )
    if not current_plans:
        await callback.message.answer(
            "Не удалось получить актуальные предложения для сохранённого расчёта."
        )
        return

    current = current_plans[0]
    comparison = compare_purchase_plans(saved_plan, current)
    await state.update_data(
        last_purchase_plans=[serialize_purchase_plan(current)],
        last_purchase_vehicle_id=quote.vehicle_id,
    )

    await callback.message.edit_text(
        f"{purchase_comparison_text(comparison, current)}"
        f"\n\n"
        f"{purchase_plan_text(current, 1)}",
        reply_markup=quote_refresh_keyboard(quote.id, current, 0),
    )


@dp.callback_query(F.data.startswith("quote:delete:"))
async def quote_delete_callback(callback: CallbackQuery):
    await callback.answer()
    if callback.message is None:
        return

    try:
        quote_id = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    await delete_purchase_quote(callback.from_user.id, quote_id)
    quotes = await list_purchase_quotes(callback.from_user.id)
    if not quotes:
        await callback.message.edit_text("Сохранённых расчётов больше нет.")
        return

    await callback.message.edit_text(
        "<b>Сохранённые расчёты</b>",
        reply_markup=quotes_keyboard(quotes),
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
    await callback.answer()
    if callback.message is None:
        return

    index = int((callback.data or "").rsplit(":", 1)[1])
    data = await state.get_data()
    items = data.get("last_parts") or []
    if index < 0 or index >= len(items):
        await callback.answer("Эта выдача устарела", show_alert=True)
        return

    candidate = deserialize_candidate(items[index])
    current = f"{candidate.min_price:,.0f}".replace(",", " ")
    await callback.message.answer(
        f"<b>{escape(candidate.brand)} · "
        f"<code>{escape(candidate.article)}</code></b>\n"
        f"Текущая минимальная цена: <b>{current} ₽</b>\n\n"
        "При каком снижении сообщить?",
        reply_markup=price_alert_target_keyboard(index),
    )


@dp.callback_query(F.data.startswith("alert:set:"))
async def price_alert_set_callback(callback: CallbackQuery, state: FSMContext):
    if callback.message is None:
        return

    parts = (callback.data or "").split(":")
    if len(parts) != 4:
        await callback.answer("Некорректный порог", show_alert=True)
        return

    try:
        index = int(parts[2])
        drop_percent = Decimal(parts[3])
    except (ValueError, ArithmeticError):
        await callback.answer("Некорректный порог", show_alert=True)
        return

    data = await state.get_data()
    items = data.get("last_parts") or []
    if index < 0 or index >= len(items):
        await callback.answer("Эта выдача устарела", show_alert=True)
        return

    candidate = deserialize_candidate(items[index])
    vehicle, _ = await get_catalog_vehicle(state, callback.from_user.id)
    current_price = candidate.min_price
    drop = drop_percent / Decimal("100")
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
    await callback.answer("Уведомление создано")
    await callback.message.edit_text(
        f"🔔 Буду следить за <b>{escape(candidate.brand)}</b> "
        f"<code>{escape(candidate.article)}</code>.\n"
        f"Сообщу при цене ≤ <b>{target} ₽</b>."
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

    base_candidates = [deserialize_candidate(item) for item in raw_items]
    candidates, sort_label = sort_part_candidates(base_candidates, mode)
    visible = candidates[:5]

    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_sort_mode=mode,
        last_page=0,
    )

    query = data.get("last_query") or "запчасть"
    parent_id = data.get("last_parent_id")
    vehicle = vehicle_from_state(data.get("last_vehicle"))
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."
    total_found = data.get("last_total_found") or len(candidates)

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(index + 1, candidate)
        for index, candidate in enumerate(visible)
    )

    await callback.message.edit_text(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n"
        f"Сортировка: <b>{escape(sort_label)}</b>\n"
        f"Найдено вариантов: <b>{total_found}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(
            visible,
            parent_id,
            page=0,
            total_count=len(candidates),
        ),
    )


@dp.callback_query(F.data.startswith("page:"))
async def parts_page_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    raw_page = (callback.data or "").split(":", 1)[1]
    if raw_page == "noop":
        return
    try:
        requested_page = int(raw_page)
    except ValueError:
        return

    data = await state.get_data()
    raw_items = data.get("last_parts_recommended") or []
    if not raw_items:
        await callback.message.answer("Эта выдача устарела. Выполните поиск ещё раз.")
        return

    base_candidates = [deserialize_candidate(item) for item in raw_items]
    mode = data.get("last_sort_mode") or "recommended"
    candidates, sort_label = sort_part_candidates(base_candidates, mode)
    total_pages = max(1, (len(candidates) + 4) // 5)
    page = min(max(requested_page, 0), total_pages - 1)
    start = page * 5
    visible = candidates[start:start + 5]

    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_page=page,
    )

    query = data.get("last_query") or "запчасть"
    parent_id = data.get("last_parent_id")
    vehicle = vehicle_from_state(data.get("last_vehicle"))
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."
    total_found = data.get("last_total_found") or len(candidates)

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(start + index + 1, candidate)
        for index, candidate in enumerate(visible)
    )
    await callback.message.edit_text(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n"
        f"Сортировка: <b>{escape(sort_label)}</b>\n"
        f"Найдено вариантов: <b>{total_found}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(
            visible,
            parent_id,
            page=page,
            total_count=len(candidates),
        ),
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
        reply_markup=part_detail_keyboard(index, parent_id, candidate),
    )


@dp.callback_query(F.data.startswith("pricehist:"))
async def price_history_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.message is None:
        return

    try:
        index = int((callback.data or "").rsplit(":", 1)[1])
    except ValueError:
        return

    data = await state.get_data()
    raw_items = data.get("last_parts") or []
    if index < 0 or index >= len(raw_items):
        await callback.message.answer("Эта выдача устарела.")
        return

    candidate = deserialize_candidate(raw_items[index])
    points = await list_price_history(
        candidate.brand,
        candidate.article,
        limit=40,
    )
    await callback.message.answer(
        f"<b>{escape(candidate.brand)} · "
        f"<code>{escape(candidate.article)}</code></b>\n\n"
        f"{summarize_price_history(points)}"
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
    vehicle = vehicle_from_state(data.get("last_vehicle"))
    note = data.get("last_compatibility_note") or "Данные и цены пока демонстрационные."
    page = int(data.get("last_page") or 0)
    total_count = len(data.get("last_parts_recommended") or raw_items)
    start = page * 5

    vehicle_block = f"{vehicle_summary(vehicle)}\n\n" if vehicle else ""
    body = "\n\n".join(
        candidate_text(start + index + 1, candidate)
        for index, candidate in enumerate(candidates)
    )

    await callback.message.edit_text(
        f"{vehicle_block}"
        f"Запрос: <b>{escape(query)}</b>\n\n"
        f"{body}\n\n"
        f"<i>{escape(note)}</i>",
        reply_markup=parts_results_keyboard(
            candidates,
            parent_id,
            page=page,
            total_count=total_count,
        ),
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
    if candidates:
        await record_candidate_prices(candidates)
    if not candidates:
        await callback.message.edit_text(
            "Предложений пока нет.",
            reply_markup=catalog_keyboard(node.parent or "root"),
        )
        return

    stored = candidates[:20]
    visible = stored[:5]
    await state.update_data(
        last_parts=[serialize_candidate(item) for item in visible],
        last_parts_recommended=[serialize_candidate(item) for item in stored],
        last_query=node.query,
        last_parent_id=node.parent,
        last_vehicle=vehicle_state_payload(vehicle),
        last_compatibility_note=compatibility_note,
        last_sort_mode="recommended",
        last_page=0,
        last_total_found=len(candidates),
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
        reply_markup=parts_results_keyboard(
            visible,
            node.parent,
            page=0,
            total_count=len(stored),
        ),
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


async def main():
    if not app_settings.bot_token.strip():
        raise RuntimeError("BOT_TOKEN is required to run the Telegram bot")

    await init_db()
    log_event(
        logger,
        logging.INFO,
        "application_start",
        "Zap application starting",
        run_mode=app_settings.bot_run_mode,
        providers=[provider.name for provider in providers],
        fitment_enabled=fitment_catalog is not None,
        vehicle_api_enabled=app_settings.vehicle_api_enabled,
    )
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
            BotCommand(command="works", description="Подбор по списку работ"),
            BotCommand(command="shopping", description="Список закупки"),
            BotCommand(command="quotes", description="Сохранённые расчёты"),
            BotCommand(command="status", description="Статус источников"),
        ]
    )
    alert_task = None
    worker_mode = app_settings.price_alert_worker_mode.casefold().strip()
    if app_settings.price_alerts_enabled and worker_mode == "embedded":
        alert_task = asyncio.create_task(
            price_alert_loop(
                bot,
                search_service,
                app_settings.price_alert_interval_seconds,
            )
        )
    elif worker_mode not in {"embedded", "external", "disabled"}:
        raise ValueError(
            "PRICE_ALERT_WORKER_MODE must be embedded, external or disabled"
        )

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
