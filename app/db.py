from sqlalchemy import BigInteger, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.config import settings
from app.domain import Vehicle

class Base(DeclarativeBase):
    pass

class VehicleRow(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    brand: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    year: Mapped[int] = mapped_column(Integer)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)

engine = create_async_engine(settings().database_url)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_vehicle(user_id: int) -> Vehicle | None:
    async with Session() as s:
        row = await s.scalar(select(VehicleRow).where(VehicleRow.telegram_user_id == user_id))
        return None if row is None else Vehicle(row.brand, row.model, row.year, row.vin)

async def save_vehicle(user_id: int, brand: str, model: str, year: int, vin: str | None) -> Vehicle:
    async with Session() as s:
        row = await s.scalar(select(VehicleRow).where(VehicleRow.telegram_user_id == user_id))
        if row is None:
            row = VehicleRow(telegram_user_id=user_id, brand=brand, model=model, year=year, vin=vin)
            s.add(row)
        else:
            row.brand, row.model, row.year, row.vin = brand, model, year, vin
        await s.commit()
    return Vehicle(brand, model, year, vin)
