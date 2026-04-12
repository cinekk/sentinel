"""
Medical evacuation dispatch service.

For each hospital in 'evacuate' or 'at_risk' status, derives the patient
load by category, generates a spatially realistic transport unit pool (T/N/P/S)
from hospital positions, and greedily assigns the nearest available units.
"""
from __future__ import annotations

import math
import random

from pydantic import BaseModel

from services.flood_assessment import HospitalFloodStatus
from services.spatial import haversine

# ── Unit type constants ───────────────────────────────────────────────────────

# Patients per trip for each unit type
UNIT_CAPACITY: dict[str, int] = {"S": 1, "N": 1, "P": 2, "T": 4}
# Road speed assumption per type (km/h)
UNIT_SPEED_KMH: dict[str, float] = {"S": 70.0, "N": 65.0, "P": 75.0, "T": 90.0}
# Straight-line → road distance multiplier
_ROAD_FACTOR = 1.35

# Pool type mix: 40% T, 30% P, 20% S, 10% N
_TYPE_CYCLE = ["T", "T", "T", "T", "P", "P", "P", "S", "S", "N"]

# Patient ratio per total occupied beds
_RATIO_ICU = 0.05
_RATIO_WARD = 0.60
# ambulatory = remainder


# ── Pydantic models ───────────────────────────────────────────────────────────

class TransportUnit(BaseModel):
    unit_id: str
    call_sign: str
    unit_type: str          # T | N | P | S
    lat: float
    lon: float
    status: str             # available | en_route | unavailable
    distance_km: float
    eta_minutes: int


class PatientGroup(BaseModel):
    category: str           # icu | ward | ambulatory
    label: str              # human-readable Polish label
    count: int
    required_unit_type: str
    units_needed: int


class HospitalEvacOrder(BaseModel):
    hospital_id: str
    name: str
    lat: float
    lon: float
    priority: str           # NATYCHMIASTOWE | PILNE | PLANOWE
    patient_groups: list[PatientGroup]
    assigned_units: list[TransportUnit]
    units_needed: int
    units_available: int
    deficit: int
    transfer_target: str | None


# ── Unit pool generation ──────────────────────────────────────────────────────

def _generate_unit_pool(hospitals: list[HospitalFloodStatus]) -> list[dict]:
    """
    Generate a deterministic, spatially realistic pool of transport units.
    Uses hospital coordinates as bases with small geographic offsets.
    SOR hospitals generate 2 units; others generate 1.
    ~10% of units are randomly marked unavailable.
    """
    rng = random.Random(42)
    units: list[dict] = []
    idx = 0

    for h in hospitals:
        n = 2 if h.sor else 1
        for _ in range(n):
            unit_type = _TYPE_CYCLE[idx % len(_TYPE_CYCLE)]
            idx += 1
            lat = h.lat + rng.uniform(-0.05, 0.05)
            lon = h.lon + rng.uniform(-0.08, 0.08)
            uid = f"LU-{unit_type}-{idx:02d}"
            status = "unavailable" if rng.random() < 0.10 else "available"
            units.append({
                "unit_id": uid,
                "call_sign": uid,
                "unit_type": unit_type,
                "lat": lat,
                "lon": lon,
                "status": status,
            })

    return units


def _eta(distance_km: float, unit_type: str) -> int:
    road_km = distance_km * _ROAD_FACTOR
    speed = UNIT_SPEED_KMH.get(unit_type, 70.0)
    return max(1, round(road_km / speed * 60))


# ── Patient group derivation ──────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "icu": "OIT / OIOM",
    "ward": "Oddział ogólny",
    "ambulatory": "Ambulatoryjni",
}


