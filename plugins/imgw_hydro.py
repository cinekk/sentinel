"""
IMGW Hydrological Stations Plugin.

Fetches live river gauge readings from the IMGW hydrology API and exposes them
as a GeoJSON layer. Filtered to rivers in Lublin voivodeship.

API: https://hydro.imgw.pl/api/station/
Cache TTL: 5 minutes (gauges update every ~10-15 min on the IMGW portal).

Override support: call set_gauge_override(station_id, alert_level) for demo purposes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Literal

import httpx

from plugins.base import BasePlugin

logger = logging.getLogger(__name__)

_IMGW_API = "https://hydro.imgw.pl/api/station/"

# Lublin voivodeship bounding box
_LAT_MIN, _LAT_MAX = 50.4, 51.9
_LON_MIN, _LON_MAX = 21.5, 24.1

_CACHE_TTL_SECONDS = 300  # 5 minutes

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


def get_overrides() -> dict[str, AlertLevel]:
    return dict(_overrides)


def _compute_alert_level(level_cm: float | None, warning_cm: float | None, alarm_cm: float | None) -> AlertLevel:
    if level_cm is None:
        return "unknown"
    if alarm_cm and level_cm >= alarm_cm:
        return "alarm"
    if warning_cm and level_cm >= warning_cm:
        return "warning"
    return "normal"


def _in_lublin_bbox(lat: float, lon: float) -> bool:
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


async def _fetch_all_stations() -> list[dict]:
    """Fetch all IMGW stations and return those within Lublin voivodeship bbox."""
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(_IMGW_API)
        resp.raise_for_status()
        stations = resp.json()

    result = []
    for s in stations:
        try:
            lat = float(s.get("lat") or s.get("latitude") or 0)
            lon = float(s.get("lon") or s.get("longitude") or 0)
        except (TypeError, ValueError):
            continue
        if not _in_lublin_bbox(lat, lon):
            continue
        result.append({
            "id": str(s.get("id") or s.get("stationId") or ""),
            "name": s.get("stationName") or s.get("name") or "Stacja IMGW",
            "river": s.get("riverName") or s.get("river") or "—",
            "lat": lat,
            "lon": lon,
            "level_cm": _safe_float(s.get("state") or s.get("stan")),
            "warning_cm": _safe_float(s.get("warningState") or s.get("ostrzezenie")),
            "alarm_cm": _safe_float(s.get("alarmState") or s.get("alarm")),
        })
    return result


def _safe_float(v: object) -> float | None:
    try:
        return float(v) if v is not None else None  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _build_feature(s: dict) -> dict:
    alert = _overrides.get(s["id"]) or _compute_alert_level(
        s["level_cm"], s["warning_cm"], s["alarm_cm"]
    )
    color = {"normal": "#22c55e", "warning": "#f59e0b", "alarm": "#ef4444"}.get(alert, "#6b7280")
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
        "properties": {
            "id": s["id"],
            "station_name": s["name"],
            "river": s["river"],
            "level_cm": s["level_cm"],
            "warning_cm": s["warning_cm"],
            "alarm_cm": s["alarm_cm"],
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
