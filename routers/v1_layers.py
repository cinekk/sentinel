"""
/api/v1/layers/* — resource layer aliases + sensor data.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from plugins import registry
from plugins.gios import GIOSPlugin, _MOCK_FALLBACK

router = APIRouter(prefix="/api/v1/layers", tags=["v1-layers"])

# ── Mock IMGW weather stations ─────────────────────────────────────────────────
WEATHER_DATA = _WEATHER = [
    {"name": "IMGW Puławy", "lat": 51.4158, "lon": 21.9698, "temp_c": 12.3, "wind_dir": "NE", "wind_speed_kmh": 15, "humidity_pct": 68},
    {"name": "IMGW Lublin", "lat": 51.2490, "lon": 22.5665, "temp_c": 11.8, "wind_dir": "NE", "wind_speed_kmh": 18, "humidity_pct": 72},
    {"name": "IMGW Zamość", "lat": 50.7231, "lon": 23.2519, "temp_c": 10.9, "wind_dir": "E", "wind_speed_kmh": 12, "humidity_pct": 75},
    {"name": "IMGW Chełm", "lat": 51.1431, "lon": 23.4722, "temp_c": 11.5, "wind_dir": "NE", "wind_speed_kmh": 14, "humidity_pct": 70},
]


@router.get("/hospitals")
async def get_hospitals() -> dict:
    return await _fetch_layer("hospitals")


@router.get("/schools")
async def get_schools() -> dict:
    return await _fetch_layer("schools")


@router.get("/social-facilities")
async def get_social_facilities() -> dict:
    return await _fetch_layer("social")


@router.get("/air-quality")
async def get_air_quality() -> list[dict]:
    """GIOŚ air quality stations — live data with fallback to mock."""
    return await get_air_quality_data()


async def get_air_quality_data() -> list[dict]:
    """Fetch air quality in briefing-compatible format. Used by voice.py too."""
    plugin = registry.get("air_quality")
    if isinstance(plugin, GIOSPlugin):
        return await plugin.get_briefing_data()
    return [{"source": "mock", **m} for m in _MOCK_FALLBACK]


@router.get("/weather")
async def get_weather() -> list[dict]:
    """Mock IMGW weather stations."""
    return _WEATHER


async def _fetch_layer(layer_id: str) -> dict:
    plugin = registry.get(layer_id)
    if not plugin:
        raise HTTPException(status_code=503, detail=f"Layer '{layer_id}' not available")
    return await plugin.fetch()
