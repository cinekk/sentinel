from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from plugins import registry
from plugins.mock_boundary import MockBoundaryPlugin, MockEventsPlugin
from plugins.resources import FireStationsPlugin, HospitalsPlugin, SchoolsPlugin, SocialPlugin
from plugins.simulation import SimulationPlugin
from routers.crisis import router as crisis_router
from routers.events import router as events_router
from routers.fires_compat import router as fires_compat_router
from routers.layers import router as layers_router
from routers.resources import router as resources_router
from routers.simulation import router as simulation_router
from routers.v1_layers import router as v1_layers_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    registry.register(MockBoundaryPlugin())
    registry.register(MockEventsPlugin())
    registry.register(SimulationPlugin())
    registry.register(HospitalsPlugin())
    registry.register(SocialPlugin())
    registry.register(SchoolsPlugin())
    registry.register(FireStationsPlugin())
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
app.include_router(v1_layers_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "plugins": [p.layer_id for p in registry.all()]}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
