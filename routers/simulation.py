from fastapi import APIRouter, HTTPException

from models import SimulationConfig
from plugins import registry

router = APIRouter(prefix="/api/simulation", tags=["simulation"])


def _get_plugin():
    plugin = registry.get("simulation_threat")
    if plugin is None:
        raise HTTPException(status_code=503, detail="SimulationPlugin not registered")
    return plugin


@router.post("/start")
async def start_simulation(config: SimulationConfig | None = None) -> dict:
    plugin = _get_plugin()
    if plugin.running:
        return {"status": "already_running", "tick": plugin.tick}
    plugin.start(config)
    return {"status": "started", "config": plugin.state["config"]}


@router.post("/stop")
async def stop_simulation() -> dict:
    plugin = _get_plugin()
    plugin.stop()
    return {"status": "stopped", "tick": plugin.tick}


@router.post("/reset")
async def reset_simulation() -> dict:
    plugin = _get_plugin()
    plugin.reset()
    return {"status": "reset"}


@router.get("/state")
async def get_state() -> dict:
    return _get_plugin().state
