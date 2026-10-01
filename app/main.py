import asyncio
from html import escape
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from app.config import settings
from app.db import get_vehicle, init_db, save_vehicle
from app.domain import rank_offers
from app.providers import MockProvider, ExistProvider, AutodocProvider

class Garage(StatesGroup):
    brand = State()
    model = State()
    year = State()
    vin = State()

providers = [MockProvider(), ExistProvider(), AutodocProvider()]
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "MVP бота для подбора запчастей.\n\n"
        "Сначала добавь автомобиль: /garage\n"
        "Затем просто напиши название детали или артикул.\n\n"
        "<i>Пока используются демонстрационные цены.</i>"
    )

@dp.message(Command("garage"))
async def garage(message: Message, state: FSMContext):
    current = await get_vehicle(message.from_user.id)
    if current:
        vin = current.vin or "не указан"
        await message.answer(
            f"<b>Сейчас:</b> {escape(current.brand)} {escape(current.model)}, {current.year}\n"
            f"VIN: <code>{escape(vin)}</code>\n\n"
            "Чтобы заменить авто, отправь /garage_add"
        )
        return
    await state.set_state(Garage.brand)
    await message.answer("Марка? Например: BMW")

@dp.message(Command("garage_add"))
async def garage_add(message: Message, state: FSMContext):
    await state.set_state(Garage.brand)
    await message.answer("Марка?")

@dp.message(Garage.brand)
async def garage_brand(message: Message, state: FSMContext):
    await state.update_data(brand=(message.text or "").strip())
    await state.set_state(Garage.model)
    await message.answer("Модель? Например: X3 G01")

@dp.message(Garage.model)
async def garage_model(message: Message, state: FSMContext):
    await state.update_data(model=(message.text or "").strip())
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
    vehicle = await save_vehicle(message.from_user.id, data["brand"], data["model"], data["year"], vin)
    await state.clear()
    await message.answer(
        f"Сохранено: <b>{escape(vehicle.brand)} {escape(vehicle.model)}, {vehicle.year}</b>.\n"
        "Теперь напиши, какую деталь ищем."
    )

def offer_text(label, offer):
    return (
        f"<b>{label}</b>\n"
        f"{escape(offer.brand)} · <code>{escape(offer.article)}</code>\n"
        f"{offer.price:,.0f} ₽ · {offer.delivery_days} дн. · {escape(offer.provider)}"
    ).replace(",", " ")

@dp.message(F.text)
async def search(message: Message):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    vehicle = await get_vehicle(message.from_user.id)
    if vehicle is None:
        await message.answer("Сначала добавь автомобиль через /garage.")
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
    bot = Bot(settings().bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
