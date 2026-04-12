"""
Flood Assessment Service.

Combines IMGW river gauges + ISOK flood zones + hospital data + 112 medical events
to classify each hospital as "operational", "at_risk", or "evacuate".

Cache TTL: 2 minutes (gauges update ~15 min, 112 events are live).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select

from database import EventRow, HospitalRow, SessionLocal
from services.flood_zones import point_in_flood_zone
from services.spatial import haversine

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 120
_DEMAND_THRESHOLD = 10       # medical 112 calls within 15 km in last 2h → AT_RISK
_DEMAND_RADIUS_KM = 15.0
_DEMAND_WINDOW_H = 2

# In-memory hospital overrides: facility_id → patch dict
# Keys: "generator_state", "personnel_pct", "road_cut" (bool)
_hospital_overrides: dict[str, dict] = {}

# In-memory mock defaults for hospitals that have no specific override
# (generator_state, personnel_pct).  Populated on first assessment call.
_hospital_mock_state: dict[str, dict] = {}

_cache: list["HospitalFloodStatus"] | None = None
_cache_time: datetime | None = None


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class HospitalFloodStatus(BaseModel):
    hospital_id: str
    name: str
    lat: float
    lon: float
    status: Literal["operational", "at_risk", "evacuate"]
    risk_factors: list[str]
    beds: int
    sor: bool
    generator_state: str          # "ok" | "degraded" | "offline"
    personnel_pct: int            # 0–100
    nearest_gauge: str | None
    nearest_gauge_level: str | None  # "normal" | "warning" | "alarm" | "unknown"
    demand_112: int
    can_receive: bool


# ---------------------------------------------------------------------------
# Override helpers
# ---------------------------------------------------------------------------

def set_hospital_override(facility_id: str, patch: dict) -> None:
    """Patch generator_state, personnel_pct, and/or road_cut for a hospital."""
    _hospital_overrides.setdefault(facility_id, {}).update(patch)
    # Invalidate cache
    global _cache, _cache_time
    _cache = None
    _cache_time = None


def get_hospital_overrides() -> dict[str, dict]:
    return dict(_hospital_overrides)


def clear_all_overrides() -> None:
    global _cache, _cache_time
    _hospital_overrides.clear()
    _cache = None
    _cache_time = None


async def set_hospital_override_by_city(city_name: str, patch: dict) -> int:
    """Apply an override patch to all hospitals in the given city.

    Returns the number of hospitals updated. Uses case-insensitive city match.
    """
    city_lower = city_name.lower()
    try:
        async with SessionLocal() as session:
            result = await session.execute(select(HospitalRow))
            rows = result.scalars().all()
    except Exception as exc:
        logger.error("set_hospital_override_by_city: DB error: %s", exc)
        return 0

    count = 0
    for row in rows:
        if (row.city or "").lower() == city_lower:
            fid = row.facility_id or str(row.id)
            set_hospital_override(fid, patch)
            count += 1

    if count == 0:
        logger.warning("set_hospital_override_by_city: no hospitals found for city=%r", city_name)
    else:
        logger.info("set_hospital_override_by_city: patched %d hospitals in %s", count, city_name)
    return count


# ---------------------------------------------------------------------------
# Assessment logic
# ---------------------------------------------------------------------------

def _mock_state_for(facility_id: str, city: str) -> dict:
    """Return a stable mock generator/personnel state for a hospital.
    A few flood-prone cities get degraded/offline values for demo realism.
    """
    if facility_id in _hospital_mock_state:
        return _hospital_mock_state[facility_id]

    # Hospitals near Puławy or in low-lying cities get degraded state
    degraded_cities = {"puławy", "dęblin", "annopol", "kazimierz dolny", "włodawa", "hrubieszów"}
    offline_cities: set[str] = set()   # reserve one for extreme demo case

    city_lower = (city or "").lower()
    if city_lower in offline_cities:
        state = {"generator_state": "offline", "personnel_pct": 40}
    elif city_lower in degraded_cities:
        state = {"generator_state": "degraded", "personnel_pct": 65}
    else:
        state = {"generator_state": "ok", "personnel_pct": 85}

    _hospital_mock_state[facility_id] = state
    return state


async def _count_medical_calls(lat: float, lon: float) -> int:
    """Count medical 112 calls within DEMAND_RADIUS_KM in last DEMAND_WINDOW_H hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_DEMAND_WINDOW_H)
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(EventRow).where(
                    EventRow.category == "medical",
                    EventRow.time >= cutoff,
                )
            )
            rows = result.scalars().all()
    except Exception:
        return 0

    return sum(
        1 for r in rows
        if haversine(lat, lon, r.latitude, r.longitude) <= _DEMAND_RADIUS_KM
    )


