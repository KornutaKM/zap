from datetime import datetime, timezone
from decimal import Decimal
import json

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.domain import CustomerOrder, FavoritePart, Offer, OrderEvent, OrderLine, PriceAlert, PriceHistoryPoint, SavedPurchaseQuote, SearchHistoryItem, ShoppingListItem, SupplierOrderGroup, Vehicle


class Base(DeclarativeBase):
    pass


class VehicleRow(Base):
    """Legacy single-vehicle table kept for automatic migration."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)


class SearchHistoryRow(Base):
    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    query: Mapped[str] = mapped_column(String(250))
    vehicle_label: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FavoritePartRow(Base):
    __tablename__ = "favorite_parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    brand: Mapped[str] = mapped_column(String(120))
    article: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(250))


class PriceAlertRow(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    brand: Mapped[str] = mapped_column(String(120))
    article: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(250))
    target_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    last_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShoppingListRow(Base):
    __tablename__ = "shopping_list"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    brand: Mapped[str] = mapped_column(String(120))
    article: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(250))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedPurchaseQuoteRow(Base):
    __tablename__ = "saved_purchase_quotes"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(250))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    provider_count: Mapped[int] = mapped_column(Integer)
    max_delivery_days: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), default="saved", index=True)
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PriceHistoryRow(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(120), index=True)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    article: Mapped[str] = mapped_column(String(120), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    delivery_days: Mapped[int] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class CustomerOrderRow(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_quote_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    item_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    provider_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SupplierOrderGroupRow(Base):
    __tablename__ = "order_provider_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    item_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shipping_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    grand_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    checkout_mode: Mapped[str] = mapped_column(String(40), default="deeplink")
    external_order_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class OrderLineRow(Base):
    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("order_provider_groups.id"), index=True)
    provider: Mapped[str] = mapped_column(String(120), index=True)
    brand: Mapped[str] = mapped_column(String(120), index=True)
    article: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(250))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    delivery_days: Mapped[int] = mapped_column(Integer)
    offer_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True)
    price_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class OrderEventRow(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    message: Mapped[str] = mapped_column(String(500))
    from_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class GarageVehicleRow(Base):
    __tablename__ = "garage_vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    generation_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    engine: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fuel: Mapped[str | None] = mapped_column(String(40), nullable=True)
    drive: Mapped[str | None] = mapped_column(String(40), nullable=True)
    power_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modification_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


engine = create_async_engine(
    settings().database_url,
    pool_pre_ping=True,
)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _to_vehicle(row: GarageVehicleRow) -> Vehicle:
    return Vehicle(
        brand=row.brand,
        model=row.model,
        year=row.year,
        vin=row.vin,
        id=row.id,
        generation_code=row.generation_code,
        engine=row.engine,
        fuel=row.fuel,
        drive=row.drive,
        power_hp=row.power_hp,
        modification_key=row.modification_key,
    )


async def _migrate_garage_vehicle_columns() -> None:
    if not str(engine.url).startswith("sqlite"):
        return

    columns = {
        "generation_code": "VARCHAR(40)",
        "engine": "VARCHAR(80)",
        "fuel": "VARCHAR(40)",
        "drive": "VARCHAR(40)",
        "power_hp": "INTEGER",
        "modification_key": "VARCHAR(120)",
    }

    async with engine.begin() as conn:
        rows = await conn.execute(text("PRAGMA table_info(garage_vehicles)"))
        existing = {row[1] for row in rows}

        for name, sql_type in columns.items():
            if name not in existing:
                await conn.execute(
                    text(f"ALTER TABLE garage_vehicles ADD COLUMN {name} {sql_type}")
                )


async def _migrate_legacy_vehicles() -> None:
    async with Session() as session:
        legacy_rows = (await session.scalars(select(VehicleRow))).all()
        changed = False

        for legacy in legacy_rows:
            existing = await session.scalar(
                select(GarageVehicleRow.id).where(
                    GarageVehicleRow.telegram_user_id == legacy.telegram_user_id
                )
            )
            if existing is not None:
                continue

            session.add(
                GarageVehicleRow(
                    telegram_user_id=legacy.telegram_user_id,
                    brand=legacy.brand,
                    model=legacy.model,
                    year=legacy.year,
                    vin=legacy.vin,
                    is_active=True,
                )
            )
            changed = True

        if changed:
            await session.commit()


async def init_db() -> None:
    from app.migrations import upgrade_database

    await upgrade_database()
    await _migrate_legacy_vehicles()


async def list_vehicles(user_id: int) -> list[Vehicle]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(GarageVehicleRow)
                .where(GarageVehicleRow.telegram_user_id == user_id)
                .order_by(GarageVehicleRow.is_active.desc(), GarageVehicleRow.id.asc())
            )
        ).all()
        return [_to_vehicle(row) for row in rows]


async def get_vehicle(user_id: int) -> Vehicle | None:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow)
            .where(GarageVehicleRow.telegram_user_id == user_id)
            .order_by(GarageVehicleRow.is_active.desc(), GarageVehicleRow.id.asc())
        )
        return None if row is None else _to_vehicle(row)


async def save_vehicle(
    user_id: int,
    brand: str,
    model: str,
    year: int,
    vin: str | None,
) -> Vehicle:
    async with Session() as session:
        await session.execute(
            update(GarageVehicleRow)
            .where(GarageVehicleRow.telegram_user_id == user_id)
            .values(is_active=False)
        )

        row = GarageVehicleRow(
            telegram_user_id=user_id,
            brand=brand,
            model=model,
            year=year,
            vin=vin,
            is_active=True,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _to_vehicle(row)


async def set_active_vehicle(user_id: int, vehicle_id: int) -> Vehicle | None:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle_id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        await session.execute(
            update(GarageVehicleRow)
            .where(GarageVehicleRow.telegram_user_id == user_id)
            .values(is_active=False)
        )
        row.is_active = True
        await session.commit()
        return _to_vehicle(row)


async def delete_vehicle(user_id: int, vehicle_id: int) -> bool:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle_id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return False

        was_active = row.is_active
        await session.delete(row)
        await session.flush()

        if was_active:
            replacement = await session.scalar(
                select(GarageVehicleRow)
                .where(GarageVehicleRow.telegram_user_id == user_id)
                .order_by(GarageVehicleRow.id.asc())
            )
            if replacement is not None:
                replacement.is_active = True

        await session.commit()
        return True



async def record_search(
    user_id: int,
    query: str,
    vehicle: Vehicle | None,
) -> None:
    label = None
    if vehicle is not None:
        year_text = f", {vehicle.year}" if vehicle.year > 0 else ""
        label = f"{vehicle.brand} {vehicle.model}{year_text}"

    async with Session() as session:
        session.add(
            SearchHistoryRow(
                telegram_user_id=user_id,
                query=query[:250],
                vehicle_label=label,
            )
        )
        await session.commit()


async def list_recent_searches(user_id: int, limit: int = 10) -> list[SearchHistoryItem]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(SearchHistoryRow)
                .where(SearchHistoryRow.telegram_user_id == user_id)
                .order_by(SearchHistoryRow.id.desc())
                .limit(limit)
            )
        ).all()
        return [
            SearchHistoryItem(
                id=row.id,
                query=row.query,
                vehicle_label=row.vehicle_label,
            )
            for row in rows
        ]


async def get_search_history_item(
    user_id: int,
    history_id: int,
) -> SearchHistoryItem | None:
    async with Session() as session:
        row = await session.scalar(
            select(SearchHistoryRow).where(
                SearchHistoryRow.id == history_id,
                SearchHistoryRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None
        return SearchHistoryItem(
            id=row.id,
            query=row.query,
            vehicle_label=row.vehicle_label,
        )


async def add_favorite(
    user_id: int,
    brand: str,
    article: str,
    title: str,
) -> FavoritePart:
    async with Session() as session:
        row = await session.scalar(
            select(FavoritePartRow).where(
                FavoritePartRow.telegram_user_id == user_id,
                FavoritePartRow.brand == brand,
                FavoritePartRow.article == article,
            )
        )
        if row is None:
            row = FavoritePartRow(
                telegram_user_id=user_id,
                brand=brand,
                article=article,
                title=title,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)

        return FavoritePart(
            id=row.id,
            brand=row.brand,
            article=row.article,
            title=row.title,
        )


async def list_favorites(user_id: int) -> list[FavoritePart]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(FavoritePartRow)
                .where(FavoritePartRow.telegram_user_id == user_id)
                .order_by(FavoritePartRow.id.desc())
            )
        ).all()
        return [
            FavoritePart(
                id=row.id,
                brand=row.brand,
                article=row.article,
                title=row.title,
            )
            for row in rows
        ]


async def remove_favorite(user_id: int, favorite_id: int) -> bool:
    async with Session() as session:
        row = await session.scalar(
            select(FavoritePartRow).where(
                FavoritePartRow.id == favorite_id,
                FavoritePartRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True



async def set_vehicle_modification(
    user_id: int,
    vehicle_id: int,
    *,
    generation_code: str,
    engine_code: str,
    fuel: str,
    drive: str,
    power_hp: int,
    modification_key: str,
) -> Vehicle | None:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle_id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        row.generation_code = generation_code
        row.engine = engine_code
        row.fuel = fuel
        row.drive = drive
        row.power_hp = power_hp
        row.modification_key = modification_key
        await session.commit()
        await session.refresh(row)
        return _to_vehicle(row)


async def clear_vehicle_modification(
    user_id: int,
    vehicle_id: int,
) -> Vehicle | None:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle_id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        row.generation_code = None
        row.engine = None
        row.fuel = None
        row.drive = None
        row.power_hp = None
        row.modification_key = None
        await session.commit()
        await session.refresh(row)
        return _to_vehicle(row)



async def get_vehicle_by_id(user_id: int, vehicle_id: int) -> Vehicle | None:
    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle_id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        return None if row is None else _to_vehicle(row)


async def create_price_alert(
    user_id: int,
    *,
    vehicle_id: int | None,
    brand: str,
    article: str,
    title: str,
    target_price,
    last_price=None,
) -> PriceAlert:
    target = Decimal(str(target_price))
    last = Decimal(str(last_price)) if last_price is not None else None

    async with Session() as session:
        row = await session.scalar(
            select(PriceAlertRow).where(
                PriceAlertRow.telegram_user_id == user_id,
                PriceAlertRow.vehicle_id == vehicle_id,
                PriceAlertRow.brand == brand,
                PriceAlertRow.article == article,
                PriceAlertRow.is_active.is_(True),
            )
        )
        if row is None:
            row = PriceAlertRow(
                telegram_user_id=user_id,
                vehicle_id=vehicle_id,
                brand=brand,
                article=article,
                title=title,
                target_price=target,
                last_price=last,
                is_active=True,
            )
            session.add(row)
        else:
            row.target_price = target
            row.last_price = last
            row.title = title

        await session.commit()
        await session.refresh(row)
        return PriceAlert(
            id=row.id,
            telegram_user_id=row.telegram_user_id,
            vehicle_id=row.vehicle_id,
            brand=row.brand,
            article=row.article,
            title=row.title,
            target_price=Decimal(str(row.target_price)),
            last_price=Decimal(str(row.last_price)) if row.last_price is not None else None,
            is_active=row.is_active,
        )


async def list_price_alerts(
    user_id: int | None = None,
    *,
    active_only: bool = True,
) -> list[PriceAlert]:
    async with Session() as session:
        stmt = select(PriceAlertRow)
        if user_id is not None:
            stmt = stmt.where(PriceAlertRow.telegram_user_id == user_id)
        if active_only:
            stmt = stmt.where(PriceAlertRow.is_active.is_(True))
        stmt = stmt.order_by(PriceAlertRow.id.desc())

        rows = (await session.scalars(stmt)).all()
        return [
            PriceAlert(
                id=row.id,
                telegram_user_id=row.telegram_user_id,
                vehicle_id=row.vehicle_id,
                brand=row.brand,
                article=row.article,
                title=row.title,
                target_price=Decimal(str(row.target_price)),
                last_price=Decimal(str(row.last_price)) if row.last_price is not None else None,
                is_active=row.is_active,
            )
            for row in rows
        ]


async def update_price_alert(
    alert_id: int,
    *,
    last_price=None,
    triggered: bool = False,
) -> None:
    async with Session() as session:
        row = await session.get(PriceAlertRow, alert_id)
        if row is None:
            return

        if last_price is not None:
            row.last_price = Decimal(str(last_price))
        if triggered:
            row.is_active = False
            row.triggered_at = datetime.now(timezone.utc)
        await session.commit()


async def delete_price_alert(user_id: int, alert_id: int) -> bool:
    async with Session() as session:
        row = await session.scalar(
            select(PriceAlertRow).where(
                PriceAlertRow.id == alert_id,
                PriceAlertRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True



async def update_vehicle_from_resolution(
    user_id: int,
    vehicle: Vehicle,
) -> Vehicle | None:
    if vehicle.id is None:
        return None

    async with Session() as session:
        row = await session.scalar(
            select(GarageVehicleRow).where(
                GarageVehicleRow.id == vehicle.id,
                GarageVehicleRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        row.brand = vehicle.brand
        row.model = vehicle.model
        row.year = vehicle.year
        row.vin = vehicle.vin
        row.generation_code = vehicle.generation_code
        row.engine = vehicle.engine
        row.fuel = vehicle.fuel
        row.drive = vehicle.drive
        row.power_hp = vehicle.power_hp
        row.modification_key = vehicle.modification_key
        await session.commit()
        await session.refresh(row)
        return _to_vehicle(row)



async def add_shopping_item(
    user_id: int,
    *,
    vehicle_id: int | None,
    brand: str,
    article: str,
    title: str,
    quantity: int = 1,
) -> ShoppingListItem:
    qty = max(1, min(quantity, 99))
    async with Session() as session:
        row = await session.scalar(
            select(ShoppingListRow).where(
                ShoppingListRow.telegram_user_id == user_id,
                ShoppingListRow.vehicle_id == vehicle_id,
                ShoppingListRow.brand == brand,
                ShoppingListRow.article == article,
            )
        )
        if row is None:
            row = ShoppingListRow(
                telegram_user_id=user_id,
                vehicle_id=vehicle_id,
                brand=brand,
                article=article,
                title=title,
                quantity=qty,
            )
            session.add(row)
        else:
            row.quantity = min(99, row.quantity + qty)
            row.title = title

        await session.commit()
        await session.refresh(row)
        return ShoppingListItem(
            id=row.id,
            telegram_user_id=row.telegram_user_id,
            vehicle_id=row.vehicle_id,
            brand=row.brand,
            article=row.article,
            title=row.title,
            quantity=row.quantity,
        )


async def list_shopping_items(user_id: int) -> list[ShoppingListItem]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(ShoppingListRow)
                .where(ShoppingListRow.telegram_user_id == user_id)
                .order_by(ShoppingListRow.id.asc())
            )
        ).all()
        return [
            ShoppingListItem(
                id=row.id,
                telegram_user_id=row.telegram_user_id,
                vehicle_id=row.vehicle_id,
                brand=row.brand,
                article=row.article,
                title=row.title,
                quantity=row.quantity,
            )
            for row in rows
        ]


async def change_shopping_quantity(
    user_id: int,
    item_id: int,
    delta: int,
) -> ShoppingListItem | None:
    async with Session() as session:
        row = await session.scalar(
            select(ShoppingListRow).where(
                ShoppingListRow.id == item_id,
                ShoppingListRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        row.quantity = max(1, min(99, row.quantity + delta))
        await session.commit()
        await session.refresh(row)
        return ShoppingListItem(
            id=row.id,
            telegram_user_id=row.telegram_user_id,
            vehicle_id=row.vehicle_id,
            brand=row.brand,
            article=row.article,
            title=row.title,
            quantity=row.quantity,
        )


async def remove_shopping_item(user_id: int, item_id: int) -> bool:
    async with Session() as session:
        row = await session.scalar(
            select(ShoppingListRow).where(
                ShoppingListRow.id == item_id,
                ShoppingListRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True


async def clear_shopping_list(user_id: int) -> None:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(ShoppingListRow).where(
                    ShoppingListRow.telegram_user_id == user_id
                )
            )
        ).all()
        for row in rows:
            await session.delete(row)
        await session.commit()



async def save_purchase_quote(
    user_id: int,
    *,
    vehicle_id: int | None,
    title: str,
    grand_total,
    provider_count: int,
    max_delivery_days: int,
    snapshot: dict,
) -> SavedPurchaseQuote:
    async with Session() as session:
        row = SavedPurchaseQuoteRow(
            telegram_user_id=user_id,
            vehicle_id=vehicle_id,
            title=title[:250],
            grand_total=Decimal(str(grand_total)),
            provider_count=max(0, provider_count),
            max_delivery_days=max(0, max_delivery_days),
            status="saved",
            snapshot_json=json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return SavedPurchaseQuote(
            id=row.id,
            telegram_user_id=row.telegram_user_id,
            vehicle_id=row.vehicle_id,
            title=row.title,
            grand_total=Decimal(str(row.grand_total)),
            provider_count=row.provider_count,
            max_delivery_days=row.max_delivery_days,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )


async def list_purchase_quotes(
    user_id: int,
    limit: int = 20,
) -> list[SavedPurchaseQuote]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(SavedPurchaseQuoteRow)
                .where(SavedPurchaseQuoteRow.telegram_user_id == user_id)
                .order_by(SavedPurchaseQuoteRow.id.desc())
                .limit(limit)
            )
        ).all()
        return [
            SavedPurchaseQuote(
                id=row.id,
                telegram_user_id=row.telegram_user_id,
                vehicle_id=row.vehicle_id,
                title=row.title,
                grand_total=Decimal(str(row.grand_total)),
                provider_count=row.provider_count,
                max_delivery_days=row.max_delivery_days,
                status=row.status,
                created_at=row.created_at.isoformat() if row.created_at else None,
            )
            for row in rows
        ]


async def get_purchase_quote(
    user_id: int,
    quote_id: int,
) -> tuple[SavedPurchaseQuote, dict] | None:
    async with Session() as session:
        row = await session.scalar(
            select(SavedPurchaseQuoteRow).where(
                SavedPurchaseQuoteRow.id == quote_id,
                SavedPurchaseQuoteRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None
        try:
            snapshot = json.loads(row.snapshot_json)
        except json.JSONDecodeError:
            snapshot = {}
        quote = SavedPurchaseQuote(
            id=row.id,
            telegram_user_id=row.telegram_user_id,
            vehicle_id=row.vehicle_id,
            title=row.title,
            grand_total=Decimal(str(row.grand_total)),
            provider_count=row.provider_count,
            max_delivery_days=row.max_delivery_days,
            status=row.status,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )
        return quote, snapshot


async def delete_purchase_quote(user_id: int, quote_id: int) -> bool:
    async with Session() as session:
        row = await session.scalar(
            select(SavedPurchaseQuoteRow).where(
                SavedPurchaseQuoteRow.id == quote_id,
                SavedPurchaseQuoteRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return False
        await session.delete(row)
        await session.commit()
        return True


async def record_price_observations(offers: list[Offer]) -> int:
    if not offers:
        return 0

    added = 0
    async with Session() as session:
        for offer in offers:
            latest = await session.scalar(
                select(PriceHistoryRow)
                .where(
                    PriceHistoryRow.provider == offer.provider,
                    PriceHistoryRow.brand == offer.brand,
                    PriceHistoryRow.article == offer.article,
                )
                .order_by(PriceHistoryRow.id.desc())
                .limit(1)
            )
            if (
                latest is not None
                and Decimal(str(latest.price)) == offer.price
                and latest.delivery_days == offer.delivery_days
            ):
                continue

            session.add(
                PriceHistoryRow(
                    provider=offer.provider,
                    brand=offer.brand,
                    article=offer.article,
                    price=offer.price,
                    delivery_days=offer.delivery_days,
                )
            )
            await session.flush()
            added += 1

        if added:
            await session.commit()
        return added


async def list_price_history(
    brand: str,
    article: str,
    *,
    provider: str | None = None,
    limit: int = 20,
) -> list[PriceHistoryPoint]:
    async with Session() as session:
        stmt = select(PriceHistoryRow).where(
            PriceHistoryRow.brand == brand,
            PriceHistoryRow.article == article,
        )
        if provider:
            stmt = stmt.where(PriceHistoryRow.provider == provider)
        stmt = stmt.order_by(PriceHistoryRow.id.desc()).limit(limit)

        rows = (await session.scalars(stmt)).all()
        return [
            PriceHistoryPoint(
                id=row.id,
                provider=row.provider,
                brand=row.brand,
                article=row.article,
                price=Decimal(str(row.price)),
                delivery_days=row.delivery_days,
                observed_at=row.observed_at.isoformat() if row.observed_at else "",
            )
            for row in rows
        ]



def _to_customer_order(row: CustomerOrderRow) -> CustomerOrder:
    return CustomerOrder(
        id=row.id,
        telegram_user_id=row.telegram_user_id,
        vehicle_id=row.vehicle_id,
        source_quote_id=row.source_quote_id,
        status=row.status,
        item_total=Decimal(str(row.item_total)),
        shipping_total=Decimal(str(row.shipping_total)),
        grand_total=Decimal(str(row.grand_total)),
        provider_count=row.provider_count,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def _to_supplier_group(row: SupplierOrderGroupRow) -> SupplierOrderGroup:
    return SupplierOrderGroup(
        id=row.id,
        order_id=row.order_id,
        provider=row.provider,
        status=row.status,
        item_total=Decimal(str(row.item_total)),
        shipping_total=Decimal(str(row.shipping_total)),
        grand_total=Decimal(str(row.grand_total)),
        checkout_mode=row.checkout_mode,
        external_order_id=row.external_order_id,
        checkout_url=row.checkout_url,
        last_error=row.last_error,
    )


def _to_order_line(row: OrderLineRow) -> OrderLine:
    return OrderLine(
        id=row.id,
        order_id=row.order_id,
        group_id=row.group_id,
        provider=row.provider,
        brand=row.brand,
        article=row.article,
        title=row.title,
        quantity=row.quantity,
        unit_price=Decimal(str(row.unit_price)),
        delivery_days=row.delivery_days,
        offer_url=row.offer_url,
        in_stock=row.in_stock,
        price_confirmed=row.price_confirmed,
    )


def _to_order_event(row: OrderEventRow) -> OrderEvent:
    return OrderEvent(
        id=row.id,
        order_id=row.order_id,
        event_type=row.event_type,
        message=row.message,
        from_status=row.from_status,
        to_status=row.to_status,
        provider=row.provider,
        created_at=row.created_at.isoformat() if row.created_at else None,
    )


async def create_customer_order(
    user_id: int,
    *,
    vehicle_id: int | None,
    source_quote_id: int | None,
    item_total,
    shipping_total,
    grand_total,
    groups: list[dict],
) -> CustomerOrder:
    async with Session() as session:
        order = CustomerOrderRow(
            telegram_user_id=user_id,
            vehicle_id=vehicle_id,
            source_quote_id=source_quote_id,
            status="draft",
            item_total=Decimal(str(item_total)),
            shipping_total=Decimal(str(shipping_total)),
            grand_total=Decimal(str(grand_total)),
            provider_count=len(groups),
        )
        session.add(order)
        await session.flush()

        for group_data in groups:
            group = SupplierOrderGroupRow(
                order_id=order.id,
                provider=group_data["provider"],
                status="draft",
                item_total=Decimal(str(group_data["item_total"])),
                shipping_total=Decimal(str(group_data["shipping_total"])),
                grand_total=Decimal(str(group_data["grand_total"])),
                checkout_mode=group_data.get("checkout_mode", "deeplink"),
                checkout_url=group_data.get("checkout_url"),
            )
            session.add(group)
            await session.flush()

            for line_data in group_data.get("lines", []):
                session.add(
                    OrderLineRow(
                        order_id=order.id,
                        group_id=group.id,
                        provider=group.provider,
                        brand=line_data["brand"],
                        article=line_data["article"],
                        title=line_data["title"],
                        quantity=int(line_data["quantity"]),
                        unit_price=Decimal(str(line_data["unit_price"])),
                        delivery_days=int(line_data["delivery_days"]),
                        offer_url=line_data.get("offer_url"),
                        in_stock=bool(line_data.get("in_stock", True)),
                        price_confirmed=False,
                    )
                )

        session.add(
            OrderEventRow(
                order_id=order.id,
                event_type="order_created",
                message="Черновик заказа создан из плана закупки.",
                to_status="draft",
            )
        )
        await session.commit()
        await session.refresh(order)
        return _to_customer_order(order)


async def list_customer_orders(
    user_id: int,
    limit: int = 20,
) -> list[CustomerOrder]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(CustomerOrderRow)
                .where(CustomerOrderRow.telegram_user_id == user_id)
                .order_by(CustomerOrderRow.id.desc())
                .limit(limit)
            )
        ).all()
        return [_to_customer_order(row) for row in rows]


async def get_customer_order(
    user_id: int,
    order_id: int,
) -> tuple[CustomerOrder, list[SupplierOrderGroup], list[OrderLine], list[OrderEvent]] | None:
    async with Session() as session:
        order = await session.scalar(
            select(CustomerOrderRow).where(
                CustomerOrderRow.id == order_id,
                CustomerOrderRow.telegram_user_id == user_id,
            )
        )
        if order is None:
            return None

        groups = (
            await session.scalars(
                select(SupplierOrderGroupRow)
                .where(SupplierOrderGroupRow.order_id == order_id)
                .order_by(SupplierOrderGroupRow.id.asc())
            )
        ).all()
        lines = (
            await session.scalars(
                select(OrderLineRow)
                .where(OrderLineRow.order_id == order_id)
                .order_by(OrderLineRow.id.asc())
            )
        ).all()
        events = (
            await session.scalars(
                select(OrderEventRow)
                .where(OrderEventRow.order_id == order_id)
                .order_by(OrderEventRow.id.desc())
                .limit(50)
            )
        ).all()

        return (
            _to_customer_order(order),
            [_to_supplier_group(row) for row in groups],
            [_to_order_line(row) for row in lines],
            [_to_order_event(row) for row in events],
        )


async def append_order_event(
    order_id: int,
    *,
    event_type: str,
    message: str,
    from_status: str | None = None,
    to_status: str | None = None,
    provider: str | None = None,
    payload: dict | None = None,
) -> None:
    async with Session() as session:
        session.add(
            OrderEventRow(
                order_id=order_id,
                event_type=event_type[:80],
                message=message[:500],
                from_status=from_status,
                to_status=to_status,
                provider=provider[:120] if provider else None,
                payload_json=(
                    json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                    if payload is not None
                    else None
                ),
            )
        )
        await session.commit()


async def update_order_status(
    user_id: int,
    order_id: int,
    status: str,
    *,
    message: str,
) -> CustomerOrder | None:
    async with Session() as session:
        row = await session.scalar(
            select(CustomerOrderRow).where(
                CustomerOrderRow.id == order_id,
                CustomerOrderRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None

        previous = row.status
        if previous == status:
            return _to_customer_order(row)

        row.status = status
        row.updated_at = datetime.now(timezone.utc)
        session.add(
            OrderEventRow(
                order_id=order_id,
                event_type="order_status",
                message=message[:500],
                from_status=previous,
                to_status=status,
            )
        )
        await session.commit()
        await session.refresh(row)
        return _to_customer_order(row)


async def update_order_line_confirmation(
    order_id: int,
    line_id: int,
    *,
    unit_price,
    delivery_days: int,
    in_stock: bool,
    price_confirmed: bool,
    offer_url: str | None,
) -> None:
    async with Session() as session:
        row = await session.scalar(
            select(OrderLineRow).where(
                OrderLineRow.id == line_id,
                OrderLineRow.order_id == order_id,
            )
        )
        if row is None:
            return
        row.unit_price = Decimal(str(unit_price))
        row.delivery_days = max(0, delivery_days)
        row.in_stock = in_stock
        row.price_confirmed = price_confirmed
        row.offer_url = offer_url
        await session.commit()


async def update_supplier_group_checkout(
    order_id: int,
    group_id: int,
    *,
    status: str,
    checkout_mode: str | None = None,
    external_order_id: str | None = None,
    checkout_url: str | None = None,
    last_error: str | None = None,
) -> SupplierOrderGroup | None:
    async with Session() as session:
        row = await session.scalar(
            select(SupplierOrderGroupRow).where(
                SupplierOrderGroupRow.id == group_id,
                SupplierOrderGroupRow.order_id == order_id,
            )
        )
        if row is None:
            return None

        previous_status = row.status
        next_mode = checkout_mode if checkout_mode is not None else row.checkout_mode
        changed = any(
            (
                previous_status != status,
                row.checkout_mode != next_mode,
                row.external_order_id != external_order_id,
                row.checkout_url != checkout_url,
                row.last_error != last_error,
            )
        )
        if not changed:
            return _to_supplier_group(row)

        row.status = status
        row.checkout_mode = next_mode
        row.external_order_id = external_order_id
        row.checkout_url = checkout_url
        row.last_error = last_error
        row.updated_at = datetime.now(timezone.utc)

        session.add(
            OrderEventRow(
                order_id=order_id,
                event_type="supplier_status",
                message=f"Статус поставщика {row.provider}: {status}",
                from_status=previous_status,
                to_status=status,
                provider=row.provider,
            )
        )
        await session.commit()
        await session.refresh(row)
        return _to_supplier_group(row)


async def replace_order_totals(
    user_id: int,
    order_id: int,
    *,
    item_total,
    shipping_total,
    grand_total,
) -> CustomerOrder | None:
    async with Session() as session:
        row = await session.scalar(
            select(CustomerOrderRow).where(
                CustomerOrderRow.id == order_id,
                CustomerOrderRow.telegram_user_id == user_id,
            )
        )
        if row is None:
            return None
        row.item_total = Decimal(str(item_total))
        row.shipping_total = Decimal(str(shipping_total))
        row.grand_total = Decimal(str(grand_total))
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        return _to_customer_order(row)



async def replace_supplier_group_totals(
    order_id: int,
    group_id: int,
    *,
    item_total,
    shipping_total,
    grand_total,
    status: str | None = None,
) -> SupplierOrderGroup | None:
    async with Session() as session:
        row = await session.scalar(
            select(SupplierOrderGroupRow).where(
                SupplierOrderGroupRow.id == group_id,
                SupplierOrderGroupRow.order_id == order_id,
            )
        )
        if row is None:
            return None

        row.item_total = Decimal(str(item_total))
        row.shipping_total = Decimal(str(shipping_total))
        row.grand_total = Decimal(str(grand_total))
        if status is not None:
            row.status = status
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        return _to_supplier_group(row)



async def list_orders_for_status_monitor(
    statuses: tuple[str, ...] = (
        "checkout_pending",
        "awaiting_manual_checkout",
        "partially_placed",
        "placed",
    ),
    limit: int = 200,
) -> list[CustomerOrder]:
    async with Session() as session:
        rows = (
            await session.scalars(
                select(CustomerOrderRow)
                .where(CustomerOrderRow.status.in_(statuses))
                .order_by(CustomerOrderRow.id.asc())
                .limit(limit)
            )
        ).all()
        return [_to_customer_order(row) for row in rows]
