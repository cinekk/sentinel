from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, SessionLocal, HospitalRow
from plugins import registry
from plugins.flood_zones import FloodZonesPlugin
from plugins.gios import GIOSPlugin
from plugins.imgw_hydro import IMGWHydroPlugin
from plugins.mock_boundary import MockBoundaryPlugin, EventsPlugin
from plugins.resources import FireStationsPlugin, HospitalsPlugin, HospitalStatusPlugin, SchoolsPlugin, SocialPlugin, TransportUnitsPlugin
from plugins.flood_scenario import FloodScenarioPlugin
from plugins.simulation import SimulationPlugin
from routers.assistant import router as assistant_router
from routers.crisis import router as crisis_router
from routers.emergency_calls import router as emergency_router
from routers.events import router as events_router
from routers.fires_compat import router as fires_compat_router
from routers.flood import router as flood_router
from routers.flood_scenario import router as flood_scenario_router
from routers.layers import router as layers_router
from routers.resources import router as resources_router
from routers.simulation import router as simulation_router
from routers.v1_layers import router as v1_layers_router
from routers.voice import router as voice_router
from services.flood_zones import load_flood_zones


async def _seed_hospitals_if_empty() -> None:
    from sqlalchemy import func, select
    from seed_hospitals import HOSPITALS
    async with SessionLocal() as session:
        count = await session.scalar(select(func.count()).select_from(HospitalRow))
        if count == 0:
            for h in HOSPITALS:
                session.add(HospitalRow(**h))
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    await _seed_hospitals_if_empty()
    await load_flood_zones()
    registry.register(MockBoundaryPlugin())
    registry.register(EventsPlugin())
    registry.register(FloodZonesPlugin())
    registry.register(SimulationPlugin())
    registry.register(HospitalsPlugin())
    registry.register(SocialPlugin())
    registry.register(SchoolsPlugin())
    registry.register(FireStationsPlugin())
    registry.register(GIOSPlugin())
    registry.register(IMGWHydroPlugin())
    registry.register(HospitalStatusPlugin())
    registry.register(TransportUnitsPlugin())
    registry.register(FloodScenarioPlugin())
    yield


app = FastAPI(title="SENTINEL", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(layers_router)
app.include_router(resources_router)
app.include_router(simulation_router)
app.include_router(crisis_router)
app.include_router(fires_compat_router)
app.include_router(emergency_router)
app.include_router(v1_layers_router)
app.include_router(assistant_router)
app.include_router(voice_router)
app.include_router(flood_router)
app.include_router(flood_scenario_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "plugins": [p.layer_id for p in registry.all()]}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
