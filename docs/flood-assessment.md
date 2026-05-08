# Flood Assessment

## Purpose

Combines three live data sources to classify every hospital as `operational`,
`at_risk`, or `evacuate`. Drives the evacuation dispatch system and voice
briefing hospital status blocks.

No LLM involved — purely rule-based.

---

## Data Sources

| Source | What it provides | How it's accessed |
|---|---|---|
| IMGW gauges | River alert level per station (`normal` / `warning` / `alarm`) | `plugins.imgw_hydro.get_gauges_snapshot()` |
| ISOK flood zones | Whether a point falls in a 1% or 10% flood probability zone | `services.flood_zones.point_in_flood_zone(lat, lon)` |
| 112 events DB | Count of medical calls within 15 km in the last 2 hours | `SELECT` from `EventRow` where `category="medical"` |

IMGW gauges update approximately every 15 minutes from the live API.
ISOK flood zones are static polygons loaded at startup.
112 call counts are live from the SQLite DB.

---

## Assessment Rules

Applied per hospital in `_assess_one()`:

### EVACUATE — any of these triggers it

| Condition | Risk factor label |
|---|---|
| Hospital point in ISOK P=1% flood zone | "Drogi dojazdu odcięte (ISOK P=1%)" |
| `road_cut` override is set | "Drogi dojazdu odcięte (ISOK P=1%)" |
| In P=10% zone **and** nearest gauge at `alarm` | "Szpital w strefie P=10% + alarm powodziowy (…)" |
| Generator override set to `offline` | "Brak zasilania awaryjnego" |

### AT_RISK — any of these, if not already EVACUATE

| Condition | Threshold | Risk factor label |
|---|---|---|
| In P=10% zone + nearest gauge at `warning` | — | "Szpital w strefie P=10% + ostrzeżenie powodziowe (…)" |
| Generator state `degraded` | — | "Zasilanie awaryjne w trybie degradacji" |
| Medical 112 call density | > 10 calls / 15 km / 2h | "Wysoki napływ wzywań 112 w okolicy (N w ciągu 2h)" |

### OPERATIONAL

No EVACUATE or AT_RISK conditions triggered.

### `can_receive` flag

`True` when: `status == "operational"` AND `demand_112 ≤ 10` AND `beds > 20`.
Used by the evacuation dispatch to identify transfer targets.

---

## HospitalFloodStatus Fields

```python
hospital_id: str          # facility_id from DB, or str(row.id)
name: str
lat: float
lon: float
status: "operational" | "at_risk" | "evacuate"
risk_factors: list[str]   # human-readable Polish strings
beds: int                 # beds_total_physical
sor: bool                 # has_sor
generator_state: str      # "ok" | "degraded" | "offline"
personnel_pct: int        # 0–100 (used as occupancy proxy in evacuation dispatch)
nearest_gauge: str | None
nearest_gauge_level: str | None  # "normal" | "warning" | "alarm" | "unknown"
demand_112: int
can_receive: bool
```

---

## Override System

For demo use — allows the flood scenario script to change hospital state
without altering DB records.

**Functions:**
- `set_hospital_override(facility_id, patch)` — patch `generator_state`, `personnel_pct`, `road_cut`
- `set_hospital_override_by_city(city_name, patch)` — applies to all hospitals in a city (case-insensitive)
- `clear_all_overrides()` — resets all overrides, invalidates cache

All overrides invalidate the cache immediately.

**Mock defaults** (no override set):
- Hospitals in flood-prone cities (Puławy, Dęblin, Annopol, Kazimierz Dolny, Włodawa, Hrubieszów): `generator_state="degraded"`, `personnel_pct=65`
- All others: `generator_state="ok"`, `personnel_pct=85`

Mock defaults are stable per `facility_id` (set once, cached in `_hospital_mock_state`).

---

## Caching

Results are cached in-memory for **120 seconds**.

Cache is invalidated by:
- Any call to `set_hospital_override()` or `clear_all_overrides()`
- Any `GaugeOverrideAct` executed by the flood scenario script

The 2-minute TTL is a balance between gauge update frequency (~15 min)
and 112 call liveness (real-time). The flood scenario invalidates the cache
directly on each tick so changes appear immediately during a demo.

---

## Entry Points

`assess_hospitals() -> list[HospitalFloodStatus]` — called from:
- `routers/voice.py` `_build_briefing_text()` when flood scenario is running
- `services/evacuation.py` `get_evacuation_dispatch()` (via caller)
- The flood assessment API endpoint (if exposed via `routers/flood.py`)
