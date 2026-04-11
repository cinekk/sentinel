import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

import database
from database import Base, get_db, HospitalRow
from plugins import registry, PluginRegistry
from plugins.mock_boundary import MockBoundaryPlugin, MockEventsPlugin
from plugins.simulation import SimulationPlugin
from seed_hospitals import HOSPITALS


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    original_session_local = database.SessionLocal
    database.SessionLocal = session_factory

    async with session_factory() as session:
        for h in HOSPITALS:
            session.add(HospitalRow(**h))
        await session.commit()

    async with session_factory() as session:
        yield session

    database.SessionLocal = original_session_local
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    from main import app

    # Override DB dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Reset and repopulate plugin registry for each test
    registry._plugins.clear()
    registry.register(MockBoundaryPlugin())
    registry.register(MockEventsPlugin())
    # Note: SimulationPlugin NOT registered here — keeps existing tests isolated

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sim_client(db_session: AsyncSession):
    """Client with SimulationPlugin registered. Each test gets a fresh plugin instance."""
    from main import app

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    registry._plugins.clear()
    registry.register(MockBoundaryPlugin())
    registry.register(MockEventsPlugin())
    registry.register(SimulationPlugin())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Stop any running sim task to avoid leaking asyncio tasks between tests
    plugin = registry.get("simulation_threat")
    if plugin:
        plugin.stop()

    app.dependency_overrides.clear()
