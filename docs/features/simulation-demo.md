# Simulation & Demo Scenarios

## Overview

SENTINEL has two parallel simulation systems that can run independently
or together during a demo:

| System | Controls | What it drives |
|---|---|---|
| **SimulationPlugin** (chemical/fire) | `POST /api/simulation/start|stop|reset` | Spreading threat ellipse + PM2.5/PM10 plume on the map |
| **FloodScenarioPlugin** (flood) | `POST /api/flood-scenario/start|stop|reset` | Scripted Wisła flood arc — gauges, hospitals, 112 calls |
| **CallGenerator** (112 calls) | `POST /api/emergency/start|pause|resume|reset` | Synthetic 112 emergency call events in the DB |

These are independent — each has its own start/stop/reset. For the full
Zestaw A demo, all three are typically run together.

---

## Zestaw D — Chemical Fire (Primary Demo)

**Scenario:** Industrial fire + chemical plume at Puławy chemical plant.

**Driven by:** `SimulationPlugin` (`plugins/simulation_threat.py`)

**What it produces:**
- A spreading ellipse on the map (`simulation_threat` layer) — grows each tick
- PM2.5/PM10 concentration in plume properties
- Direction follows wind bearing configured at start

**Start:**
```http
POST /api/simulation/start
{
  "source_lat": 51.4158,
  "source_lon": 21.9698,
  "wind_speed_kmh": 15.0,
  "wind_direction_deg": 45.0,
  "fire_intensity": 1.0,
  "tick_interval_seconds": 10
}
```
Body is optional — defaults to Puławy coordinates, NE wind, 10s ticks.

**State:** `GET /api/simulation/state` returns `running`, `tick`, `config`.

---

## Zestaw A — Flood Scenario (Secondary Demo)

**Scenario:** Wisła river flood, Puławy area. 12-tick scripted arc, each tick
= 15 seconds real time = ~10 minutes narrative time. Max narrative duration: ~2 hours.

### Script Timeline (`plugins/flood_scenario.py`)

| Tick | Narrative | Actions |
|---|---|---|
| 1 | T+10min | Wisła/Puławy gauge → **warning** |
| 2 | T+20min | 4× medical 112 calls near Puławy hospital |
| 3 | T+30min | Puławy hospital: `personnel_pct=60` (staff recalled) |
| 4 | T+40min | Wisła/Puławy gauge → **alarm** |
| 5 | T+50min | 10× medical 112 calls near Puławy (ambulances overwhelmed) |
| 6 | T+1h | Puławy hospital: `generator_state=degraded` + CrisisEvent created |
| 7 | T+1h10min | 6× more medical 112 calls |
| 8 | T+1h20min | Puławy hospital: `generator_state=offline` → **EVACUATE** triggered |
| 9 | T+1h30min | Wieprz/Dęblin gauge → **warning** + Dęblin hospital: `generator_state=degraded` |
| 10 | T+1h40min | 4× medical 112 calls near Dęblin |
| 11–12 | T+1h50–2h | Assessment engine detects Dęblin **AT_RISK**; scenario holds at steady state |

After tick 12 the plugin keeps running but executes no more acts — system
holds at steady state until manually stopped.

### Act Types

**`GaugeOverrideAct`** — sets a river gauge's alert level by nearest-coordinate
lookup. Calls `plugins.imgw_hydro.set_gauge_override_by_location()` and
directly invalidates the flood assessment cache.

**`InjectEventsAct`** — writes N `EventRow` records (`source="simulation"`,
`model="flood_scenario"`) randomly distributed within `radius_km` of the
given coordinate.

**`HospitalOverrideAct`** — calls
`services.flood_assessment.set_hospital_override_by_city()` to patch
`generator_state`, `personnel_pct`, or `road_cut` for all hospitals in a city.

**`CrisisEventAct`** — creates, patches, or resolves a `CrisisEvent` in the
in-memory crisis store. The flood scenario stores the created event's ID
and resolves it on `stop()`.

### Flood Zone GeoJSON

`FloodScenarioPlugin.fetch()` returns the growing flood circle geometry:
- From tick 6: circle centred on Puławy, radius = `2.0 + (tick - 6) × 0.5 km`
- From tick 9: additional 1 km circle centred on Dęblin

### Cleanup on Stop

`stop()` triggers `_cleanup()` which:
1. Clears all IMGW gauge overrides
2. Clears all hospital overrides (restores mock defaults)
3. Resolves the flood CrisisEvent in the crisis store

112 simulation events are **not** auto-deleted on stop — use
`DELETE /api/emergency/events` or `POST /api/emergency/reset` to clear them.

### Control Endpoints

```
POST /api/flood-scenario/start   {"tick_interval_seconds": 15}
POST /api/flood-scenario/stop    — clears all overrides, resolves crisis
POST /api/flood-scenario/reset   — stop + tick back to 0
GET  /api/flood-scenario/state   → {running, tick, max_tick, narrative_time_min,
                                     narrative_label, next_act_tick, crisis_id,
                                     tick_interval_seconds}
```

---

## CallGenerator — Synthetic 112 Calls

Simulates a flood crisis arc via `services/call_generator.py`. Runs an async
tick loop (30s per tick) through 6 phases across ~24 ticks (~12 min wall time,
representing ~6 hours narrative time).

All events tagged `source="simulation"`, `model="112_sim"`.

### Phases

| Phase | Ticks | Character |
|---|---|---|
| 0 | 0–3 | Normal scattered medical calls |
| 1 | 4–7 | First riverside calls, minor flooding |
| 2 | 8–11 | Cluster near Puławy/Wisła, roads blocked |
| 3 | 12–15 | Evacuation requests, dialysis/oxygen patients |
| 4 | 16–19 | Hospital flood zone vicinity, ZRM response slowing |
| 5 | 20+ | Sectors cut off, no ZRM available |

Each tick: 2–4 events from 12 flood-prone locations, ±1.5 km jitter,
7 ZRM unit names randomly assigned.

### Control Endpoints

```
POST /api/emergency/start
POST /api/emergency/pause
POST /api/emergency/resume
POST /api/emergency/reset     — stops loop, schedules DELETE of simulation events
DELETE /api/emergency/events  — immediate DB delete of all source="simulation" events
```

---

## Typical Demo Sequence

**Full Zestaw A (flood):**
```
1. POST /api/emergency/start          — start 112 call generator
2. POST /api/flood-scenario/start     — start scripted flood arc
   (watch map for 3 minutes as ticks execute)
3. POST /api/voice/briefing           — generate spoken situation report
4. GET  /api/flood-scenario/state     — check narrative time and crisis_id
5. POST /api/flood-scenario/stop      — clean up overrides, resolve crisis
6. POST /api/emergency/reset          — clear 112 simulation events
```

**Full Zestaw D (chemical fire):**
```
1. POST /api/simulation/start         — start plume simulation
2. POST /api/crisis         (body: Puławy fire CrisisEvent)
3. POST /api/voice/briefing           — spoken report with PM2.5/plume context
4. POST /api/simulation/stop
```
