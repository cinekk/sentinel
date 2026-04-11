"""
API integration tests for Sentinel Phase 1 & 2.
Uses an in-memory SQLite database and ASGI test client.
"""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ── Health ────────────────────────────────────────────────────────────────────

async def test_health(client: AsyncClient):
    r = await client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "lublin_boundary" in body["plugins"]
    assert "events" in body["plugins"]


# ── Events ────────────────────────────────────────────────────────────────────

async def test_list_events_empty(client: AsyncClient):
    r = await client.get("/api/events")
    assert r.status_code == 200
    assert r.json() == []


async def test_create_event(client: AsyncClient):
    payload = {
        "latitude": 51.4158,
        "longitude": 21.9698,
        "category": "fire",
        "severity": "high",
        "description": "Pożar zakładu chemicznego w Puławach",
        "source": "human",
    }
    r = await client.post("/api/events", json=payload)
    assert r.status_code == 201
    body = r.json()
    assert body["category"] == "fire"
    assert body["severity"] == "high"
    assert body["id"] is not None


async def test_list_events_after_create(client: AsyncClient):
    payload = {
        "latitude": 51.25,
        "longitude": 22.57,
        "category": "medical",
        "severity": "medium",
        "description": "Wypadek drogowy",
        "source": "sensor",
    }
    await client.post("/api/events", json=payload)
    r = await client.get("/api/events")
    assert r.status_code == 200
    events = r.json()
    assert len(events) == 1
    assert events[0]["category"] == "medical"


async def test_create_event_invalid_category(client: AsyncClient):
    payload = {
        "latitude": 51.25,
        "longitude": 22.57,
        "category": "earthquake",   # not a valid category
        "severity": "high",
        "description": "test",
        "source": "human",
    }
    r = await client.post("/api/events", json=payload)
    assert r.status_code == 422


async def test_create_event_invalid_severity(client: AsyncClient):
    payload = {
        "latitude": 51.25,
        "longitude": 22.57,
        "category": "fire",
        "severity": "catastrophic",   # not a valid severity
        "description": "test",
        "source": "human",
    }
    r = await client.post("/api/events", json=payload)
    assert r.status_code == 422


# ── Layers list ───────────────────────────────────────────────────────────────

async def test_list_layers(client: AsyncClient):
    r = await client.get("/api/layers")
    assert r.status_code == 200
    layers = r.json()
    ids = {l["layer_id"] for l in layers}
    assert "lublin_boundary" in ids
    assert "events" in ids


async def test_list_layers_have_required_fields(client: AsyncClient):
    r = await client.get("/api/layers")
    for layer in r.json():
        assert "layer_id" in layer
        assert "name" in layer
        assert "data_type" in layer


# ── Layer GeoJSON ─────────────────────────────────────────────────────────────

async def test_boundary_layer_geojson(client: AsyncClient):
    r = await client.get("/api/layers/lublin_boundary/geojson")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) > 0


async def test_boundary_layer_has_voivodeship_polygon(client: AsyncClient):
    r = await client.get("/api/layers/lublin_boundary/geojson")
    features = r.json()["features"]
    voivodeships = [f for f in features if f["properties"].get("type") == "voivodeship"]
    assert len(voivodeships) == 1
    assert voivodeships[0]["geometry"]["type"] == "Polygon"


async def test_boundary_layer_has_powiat_points(client: AsyncClient):
    r = await client.get("/api/layers/lublin_boundary/geojson")
    features = r.json()["features"]
    powiaty = [f for f in features if f["properties"].get("type") == "powiat"]
    assert len(powiaty) > 0
    for p in powiaty:
        assert p["geometry"]["type"] == "Point"
        lon, lat = p["geometry"]["coordinates"]
        # All powiaty should be roughly within Lublin voivodeship bounds
        assert 21.0 <= lon <= 24.5
        assert 50.0 <= lat <= 52.5


async def test_events_layer_geojson_empty(client: AsyncClient):
    r = await client.get("/api/layers/events/geojson")
    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert body["features"] == []


async def test_unknown_layer_returns_404(client: AsyncClient):
    r = await client.get("/api/layers/does_not_exist/geojson")
    assert r.status_code == 404
    assert "does_not_exist" in r.json()["detail"]
