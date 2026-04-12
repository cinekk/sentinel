"""
FloodScenarioPlugin — scripted flood simulation for demo.

Drives the Phase 9 Infrastruktura Medyczna dashboard through a realistic
crisis arc: gauges rise, 112 demand spikes, a hospital generator fails,
evacuation is triggered, AI recommends reallocation.

Script: Powódź Wisła — okolice Puławy
Tick interval: 15s real time ≈ 10 min narrative time
Max ticks: 12 (holds at steady state afterwards)

Control: POST /api/flood-scenario/start|stop|reset
         GET  /api/flood-scenario/state
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timezone

from database import EventRow, SessionLocal
from models import (
    CrisisEventAct,
    CrisisEventCreate,
    CrisisEventPatch,
    GaugeOverrideAct,
    HospitalOverrideAct,
    InjectEventsAct,
    ScriptAct,
)
from plugins.base import BasePlugin

logger = logging.getLogger(__name__)

# ── Scenario constants ────────────────────────────────────────────────────────

_PULAWY_LAT = 51.4158
_PULAWY_LON = 21.9698
_DEBLIN_LAT = 51.5627
_DEBLIN_LON = 21.8614

_MAX_TICK = 12
_DEFAULT_TICK_INTERVAL = 15  # seconds

# ── Hardcoded Puławy script ────────────────────────────────────────────────────
# Each entry: (tick, ScriptAct)

_PULAWY_SCRIPT: list[tuple[int, ScriptAct]] = [
    # Tick 1 — Wisła/Puławy gauge rises to warning
    (1, GaugeOverrideAct(near_lat=_PULAWY_LAT, near_lon=_PULAWY_LON, level="warning")),

    # Tick 2 — 4× medical 112 calls near Puławy hospital
    (2, InjectEventsAct(n=4, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=2.0, category="medical", severity="high")),

    # Tick 3 — Hospital Puławy: staff recalled from leave
    (3, HospitalOverrideAct(city="Puławy", personnel_pct=60)),

    # Tick 4 — Wisła/Puławy gauge escalates to alarm
    (4, GaugeOverrideAct(near_lat=_PULAWY_LAT, near_lon=_PULAWY_LON, level="alarm")),

    # Tick 5 — Ambulances overwhelmed: 10 more 112 calls
    (5, InjectEventsAct(n=10, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=3.0, category="medical", severity="high")),

    # Tick 6 — Generator degrades; flood crisis zone created
    (6, HospitalOverrideAct(city="Puławy", generator_state="degraded")),
    (6, CrisisEventAct(action="create", event_kwargs={
        "type": "flood",
        "lat": _PULAWY_LAT,
        "lon": _PULAWY_LON,
        "name": "Powódź — Wisła, okolice Puławy",
        "evac_radius_km": 2.0,
        "warn_radius_km": 8.0,
        "zone_shape": "circle",
        "source": "simulation",
    })),

    # Tick 7 — 6 more medical calls (ongoing surge)
    (7, InjectEventsAct(n=6, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=3.0, category="medical", severity="high")),

    # Tick 8 — Generator goes offline → hospital must evacuate
    (8, HospitalOverrideAct(city="Puławy", generator_state="offline")),

    # Tick 9 — Secondary front: Wieprz/Dęblin rises; Dęblin hospital generator degrades
    (9, GaugeOverrideAct(near_lat=_DEBLIN_LAT, near_lon=_DEBLIN_LON, level="warning")),
    (9, HospitalOverrideAct(city="Dęblin", generator_state="degraded")),

    # Tick 10 — 4 medical 112 calls near Dęblin
    (10, InjectEventsAct(n=4, lat=_DEBLIN_LAT, lon=_DEBLIN_LON, radius_km=2.0, category="medical", severity="high")),

    # Ticks 11–12: assessment engine detects Dęblin at_risk; simulation holds at tick 12
]


# ── Plugin ────────────────────────────────────────────────────────────────────

class FloodScenarioPlugin(BasePlugin):
    layer_id = "flood_scenario"
    layer_name = "Symulacja powodzi (Puławy)"
    data_type = "flood_scenario"

    def __init__(self) -> None:
        self._running = False
        self._tick = 0
        self._tick_interval = _DEFAULT_TICK_INTERVAL
        self._crisis_id: str | None = None
        self._task: asyncio.Task | None = None

    # ── Public control ────────────────────────────────────────────────────────

    def start(self, tick_interval_seconds: int = _DEFAULT_TICK_INTERVAL) -> None:
        if self._running:
            return
        self._tick_interval = tick_interval_seconds
        self._tick = 0
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("FloodScenarioPlugin started (tick_interval=%ds)", tick_interval_seconds)

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        asyncio.create_task(self._cleanup())

    def reset(self) -> None:
        self.stop()
        self._tick = 0
        self._crisis_id = None

    @property
    def running(self) -> bool:
        return self._running

    @property
    def tick(self) -> int:
        return self._tick

    @property
    def narrative_time_min(self) -> int:
        return self._tick * 10  # each tick ≈ 10 narrative minutes

    @property
    def next_act_tick(self) -> int | None:
        """Tick number of the next scheduled act, or None if past script end."""
        future = [t for (t, _) in _PULAWY_SCRIPT if t > self._tick]
        return min(future) if future else None

    @property
    def state(self) -> dict:
        h, m = divmod(self.narrative_time_min, 60)
        narrative_label = f"T+{h}h{m:02d}min" if h else f"T+{m}min"
        return {
            "running": self._running,
            "tick": self._tick,
            "max_tick": _MAX_TICK,
            "narrative_time_min": self.narrative_time_min,
            "narrative_label": narrative_label,
            "next_act_tick": self.next_act_tick,
            "crisis_id": self._crisis_id,
            "tick_interval_seconds": self._tick_interval,
        }

    # ── BasePlugin ────────────────────────────────────────────────────────────

    async def fetch(self) -> dict:
        """Return flood zone GeoJSON: growing circle + gauge marker features."""
        features: list[dict] = []

        if self._tick >= 6 and self._crisis_id:
            # Growing flood circle centred on Puławy
            radius_km = 2.0 + (self._tick - 6) * 0.5
            features.append({
                "type": "Feature",
                "geometry": _circle_polygon(_PULAWY_LAT, _PULAWY_LON, radius_km),
                "properties": {
                    "type": "flood_zone",
                    "tick": self._tick,
                    "radius_km": round(radius_km, 2),
                    "narrative_time": self.state["narrative_label"],
                },
            })

        if self._tick >= 9:
            # Secondary Dęblin zone (smaller)
            features.append({
                "type": "Feature",
                "geometry": _circle_polygon(_DEBLIN_LAT, _DEBLIN_LON, 1.0),
                "properties": {
                    "type": "flood_zone",
                    "tick": self._tick,
                    "radius_km": 1.0,
                    "narrative_time": self.state["narrative_label"],
                },
            })

        self._last_updated = datetime.now(timezone.utc)
        return {"type": "FeatureCollection", "features": features}

    # ── Tick loop ─────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        while self._running:
            await asyncio.sleep(self._tick_interval)
            if not self._running:
                break
            if self._tick < _MAX_TICK:
                self._tick += 1
                await self._execute_tick(self._tick)
            # After MAX_TICK: hold at steady state — no more acts, keep running

    async def _execute_tick(self, tick: int) -> None:
        acts = [act for (t, act) in _PULAWY_SCRIPT if t == tick]
        for act in acts:
            try:
                await self._execute_act(act)
            except Exception as exc:
                logger.error("FloodScenario tick %d act %s failed: %s", tick, act.act, exc)

    async def _execute_act(self, act: ScriptAct) -> None:  # type: ignore[override]
        if isinstance(act, GaugeOverrideAct):
            from plugins.imgw_hydro import set_gauge_override_by_location
            sid = set_gauge_override_by_location(act.near_lat, act.near_lon, act.level)
            if sid:
                logger.info("[Flood tick %d] Gauge %s → %s", self._tick, sid, act.level)
            else:
                logger.warning("[Flood tick %d] No gauge found near (%.4f, %.4f)", self._tick, act.near_lat, act.near_lon)
            # Invalidate flood assessment cache
            import services.flood_assessment as fa
            fa._cache = None
            fa._cache_time = None

        elif isinstance(act, InjectEventsAct):
            await self._inject_events(act)

        elif isinstance(act, HospitalOverrideAct):
            from services.flood_assessment import set_hospital_override_by_city
            patch: dict = {}
            if act.generator_state is not None:
                patch["generator_state"] = act.generator_state
            if act.personnel_pct is not None:
                patch["personnel_pct"] = act.personnel_pct
            if act.road_cut is not None:
                patch["road_cut"] = act.road_cut
            if patch:
                count = await set_hospital_override_by_city(act.city, patch)
                logger.info("[Flood tick %d] Hospital override city=%s patch=%s → %d hospitals", self._tick, act.city, patch, count)

        elif isinstance(act, CrisisEventAct):
            import services.crisis_store as crisis_store
            if act.action == "create":
                from models import CrisisEventCreate
                event = crisis_store.add(CrisisEventCreate(**act.event_kwargs))
                self._crisis_id = event.id
                logger.info("[Flood tick %d] CrisisEvent created: %s", self._tick, event.id)
            elif act.action == "patch" and act.crisis_id:
                from models import CrisisEventPatch
                crisis_store.patch(act.crisis_id, CrisisEventPatch(**act.event_kwargs))
            elif act.action == "resolve":
                cid = act.crisis_id or self._crisis_id
                if cid:
                    crisis_store.patch(cid, CrisisEventPatch(status="resolved"))

    async def _inject_events(self, act: InjectEventsAct) -> None:
        descriptions = [
            "Wypadek drogowy — zatopiona droga, poszkodowani",
            "Nagłe zatrzymanie krążenia, utrudniony dojazd karetki",
            "Uraz kończyny podczas ewakuacji przed powodzią",
            "Hipotermia — osoby z obszaru zalanego",
            "Wypadek z udziałem łodzi ewakuacyjnej",
            "Zasłabnięcie starszej osoby podczas ewakuacji",
            "Utonięcie — wyciągnięty z wody, resuscytacja w toku",
            "Zatrucie wodą powodziową",
            "Złamanie — poślizgnięcie na zalanych schodach",
            "Atak astmy — wzrost wilgotności po powodzi",
            "Uraz głowy — ewakuacja w silnym prądzie",
            "Przesiąkanie wałów — evacuacja wsi, ranni",
        ]

        lat_per_km = 1.0 / 111.0
        lon_per_km = 1.0 / (111.0 * math.cos(math.radians(act.lat)))

        async with SessionLocal() as session:
            for _ in range(act.n):
                angle = random.uniform(0, 2 * math.pi)
                dist_km = random.uniform(0, act.radius_km)
                lat = act.lat + dist_km * lat_per_km * math.sin(angle)
                lon = act.lon + dist_km * lon_per_km * math.cos(angle)
                row = EventRow(
                    latitude=round(lat, 6),
                    longitude=round(lon, 6),
                    category=act.category,
                    severity=act.severity,
                    status="active",
                    description=random.choice(descriptions),
                    source="simulation",
                    model="flood_scenario",
                )
                session.add(row)
            await session.commit()
        logger.info("[Flood tick %d] Injected %d %s events near (%.4f, %.4f)", self._tick, act.n, act.category, act.lat, act.lon)

    async def _cleanup(self) -> None:
        """Clear all overrides set by the simulation."""
        from plugins.imgw_hydro import clear_all_gauge_overrides
        from services.flood_assessment import clear_all_overrides
        clear_all_gauge_overrides()
        clear_all_overrides()

        if self._crisis_id:
            import services.crisis_store as crisis_store
            from models import CrisisEventPatch
            crisis_store.patch(self._crisis_id, CrisisEventPatch(status="resolved"))
            self._crisis_id = None

        logger.info("FloodScenarioPlugin: overrides cleared")


# ── Geometry helpers ──────────────────────────────────────────────────────────

def _circle_polygon(center_lat: float, center_lon: float, radius_km: float, n_points: int = 48) -> dict:
    lat_per_km = 1.0 / 111.0
    lon_per_km = 1.0 / (111.0 * math.cos(math.radians(center_lat)))
    coords = []
    for i in range(n_points + 1):
        theta = 2 * math.pi * i / n_points
        coords.append([
            center_lon + radius_km * lon_per_km * math.cos(theta),
            center_lat + radius_km * lat_per_km * math.sin(theta),
        ])
    return {"type": "Polygon", "coordinates": [coords]}
