"""
IMGW Hydrological Stations Plugin.

Fetches live river gauge readings and alert levels from two IMGW sources:
  - https://danepubliczne.imgw.pl/api/data/hydro/   — current water levels
  - https://res2.imgw.pl/products/hydro/river-statuses/YYYYMMDDHHII.json
      — official IMGW status codes (alarm / warning / high / medium / low / below)
        published every hour; dreCode == id_stacji

Alert level mapping (from IMGW legend, chunk-BWM4BEIR.js):
  alarm   → "alarm"
  warning → "warning"
  high / medium / low / below → "normal"

Cache TTL: 5 minutes (gauges update every ~10-15 min on the IMGW portal).
Override support: call set_gauge_override(station_id, alert_level) for demo purposes.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Literal

import httpx

from plugins.base import BasePlugin

logger = logging.getLogger(__name__)

_IMGW_LEVELS_API = "https://danepubliczne.imgw.pl/api/data/hydro/"
_IMGW_STATUS_BASE = "https://res2.imgw.pl/products/hydro/river-statuses/"

_CACHE_TTL_SECONDS = 300  # 5 minutes (gauges update every ~10-15 min on the IMGW portal)

# IMGW statusCode → our AlertLevel
_STATUS_MAP: dict[str, str] = {
    "alarm": "alarm",
    "alarmOutdated": "alarm",
    "warning": "warning",
    "warningOutdated": "warning",
    "high": "normal",
    "highOutdated": "normal",
    "medium": "normal",
    "mediumOutdated": "normal",
    "low": "normal",
    "lowOutdated": "normal",
    "below": "normal",
    "belowOutdated": "normal",
}

AlertLevel = Literal["normal", "warning", "alarm", "unknown"]

# In-memory override dict: station_id → alert_level (for demo seed)
_overrides: dict[str, AlertLevel] = {}
_cache: dict | None = None
_cache_time: datetime | None = None


def set_gauge_override(station_id: str, alert_level: AlertLevel) -> None:
    """Override the alert level for a station (demo use)."""
    _overrides[station_id] = alert_level


def clear_gauge_override(station_id: str) -> None:
    _overrides.pop(station_id, None)


def clear_all_gauge_overrides() -> None:
    """Remove all gauge overrides (called by flood scenario reset)."""
    _overrides.clear()


def set_gauge_override_by_location(lat: float, lon: float, level: AlertLevel, max_km: float = 80.0) -> str | None:
    """Find the nearest cached gauge to (lat, lon) and override its alert level.

    Returns the station_id that was overridden, or None if no gauge was found in cache.
    """
    if _cache is None:
        return None

    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import radians, sin, cos, sqrt, atan2
        R = 6371.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        return R * 2 * atan2(sqrt(a), sqrt(1 - a))

    best_sid: str | None = None
    best_dist = float("inf")
    for feat in _cache.get("features", []):
        clat = feat["geometry"]["coordinates"][1]
        clon = feat["geometry"]["coordinates"][0]
        d = _haversine(lat, lon, clat, clon)
        if d < best_dist:
            best_dist = d
            best_sid = feat["properties"].get("id")

    if best_sid and best_dist <= max_km:
        set_gauge_override(best_sid, level)
        logger.info("Gauge override: station %s → %s (%.1f km away)", best_sid, level, best_dist)
        return best_sid

    logger.warning("No gauge found within %.0f km of (%.4f, %.4f)", max_km, lat, lon)
    return None


def get_overrides() -> dict[str, AlertLevel]:
    return dict(_overrides)


def _status_url_for(dt: datetime) -> str:
    """Return the river-statuses JSON URL for the most recent whole hour."""
    floored = dt.replace(minute=0, second=0, microsecond=0)
    return f"{_IMGW_STATUS_BASE}{floored.strftime('%Y%m%d%H%M')}.json"


async def _fetch_status_codes(client: httpx.AsyncClient) -> dict[str, str]:
    """Return dreCode → AlertLevel mapping from the IMGW river-statuses file."""
    url = _status_url_for(datetime.now(timezone.utc))
    try:
        resp = await client.get(url, timeout=10)
        resp.raise_for_status()
        return {
            s["dreCode"]: _STATUS_MAP.get(s.get("statusCode", ""), "unknown")
            for s in resp.json()
        }
    except Exception as exc:
        logger.warning("IMGW river-statuses unavailable (%s): alert levels will be unknown", exc)
        return {}


async def _fetch_all_stations() -> list[dict]:
    """Fetch water levels + alert statuses for Lublin voivodeship stations."""
    async with httpx.AsyncClient(timeout=20) as client:
        levels_resp, status_codes = await asyncio.gather(
            client.get(_IMGW_LEVELS_API),
            _fetch_status_codes(client),
        )
        levels_resp.raise_for_status()
        stations = levels_resp.json()

    result = []
    for s in stations:
        if s.get("wojewodztwo") != "lubelskie":
            continue
        try:
            lat = float(s.get("lat") or 0)
            lon = float(s.get("lon") or 0)
        except (TypeError, ValueError):
            continue
        sid = str(s.get("id_stacji") or "")
        result.append({
            "id": sid,
            "name": s.get("stacja") or "Stacja IMGW",
            "river": s.get("rzeka") or "—",
            "lat": lat,
            "lon": lon,
            "level_cm": _safe_float(s.get("stan_wody")),
            "alert_level": status_codes.get(sid, "unknown"),
        })
    return result


def _safe_float(v: object) -> float | None:
    try:
        return float(v) if v is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _build_feature(s: dict) -> dict:
    alert: str = _overrides.get(s["id"]) or s["alert_level"]
    color = {"normal": "#22c55e", "warning": "#f59e0b", "alarm": "#ef4444"}.get(alert, "#6b7280")
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
        "properties": {
            "id": s["id"],
            "station_name": s["name"],
            "river": s["river"],
            "level_cm": s["level_cm"],
            "alert_level": alert,
            "overridden": s["id"] in _overrides,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "marker_color": color,
            "type": "gauge",
        },
    }


class IMGWHydroPlugin(BasePlugin):
    layer_id = "gauges"
    layer_name = "Poziomy rzek (IMGW)"
    data_type = "gauge"

    async def fetch(self) -> dict:
        global _cache, _cache_time

        now = datetime.now(timezone.utc)
        if _cache and _cache_time and (now - _cache_time).total_seconds() < _CACHE_TTL_SECONDS:
            # Still apply current overrides to cached features
            return _apply_overrides_to_cache(_cache)

        try:
            stations = await _fetch_all_stations()
        except Exception as exc:
            logger.warning("IMGW API unavailable: %s — returning empty gauge layer", exc)
            stations = []

        features = [_build_feature(s) for s in stations]
        fc = {"type": "FeatureCollection", "features": features}
        _cache = fc
        _cache_time = now
        self._last_updated = now
        logger.info("IMGW: loaded %d gauges in Lublin voivodeship", len(features))
        return fc


def _apply_overrides_to_cache(fc: dict) -> dict:
    """Return a copy of the cached FeatureCollection with current overrides applied."""
    if not _overrides:
        return fc
    updated_features = []
    for feat in fc.get("features", []):
        sid = feat.get("properties", {}).get("id", "")
        if sid in _overrides:
            feat = dict(feat)
            feat["properties"] = dict(feat["properties"])
            feat["properties"]["alert_level"] = _overrides[sid]
            feat["properties"]["overridden"] = True
            feat["properties"]["marker_color"] = {
                "normal": "#22c55e", "warning": "#f59e0b", "alarm": "#ef4444"
            }.get(_overrides[sid], "#6b7280")
        updated_features.append(feat)
    return {"type": "FeatureCollection", "features": updated_features}


def get_gauges_snapshot() -> list[dict]:
    """
    Return current gauge data as a flat list of dicts (for FloodAssessmentService).
    Returns cached data if available, empty list otherwise.
    """
    if _cache is None:
        return []
    rows = []
    for feat in _cache.get("features", []):
        p = feat.get("properties", {})
        sid = p.get("id", "")
        rows.append({
            "id": sid,
            "name": p.get("station_name", ""),
            "river": p.get("river", ""),
            "lat": feat["geometry"]["coordinates"][1],
            "lon": feat["geometry"]["coordinates"][0],
            "alert_level": _overrides.get(sid) or p.get("alert_level", "unknown"),
        })
    return rows
