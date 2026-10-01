from sqlalchemy import BigInteger, Boolean, Integer, String, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.config import settings
from app.domain import Vehicle


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


class GarageVehicleRow(Base):
    __tablename__ = "garage_vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


engine = create_async_engine(settings().database_url)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _to_vehicle(row: GarageVehicleRow) -> Vehicle:
    return Vehicle(
        brand=row.brand,
        model=row.model,
        year=row.year,
        vin=row.vin,
        id=row.id,
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
