from datetime import datetime, timezone
from decimal import Decimal
import json

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.domain import FavoritePart, Offer, PriceAlert, PriceHistoryPoint, SavedPurchaseQuote, SearchHistoryItem, ShoppingListItem, Vehicle


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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_garage_vehicle_columns()
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

    async with Session() as session:
        for offer in offers:
            session.add(
                PriceHistoryRow(
                    provider=offer.provider,
                    brand=offer.brand,
                    article=offer.article,
                    price=offer.price,
                    delivery_days=offer.delivery_days,
                )
            )
        await session.commit()
        return len(offers)


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
