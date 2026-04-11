"""API tests for simulation endpoints (Phase 3)."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── State when idle ───────────────────────────────────────────────────────────

async def test_state_idle(sim_client: AsyncClient):
    r = await sim_client.get("/api/simulation/state")
    assert r.status_code == 200
    state = r.json()
    assert state["running"] is False
    assert state["tick"] == 0
    assert state["threat_zone"] is None
    assert state["alerts"] == []


async def test_state_has_config(sim_client: AsyncClient):
    r = await sim_client.get("/api/simulation/state")
    cfg = r.json()["config"]
    assert "source_lat" in cfg
    assert "source_lon" in cfg
    assert "wind_speed_kmh" in cfg
    assert "wind_direction_deg" in cfg


# ── Start ─────────────────────────────────────────────────────────────────────

async def test_start_returns_started(sim_client: AsyncClient):
    r = await sim_client.post("/api/simulation/start")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "started"
    assert "config" in body


async def test_start_with_custom_config(sim_client: AsyncClient):
    r = await sim_client.post("/api/simulation/start", json={
        "source_lat": 51.5,
        "source_lon": 22.0,
        "wind_speed_kmh": 30.0,
        "wind_direction_deg": 90.0,
        "fire_intensity": 2.0,
        "tick_interval_seconds": 10,
    })
    assert r.status_code == 200
    cfg = r.json()["config"]
    assert cfg["wind_speed_kmh"] == 30.0
    assert cfg["wind_direction_deg"] == 90.0


async def test_start_when_already_running(sim_client: AsyncClient):
    await sim_client.post("/api/simulation/start")
    r = await sim_client.post("/api/simulation/start")
    assert r.status_code == 200
    assert r.json()["status"] == "already_running"


async def test_state_running_after_start(sim_client: AsyncClient):
    await sim_client.post("/api/simulation/start")
    r = await sim_client.get("/api/simulation/state")
    assert r.json()["running"] is True


# ── Stop ──────────────────────────────────────────────────────────────────────

async def test_stop_returns_stopped(sim_client: AsyncClient):
    await sim_client.post("/api/simulation/start")
    r = await sim_client.post("/api/simulation/stop")
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"


async def test_stop_when_idle_is_safe(sim_client: AsyncClient):
    r = await sim_client.post("/api/simulation/stop")
    assert r.status_code == 200


async def test_state_not_running_after_stop(sim_client: AsyncClient):
    await sim_client.post("/api/simulation/start")
    await sim_client.post("/api/simulation/stop")
    r = await sim_client.get("/api/simulation/state")
    assert r.json()["running"] is False


# ── Reset ─────────────────────────────────────────────────────────────────────

async def test_reset_returns_reset(sim_client: AsyncClient):
    r = await sim_client.post("/api/simulation/reset")
    assert r.status_code == 200
    assert r.json()["status"] == "reset"


async def test_reset_clears_state(sim_client: AsyncClient):
    await sim_client.post("/api/simulation/start")
    await sim_client.post("/api/simulation/reset")
    state = (await sim_client.get("/api/simulation/state")).json()
    assert state["running"] is False
    assert state["tick"] == 0
    assert state["threat_zone"] is None
