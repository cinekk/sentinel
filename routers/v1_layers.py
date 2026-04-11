"""
/api/v1/layers/* — resource layer aliases + mock sensor data.
"""
from fastapi import APIRouter, HTTPException

from plugins import registry

router = APIRouter(prefix="/api/v1/layers", tags=["v1-layers"])

# ── Mock GIOŚ air-quality stations ────────────────────────────────────────────
AIR_QUALITY_DATA = _AIR_QUALITY = [
    {"name": "GIOŚ Puławy", "lat": 51.4158, "lon": 21.9698, "pm25": 18.3, "pm10": 32.1, "status": "dobra"},
    {"name": "GIOŚ Lublin ul. Obywatelska", "lat": 51.2490, "lon": 22.5665, "pm25": 24.7, "pm10": 41.2, "status": "umiarkowana"},
    {"name": "GIOŚ Chełm", "lat": 51.1431, "lon": 23.4722, "pm25": 15.2, "pm10": 28.4, "status": "dobra"},
    {"name": "GIOŚ Zamość", "lat": 50.7231, "lon": 23.2519, "pm25": 19.8, "pm10": 35.6, "status": "dobra"},
    {"name": "GIOŚ Biała Podlaska", "lat": 52.0333, "lon": 23.1167, "pm25": 12.1, "pm10": 22.3, "status": "dobra"},
    {"name": "GIOŚ Kraśnik", "lat": 50.9167, "lon": 22.2167, "pm25": 21.4, "pm10": 38.9, "status": "dobra"},
]

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
    """Mock GIOŚ PM2.5/PM10 stations. Phase 5 replaces with real API."""
    return _AIR_QUALITY


@router.get("/weather")
async def get_weather() -> list[dict]:
    """Mock IMGW weather stations."""
    return _WEATHER


async def _fetch_layer(layer_id: str) -> dict:
    plugin = registry.get(layer_id)
    if not plugin:
        raise HTTPException(status_code=503, detail=f"Layer '{layer_id}' not available")
    return await plugin.fetch()
