# Phase 10 — Flood Scenario Simulation Engine

> **Goal:** A scripted, auto-advancing flood scenario that drives the Phase 9 Infrastruktura
> Medyczna dashboard through a realistic crisis arc — gauges rise, 112 demand spikes, a hospital
> generator fails, evacuation is triggered, AI recommends reallocation.
>
> Replaces `scripts/seed_flood_demo.py`. All data flows through the same stores Phase 9 reads,
> so no special simulation-only code paths in the assessment layer.

**Status:** 🔲 Not started  
**Depends on:** Phase 9 complete (flood assessment service + gauge/hospital override APIs)

---

## Design principle

The fire simulation is physics-based (ellipse grows each tick).  
The flood simulation is **script-based** — a list of `(tick, Act)` pairs that fire on schedule.

Each `Act` is a small mutation: override a gauge level, inject 112 events, set a hospital
override, or create/patch a CrisisEvent. The assessment layer (`FloodAssessmentService`) sees
these mutations through its normal inputs — no simulation-awareness needed there.

```
FloodScenarioPlugin
  _script: list[ScriptAct]   ← hardcoded Puławy scenario
  _tick: int                 ← current tick (each tick = 15s real time = ~10 min narrative time)
  _loop()                    ← background asyncio task, same as SimulationPlugin

ScriptAct (union type):
  GaugeOverrideAct(station_id, level)               → patched into IMGWHydroPlugin override dict
  InjectEventsAct(n, lat, lon, radius_km, category) → writes N EventRows near a location
  HospitalOverrideAct(hospital_id, **fields)        → patched into hospital override dict
  CrisisEventAct(action, **kwargs)                  → add/patch/resolve in crisis_store
```

---

## Scenario: Powódź — Wisła, okolice Puławy

City: Puławy (same reference point as fire simulation — consistent demo geography).  
Tick interval: **15 seconds** real time (each tick ≈ ~10 minutes of narrative time).

| Tick | Narrative time | Act |
|------|---------------|-----|
| 0 | T+0h | Scenario starts — all gauges normal, hospitals operational |
| 1 | T+10min | Wisła/Puławy gauge → `"warning"` (ostrzeżenie) |
| 2 | T+20min | 4× medical 112 calls injected near Szpital Puławy |
| 3 | T+30min | Hospital Puławy: `personnel_pct` → 60 (staff recalled from leave) |
| 4 | T+40min | Wisła/Puławy gauge → `"alarm"` |
| 5 | T+50min | 10× medical 112 calls (ambulances overwhelmed) |
| 5 | T+50min | Hospital Puławy: `beds_available` → 95% capacity |
| 6 | T+1h | Hospital Puławy: `generator_state` → `"degraded"` |
| 6 | T+1h | CrisisEvent created: `type="flood"`, circle zone around Puławy |
| 7 | T+1h10 | Assessment: Hospital Puławy crosses → `AT_RISK` |
| 7 | T+1h10 | 6× medical 112 calls (ongoing) |
| 8 | T+1h20 | Hospital Puławy: `generator_state` → `"offline"` |
| 8 | T+1h20 | Assessment: Hospital Puławy crosses → `EVACUATE` |
| 9 | T+1h30 | Wieprz/Dęblin gauge → `"warning"` (secondary front) |
| 9 | T+1h30 | Hospital Dęblin (Szpital Rejonowy): `generator_state` → `"degraded"` |
| 10 | T+1h40 | 4× medical 112 calls near Dęblin |
| 11 | T+1h50 | Assessment: Hospital Dęblin → `AT_RISK` |
| 12 | T+2h | Simulation holds (repeats last tick data — steady state for demo questions) |

At tick 12, the AI summary should read roughly:
> *"Szpital w Puławach wymaga natychmiastowej ewakuacji (brak generatora, strefa alarmowa).
> Szpital w Dęblinie w stanie podwyższonej gotowości. Zalecane przekierowanie pacjentów do
> Szpitala Miejskiego w Lublinie (310 wolnych łóżek, SOR operacyjny)."*

---

## Tasks

### 1. Script Act models — `models.py`

- [ ] Add to `models.py`:

```python
from typing import Literal, Union
from pydantic import BaseModel

class GaugeOverrideAct(BaseModel):
    act: Literal["gauge_override"] = "gauge_override"
    station_id: str
    level: Literal["normal", "warning", "alarm"]

class InjectEventsAct(BaseModel):
    act: Literal["inject_events"] = "inject_events"
    n: int
    lat: float
    lon: float
    radius_km: float = 2.0
    category: str = "medical"
    severity: str = "high"

class HospitalOverrideAct(BaseModel):
    act: Literal["hospital_override"] = "hospital_override"
    hospital_id: str                    # matches name or ID in data.json
    generator_state: str | None = None  # "ok" | "degraded" | "offline"
    personnel_pct: int | None = None
    road_cut: bool | None = None

class CrisisEventAct(BaseModel):
    act: Literal["crisis_event"] = "crisis_event"
    action: Literal["create", "patch", "resolve"]
    crisis_id: str | None = None        # required for patch/resolve
    event_kwargs: dict = {}             # passed to CrisisEventCreate or CrisisEventPatch

ScriptAct = Union[GaugeOverrideAct, InjectEventsAct, HospitalOverrideAct, CrisisEventAct]

class FloodScript(BaseModel):
    acts: list[tuple[int, ScriptAct]]   # (tick, act)
```

