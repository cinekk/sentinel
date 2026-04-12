"""
Flood scenario control endpoints.

POST /api/flood-scenario/start    Start scripted flood simulation
POST /api/flood-scenario/stop     Stop + clear all overrides
POST /api/flood-scenario/reset    Stop + reset tick to 0
GET  /api/flood-scenario/state    Current simulation state
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from plugins import registry

router = APIRouter(prefix="/api/flood-scenario", tags=["flood-scenario"])

_DEFAULT_TICK_INTERVAL = 15


def _get_plugin():
    plugin = registry.get("flood_scenario")
    if plugin is None:
        raise HTTPException(status_code=503, detail="FloodScenarioPlugin not registered")
    return plugin


class FloodScenarioStartRequest(BaseModel):
    tick_interval_seconds: int = _DEFAULT_TICK_INTERVAL


@router.post("/start")
async def start_flood_scenario(body: FloodScenarioStartRequest | None = None) -> dict:
    plugin = _get_plugin()

    # Mutual exclusion: stop fire simulation if running
    fire_plugin = registry.get("simulation_threat")
    if fire_plugin and fire_plugin.running:
        fire_plugin.stop()

    if plugin.running:
        return {"status": "already_running", "tick": plugin.tick}

    tick_interval = (body.tick_interval_seconds if body else _DEFAULT_TICK_INTERVAL)
    plugin.start(tick_interval_seconds=tick_interval)
    return {"status": "started", "tick_interval_seconds": tick_interval}


@router.post("/stop")
async def stop_flood_scenario() -> dict:
    plugin = _get_plugin()
    plugin.stop()
    return {"status": "stopped", "tick": plugin.tick}


@router.post("/reset")
async def reset_flood_scenario() -> dict:
    plugin = _get_plugin()
    plugin.reset()
    return {"status": "reset"}


@router.get("/state")
async def get_flood_scenario_state() -> dict:
    return _get_plugin().state