def _nearest_gauge(lat: float, lon: float, gauges: list[dict]) -> dict | None:
    if not gauges:
        return None
    return min(gauges, key=lambda g: haversine(lat, lon, g["lat"], g["lon"]))


def _assess_one(
    row: HospitalRow,
    gauges: list[dict],
    demand_112: int,
) -> HospitalFloodStatus:
    fid = row.facility_id or str(row.id)
    override = _hospital_overrides.get(fid, {})
    mock = _mock_state_for(fid, row.city or "")

    generator_state: str = override.get("generator_state") or mock["generator_state"]
    personnel_pct: int = int(override.get("personnel_pct", mock["personnel_pct"]))
    road_cut: bool = bool(override.get("road_cut", False))

    flood_zone = point_in_flood_zone(row.latitude, row.longitude)
    gauge = _nearest_gauge(row.latitude, row.longitude, gauges)
    gauge_level = gauge["alert_level"] if gauge else None

    risk_factors: list[str] = []

    # ── EVACUATE conditions ──────────────────────────────────────────────────
    if road_cut or flood_zone == "p1":
        risk_factors.append("Drogi dojazdu odcięte (ISOK P=1%)")

    if flood_zone == "p10" and gauge_level == "alarm":
        risk_factors.append(f"Szpital w strefie P=10% + alarm powodziowy ({gauge['name'] if gauge else '—'})")

    if generator_state == "offline":
        risk_factors.append("Brak zasilania awaryjnego")

    evacuate = any([
        road_cut,
        flood_zone == "p1",
        (flood_zone == "p10" and gauge_level == "alarm"),
        generator_state == "offline",
    ])

    # ── AT_RISK conditions ───────────────────────────────────────────────────
    at_risk = False
    if not evacuate:
        if flood_zone == "p10" and gauge_level == "warning":
            risk_factors.append(f"Szpital w strefie P=10% + ostrzeżenie powodziowe ({gauge['name'] if gauge else '—'})")
            at_risk = True
        if generator_state == "degraded":
            risk_factors.append("Zasilanie awaryjne w trybie degradacji")
            at_risk = True
        if demand_112 > _DEMAND_THRESHOLD:
            risk_factors.append(f"Wysoki napływ wzywań 112 w okolicy ({demand_112} w ciągu 2h)")
            at_risk = True

    # ── Final status ─────────────────────────────────────────────────────────
    if evacuate:
        status: Literal["operational", "at_risk", "evacuate"] = "evacuate"
    elif at_risk:
        status = "at_risk"
    else:
        status = "operational"

    beds = row.beds_total_physical or 0
    sor = bool(row.has_sor)
    can_receive = (
        status == "operational"
        and demand_112 <= _DEMAND_THRESHOLD
        and beds > 20
    )

    return HospitalFloodStatus(
        hospital_id=fid,
        name=row.name or row.short_name or "Szpital",
        lat=row.latitude,
        lon=row.longitude,
        status=status,
        risk_factors=risk_factors,
        beds=beds,
        sor=sor,
        generator_state=generator_state,
        personnel_pct=personnel_pct,
        nearest_gauge=gauge["name"] if gauge else None,
        nearest_gauge_level=gauge_level,
        demand_112=demand_112,
        can_receive=can_receive,
    )


async def assess_hospitals() -> list[HospitalFloodStatus]:
    """
    Return flood assessment for all hospitals.
    Results are cached for CACHE_TTL_SECONDS.
    """
    global _cache, _cache_time

    now = datetime.now(timezone.utc)
    if _cache is not None and _cache_time and (now - _cache_time).total_seconds() < _CACHE_TTL_SECONDS:
        return _cache

    # Import here to avoid circular import at module load time
    from plugins.imgw_hydro import get_gauges_snapshot

    gauges = get_gauges_snapshot()

    try:
        async with SessionLocal() as session:
            result = await session.execute(select(HospitalRow))
            hospital_rows = result.scalars().all()
    except Exception as exc:
        logger.error("Failed to load hospitals for flood assessment: %s", exc)
        return []

    statuses: list[HospitalFloodStatus] = []
    for row in hospital_rows:
        demand = await _count_medical_calls(row.latitude, row.longitude)
        status = _assess_one(row, gauges, demand)
        statuses.append(status)

    _cache = statuses
    _cache_time = now
    logger.info(
        "Flood assessment: %d hospitals — %d evacuate, %d at_risk, %d operational",
        len(statuses),
        sum(1 for s in statuses if s.status == "evacuate"),
        sum(1 for s in statuses if s.status == "at_risk"),
        sum(1 for s in statuses if s.status == "operational"),
    )
    return statuses
