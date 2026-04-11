from datetime import datetime, timezone

from sqlalchemy import Boolean, String, Float, DateTime, Integer
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    time: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="active")
    description: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String, default="manual")


class HospitalRow(Base):
    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    facility_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    short_name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    operator: Mapped[str] = mapped_column(String)
    nfz_contract: Mapped[bool] = mapped_column(Boolean)

    street: Mapped[str] = mapped_column(String)
    city: Mapped[str] = mapped_column(String)
    postal_code: Mapped[str] = mapped_column(String)
    gmina: Mapped[str] = mapped_column(String)
    powiat: Mapped[str] = mapped_column(String)
    teryt_code: Mapped[str] = mapped_column(String)

    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    has_sor: Mapped[bool] = mapped_column(Boolean)
    has_pediatric_sor: Mapped[bool] = mapped_column(Boolean)
    has_izba_przyjec: Mapped[bool] = mapped_column(Boolean)
    sor_throughput_per_day: Mapped[int] = mapped_column(Integer)
    decontamination_entry: Mapped[bool] = mapped_column(Boolean)
    isolation_rooms: Mapped[int] = mapped_column(Integer)
    negative_pressure_rooms: Mapped[int] = mapped_column(Integer)

    beds_total_contracted: Mapped[int] = mapped_column(Integer)
    beds_total_physical: Mapped[int] = mapped_column(Integer)
    beds_occupied_pct: Mapped[float] = mapped_column(Float)
    beds_available_estimate: Mapped[int] = mapped_column(Integer)
    icu_oiom_beds: Mapped[int] = mapped_column(Integer)
    ventilator_capable_beds: Mapped[int] = mapped_column(Integer)

    ecmo_available: Mapped[bool] = mapped_column(Boolean)
    dialysis_stations: Mapped[int] = mapped_column(Integer)
    burn_unit: Mapped[bool] = mapped_column(Boolean)
    neonatal_icu: Mapped[bool] = mapped_column(Boolean)

    operating_rooms: Mapped[int] = mapped_column(Integer)
    polytrauma_capable: Mapped[bool] = mapped_column(Boolean)
    ct_24_7: Mapped[bool] = mapped_column(Boolean)
    mri_available: Mapped[bool] = mapped_column(Boolean)

    helipad: Mapped[bool] = mapped_column(Boolean)
    helipad_type: Mapped[str] = mapped_column(String)
    helipad_night_capable: Mapped[bool] = mapped_column(Boolean)

    backup_power: Mapped[bool] = mapped_column(Boolean)
    backup_power_fuel_hours: Mapped[float] = mapped_column(Float)

    phone_24h_sor: Mapped[str] = mapped_column(String)
    email: Mapped[str] = mapped_column(String)

    specializations: Mapped[str] = mapped_column(String)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with SessionLocal() as session:
        yield session
