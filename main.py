from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db
from plugins import registry
from plugins.mock_boundary import MockBoundaryPlugin, MockEventsPlugin
from routers.events import router as events_router
from routers.layers import router as layers_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    registry.register(MockBoundaryPlugin())
    registry.register(MockEventsPlugin())
    yield


app = FastAPI(title="SENTINEL", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(events_router)
app.include_router(layers_router)


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "plugins": [p.layer_id for p in registry.all()]}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