---

### 2. `FloodScenarioPlugin` — `plugins/flood_scenario.py`

- [ ] `FloodScenarioPlugin(BasePlugin)`
  - `layer_id = "flood_scenario"`, `layer_name = "Symulacja powodzi (Puławy)"`
  - Holds reference to `IMGWHydroPlugin` and hospital override dict (from Phase 9)
  - On `start()`:
    - Sets `_tick = 0`, `_running = True`
    - Fires tick-0 acts (reset all overrides to baseline)
    - Launches `_loop()` task
  - `_loop()`: same pattern as `SimulationPlugin._loop()`
    - `await asyncio.sleep(tick_interval_seconds)` (15s)
    - Advance tick, execute all acts for current tick
    - If tick > MAX_TICK: hold at steady state (no more acts, keep running)
  - On `stop()`: clears all overrides, resolves any flood CrisisEvents, `_running = False`
  - On `reset()`: `stop()` + `_tick = 0`
  - `state` property: `running`, `tick`, `narrative_time_min`, `active_acts_summary`

- [ ] `_execute_act(act: ScriptAct)`:
  - `GaugeOverrideAct` → calls `imgw_plugin.set_mock_override(station_id, level)`
  - `InjectEventsAct` → writes `n` `EventRow`s with jitter around `(lat, lon)`
  - `HospitalOverrideAct` → updates shared override dict (same one `FloodAssessmentService` reads)
  - `CrisisEventAct` → delegates to `crisis_store`

- [ ] `fetch()` → returns GeoJSON with current flood zone polygon (simple circle around Puławy,
  grows each tick after tick 6) + active gauge markers as features

- [ ] Hardcode `_PULAWY_SCRIPT: FloodScript` inline (no external file needed for hackathon)

---

### 3. IMGWHydroPlugin mock override — `plugins/imgw_hydro.py`

Phase 9 fetches real IMGW data. Simulation needs to override specific gauges.

- [ ] Add `_mock_overrides: dict[str, str]` to `IMGWHydroPlugin`
- [ ] `set_mock_override(station_id: str, level: str)` — sets override
- [ ] `clear_mock_overrides()` — removes all overrides
- [ ] In `fetch()`: if station_id in overrides → use mock level instead of computed level
- [ ] Expose override state in `GET /api/gauges/overrides` (for debug/demo)

---

### 4. Simulation control endpoints — `routers/flood_scenario.py`

```
POST /api/flood-scenario/start    Start scripted flood simulation
POST /api/flood-scenario/stop     Stop + clear all overrides
POST /api/flood-scenario/reset    Stop + reset tick to 0
GET  /api/flood-scenario/state    {running, tick, narrative_time_min, next_act_tick}
```

- [ ] Same pattern as `routers/simulation.py`
- [ ] `start` accepts optional `tick_interval_seconds` override (default 15, for fast-forward demo)

---

### 5. Frontend integration

- [ ] **Scenario selector** in the Infrastruktura Medyczna tab:
  - "Scenariusz: Powódź Puławy" toggle / play button
  - Shows current narrative time: `"T+1h20min"` 
  - Stop/Reset buttons
- [ ] When simulation running: auto-refresh hospital table and AI summary every 15s
  (matches tick interval; currently 5min — too slow for live demo)
- [ ] Optionally: small timeline bar showing tick progress (12 ticks = full scenario)

---

### 6. Retire `scripts/seed_flood_demo.py`

- [ ] Remove `scripts/seed_flood_demo.py` (replaced by this simulation)
- [ ] `scripts/` only keeps: `seed_demo.py` (fire scenario seed, can be kept or also retired
  in favor of the existing fire `SimulationPlugin`)

---

## Integration with existing fire simulation

Both simulations (`SimulationPlugin` and `FloodScenarioPlugin`) can run independently.
Convention: **only one scenario active at a time** — `start()` on one should `stop()` the other.

- [ ] In `main.py` startup: register both plugins
- [ ] Add mutual-exclusion check: if fire sim is running when flood sim starts, stop fire sim first
  (and vice versa)

---

## Smoke test

1. `POST /api/flood-scenario/start` with `tick_interval_seconds=2` (fast-forward)
2. After 4s (tick 2): `GET /api/flood/assessment` — Puławy hospitals still operational
3. After 10s (tick 5): assessment shows increased 112 demand
4. After 18s (tick 9): Puławy hospital → `"evacuate"`, Dęblin → `"at_risk"`
5. `GET /api/flood/summary` → LLM recommends evacuation + redirect
6. Frontend Infrastruktura Medyczna tab shows red/orange hospital markers updating live
7. `POST /api/flood-scenario/reset` → all hospitals back to `"operational"`, gauges normal
8. Fire sim can still start independently after reset

---

## Out of scope

- Configurable scenario parameters (city, hospital IDs, tick counts) — hardcoded Puławy is fine
- Saving simulation run history
- Concurrent multi-scenario execution
