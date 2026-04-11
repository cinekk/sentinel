"""
GIOŚ (Główny Inspektorat Ochrony Środowiska) air quality plugin.

Fetches real-time air quality index data from the public GIOŚ API
for stations in the Lubelskie voivodeship.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from plugins.base import BasePlugin

log = logging.getLogger(__name__)

_BASE_URL = "https://api.gios.gov.pl/pjp-api/v1/rest"
_REQUEST_TIMEOUT = 5.0
_STATION_CACHE_TTL = 86400  # 24h
_INDEX_CACHE_TTL = 900  # 15min

_INDEX_TO_PM25: dict[int, float] = {0: 5, 1: 15, 2: 30, 3: 55, 4: 80, 5: 120}
_INDEX_TO_PM10: dict[int, float] = {0: 15, 1: 35, 2: 55, 3: 80, 4: 120, 5: 150}
_INDEX_TO_STATUS: dict[int, str] = {
    0: "bardzo dobra",
    1: "dobra",
    2: "umiarkowana",
    3: "dostateczna",
    4: "zła",
    5: "bardzo zła",
}

_MOCK_FALLBACK: list[dict] = [
    {"name": "GIOŚ Puławy", "lat": 51.4158, "lon": 21.9698, "pm25": 18.3, "pm10": 32.1, "status": "dobra"},
    {"name": "GIOŚ Lublin ul. Obywatelska", "lat": 51.2490, "lon": 22.5665, "pm25": 24.7, "pm10": 41.2, "status": "umiarkowana"},
    {"name": "GIOŚ Chełm", "lat": 51.1431, "lon": 23.4722, "pm25": 15.2, "pm10": 28.4, "status": "dobra"},
    {"name": "GIOŚ Zamość", "lat": 50.7231, "lon": 23.2519, "pm25": 19.8, "pm10": 35.6, "status": "dobra"},
    {"name": "GIOŚ Biała Podlaska", "lat": 52.0333, "lon": 23.1167, "pm25": 12.1, "pm10": 22.3, "status": "dobra"},
    {"name": "GIOŚ Kraśnik", "lat": 50.9167, "lon": 22.2167, "pm25": 21.4, "pm10": 38.9, "status": "dobra"},
]

# Module-level caches
_station_cache: list[dict] | None = None
_station_cache_time: datetime | None = None
_index_cache: dict | None = None  # full GeoJSON FeatureCollection
_index_cache_time: datetime | None = None


def _clear_cache() -> None:
    """Reset all caches (used in tests)."""
    global _station_cache, _station_cache_time, _index_cache, _index_cache_time
    _station_cache = None
    _station_cache_time = None
    _index_cache = None
    _index_cache_time = None


def _cache_age(cache_time: datetime | None) -> float:
    if cache_time is None:
        return float("inf")
    return (datetime.now(timezone.utc) - cache_time).total_seconds()


async def _fetch_lubelskie_stations(client: httpx.AsyncClient) -> list[dict]:
    """Fetch all GIOŚ stations, filter to Lubelskie voivodeship."""
    global _station_cache, _station_cache_time

    if _station_cache and _cache_age(_station_cache_time) < _STATION_CACHE_TTL:
        return _station_cache

    stations: list[dict] = []
    page = 0
    while True:
        r = await client.get(
            f"{_BASE_URL}/station/findAll",
            params={"page": page, "size": 500},
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        page_stations = data.get("Lista stacji pomiarowych", [])
        if not page_stations:
            break
        stations.extend(page_stations)
        if len(page_stations) < 500:
            break
        page += 1

    lubelskie = []
    for s in stations:
        if s.get("Województwo", "").upper() != "LUBELSKIE":
            continue
        try:
            lat = float(s["WGS84 φ N"])
            lon = float(s["WGS84 λ E"])
        except (KeyError, ValueError, TypeError):
            continue
        lubelskie.append({
            "id": s.get("Identyfikator stacji"),
            "code": s.get("Kod stacji", ""),
            "name": s.get("Nazwa stacji", ""),
            "lat": lat,
            "lon": lon,
            "city": s.get("Powiat", ""),
        })

    log.info("GIOŚ: fetched %d stations total, %d in Lubelskie", len(stations), len(lubelskie))
    _station_cache = lubelskie
    _station_cache_time = datetime.now(timezone.utc)
    return lubelskie


async def _fetch_index(client: httpx.AsyncClient, station_id: int) -> dict | None:
    """Fetch air quality index for a single station. Returns None on failure."""
    try:
        r = await client.get(
            f"{_BASE_URL}/aqindex/getIndex/{station_id}",
            timeout=_REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        idx = data.get("AqIndex", {})
        overall = idx.get("Wartość indeksu")
        if overall is None:
            return None
        if not idx.get("Status indeksu ogólnego dla stacji pomiarowej", False):
            return None
        return idx
    except Exception:
        log.debug("GIOŚ: failed to fetch index for station %d", station_id, exc_info=True)
        return None


def _build_feature(station: dict, idx: dict) -> dict:
    """Build a GeoJSON Feature from station metadata and index data."""
    overall = idx.get("Wartość indeksu", 0)
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [station["lon"], station["lat"]],
        },
        "properties": {
            "name": f"GIOŚ {station['name']}",
            "station_id": station["id"],
            "source": "gios_live",
            "type": "air_quality",
            "overall_index": overall,
            "overall_category": idx.get("Nazwa kategorii indeksu", ""),
            "pm25_index": idx.get("Wartość indeksu dla wskaźnika PM2.5"),
            "pm25_category": idx.get("Nazwa kategorii indeksu dla wskażnika PM2.5", ""),
            "pm10_index": idx.get("Wartość indeksu dla wskaźnika PM10"),
            "pm10_category": idx.get("Nazwa kategorii indeksu dla wskażnika PM10", ""),
            "so2_index": idx.get("Wartość indeksu dla wskaźnika SO2"),
            "so2_category": idx.get("Nazwa kategorii indeksu dla wskażnika SO2", ""),
            "no2_index": idx.get("Wartość indeksu dla wskaźnika NO2"),
            "no2_category": idx.get("Nazwa kategorii indeksu dla wskażnika NO2", ""),
            "o3_index": idx.get("Wartość indeksu dla wskaźnika O3"),
            "o3_category": idx.get("Nazwa kategorii indeksu dla wskażnika O3", ""),
            "critical_pollutant": idx.get("Kod zanieczyszczenia krytycznego", ""),
            "measurement_time": idx.get("Data danych źródłowych ... PM2.5", ""),
            "calculation_time": idx.get("Data wykonania obliczeń indeksu", ""),
        },
    }


def _geojson_to_briefing(fc: dict) -> list[dict]:
    """Convert GeoJSON FeatureCollection to backward-compatible briefing format."""
    result = []
    for feat in fc.get("features", []):
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [0, 0])
        overall = props.get("overall_index", 0) or 0
        source = props.get("source", "gios_live")
        result.append({
            "name": props.get("name", ""),
            "lat": coords[1],
            "lon": coords[0],
            "pm25": _INDEX_TO_PM25.get(overall, 30),
            "pm10": _INDEX_TO_PM10.get(overall, 55),
            "status": _INDEX_TO_STATUS.get(overall, "umiarkowana"),
            "source": source,
        })
    return result


def _mock_geojson() -> dict:
    """Build GeoJSON from hardcoded mock data as a last resort."""
    features = []
    for m in _MOCK_FALLBACK:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [m["lon"], m["lat"]]},
            "properties": {
                "name": m["name"],
                "station_id": None,
                "source": "mock",
                "type": "air_quality",
                "overall_index": 1,
                "overall_category": m["status"],
                "pm25_index": None,
                "pm25_category": "",
                "pm10_index": None,
                "pm10_category": "",
                "so2_index": None,
                "so2_category": "",
                "no2_index": None,
                "no2_category": "",
                "o3_index": None,
                "o3_category": "",
                "critical_pollutant": "",
                "measurement_time": "",
                "calculation_time": "",
            },
        })
    return {"type": "FeatureCollection", "features": features}


class GIOSPlugin(BasePlugin):
    layer_id = "air_quality"
    layer_name = "Jakość powietrza (GIOŚ)"
    data_type = "air_quality"

    async def fetch(self) -> dict:
        global _index_cache, _index_cache_time

        if _index_cache and _cache_age(_index_cache_time) < _INDEX_CACHE_TTL:
            return _index_cache

        try:
            async with httpx.AsyncClient() as client:
                stations = await _fetch_lubelskie_stations(client)
                if not stations:
                    raise RuntimeError("No stations returned")

                results = await asyncio.gather(
                    *[_fetch_index(client, s["id"]) for s in stations],
                    return_exceptions=True,
                )

            features = []
            for station, idx in zip(stations, results):
                if isinstance(idx, Exception) or idx is None:
                    continue
                features.append(_build_feature(station, idx))

            if not features:
                raise RuntimeError("No valid index data from any station")

            fc = {"type": "FeatureCollection", "features": features}
            self._last_updated = datetime.now(timezone.utc)
            _index_cache = fc
            _index_cache_time = datetime.now(timezone.utc)
            log.info("GIOŚ: live data — %d stations with valid index", len(features))
            return fc

        except Exception:
            log.warning("GIOŚ API fetch failed, falling back", exc_info=True)
            if _index_cache:
                log.info("GIOŚ: returning cached data")
                for feat in _index_cache.get("features", []):
                    feat["properties"]["source"] = "gios_cached"
                return _index_cache

            log.info("GIOŚ: no cache, returning mock data")
            return _mock_geojson()

    async def get_briefing_data(self) -> list[dict]:
        fc = await self.fetch()
        return _geojson_to_briefing(fc)