def _patient_groups(h: HospitalFloodStatus) -> list[PatientGroup]:
    # personnel_pct as occupancy proxy (cap at 95%)
    occ = min(h.personnel_pct / 100, 0.95) * 0.90
    total = max(1, round(h.beds * occ))

    icu = max(1, round(total * _RATIO_ICU))
    ward = round(total * _RATIO_WARD)
    ambul = max(0, total - icu - ward)

    return [
        PatientGroup(
            category="icu",
            label=_CATEGORY_LABELS["icu"],
            count=icu,
            required_unit_type="S",
            units_needed=math.ceil(icu / UNIT_CAPACITY["S"]),
        ),
        PatientGroup(
            category="ward",
            label=_CATEGORY_LABELS["ward"],
            count=ward,
            required_unit_type="P",
            units_needed=math.ceil(ward / UNIT_CAPACITY["P"]),
        ),
        PatientGroup(
            category="ambulatory",
            label=_CATEGORY_LABELS["ambulatory"],
            count=ambul,
            required_unit_type="T",
            units_needed=math.ceil(ambul / UNIT_CAPACITY["T"]) if ambul else 0,
        ),
    ]


# ── Greedy unit assignment ────────────────────────────────────────────────────

def _assign(
    src_lat: float,
    src_lon: float,
    unit_type: str,
    n_needed: int,
    pool: list[dict],
    taken: set[str],
) -> list[TransportUnit]:
    candidates = [
        u for u in pool
        if u["unit_type"] == unit_type
        and u["status"] == "available"
        and u["unit_id"] not in taken
    ]
    candidates.sort(key=lambda u: haversine(src_lat, src_lon, u["lat"], u["lon"]))
    selected = candidates[:n_needed]

    result: list[TransportUnit] = []
    for u in selected:
        taken.add(u["unit_id"])
        d = round(haversine(src_lat, src_lon, u["lat"], u["lon"]), 1)
        result.append(TransportUnit(
            unit_id=u["unit_id"],
            call_sign=u["call_sign"],
            unit_type=u["unit_type"],
            lat=u["lat"],
            lon=u["lon"],
            status=u["status"],
            distance_km=d,
            eta_minutes=_eta(d, u["unit_type"]),
        ))
    return result


# ── Priority classification ───────────────────────────────────────────────────

def _priority(h: HospitalFloodStatus) -> str:
    if h.status == "evacuate":
        if h.generator_state == "offline" or any("P=1%" in f for f in h.risk_factors):
            return "NATYCHMIASTOWE"
        return "PILNE"
    return "PLANOWE"


# ── Public API ────────────────────────────────────────────────────────────────

def get_evacuation_dispatch(
    statuses: list[HospitalFloodStatus],
    transfer_map: dict[str, str] | None = None,
) -> list[HospitalEvacOrder]:
    """
    Build a full dispatch picture for hospitals in evacuate / at_risk status.

    transfer_map: hospital_id → transfer target short name.
    Hospitals are processed in priority order so the nearest units go to the
    most critical cases first.
    """
    sources = [s for s in statuses if s.status in ("evacuate", "at_risk")]
    if not sources:
        return []

    pool = _generate_unit_pool(statuses)
    taken: set[str] = set()

    # Critical cases first
    sources.sort(key=lambda h: (0 if h.status == "evacuate" else 1, -len(h.risk_factors)))

    orders: list[HospitalEvacOrder] = []
    for h in sources:
        groups = _patient_groups(h)

        assigned: list[TransportUnit] = []
        for g in groups:
            assigned.extend(_assign(h.lat, h.lon, g.required_unit_type,
                                    g.units_needed, pool, taken))

        units_needed = sum(g.units_needed for g in groups)
        deficit = max(0, units_needed - len(assigned))

        orders.append(HospitalEvacOrder(
            hospital_id=h.hospital_id,
            name=h.name,
            lat=h.lat,
            lon=h.lon,
            priority=_priority(h),
            patient_groups=groups,
            assigned_units=assigned,
            units_needed=units_needed,
            units_available=len(assigned),
            deficit=deficit,
            transfer_target=(transfer_map or {}).get(h.hospital_id),
        ))

    return orders
