# De Facto Architecture Analysis
**Date:** 2026-05-08  
**Scope:** Full codebase investigation against the WCZK 4-stage pipeline model  
**Investigator:** joint session — Tomasz + Claude

---

## What we investigated

We read every plugin, service, router, and the main app factory to understand what actually runs in production — not what the docs say. We then mapped the findings against the WCZK client requirements and the ideal pipeline:

```
Sources → Ingestion → Analysis/Thinking → Outputs
```

---

## Stage 1 — Sources (plugins/)

### What exists

| Plugin | Source | Live? | Voivodeship |
|---|---|---|---|
| `IMGWHydroPlugin` | IMGW public API | ✅ yes, 5-min cache | ❌ hardcoded `"lubelskie"` |
| `GIOSPlugin` | GIOŚ v1 API | ✅ yes, 15-min cache | ❌ hardcoded `"LUBELSKIE"` |
| `SimulationPlugin` | In-process tick loop | ✅ animates on start | Puławy (Lublin demo) |
| `FloodScenarioPlugin` | State machine | ✅ Lublin demo | Lublin demo |
| `FloodZonesPlugin` | Static ISOK file | ✅ loaded at startup | Lublin voivodeship |
| `HospitalsPlugin` | SQLite (`hospital_rows`) | ✅ seeded from seed_hospitals.py | Lublin |
| `SchoolsPlugin` | `data.json` static file | ✅ static | Lublin |
| `SocialPlugin` | `data.json` static file | ✅ static | Lublin |
| `FireStationsPlugin` | Hardcoded Python list | ✅ static | 15 Lublin stations |
| `HospitalStatusPlugin` | Derived — calls FloodAssessmentService | ✅ computed on request | Lublin |
| `TransportUnitsPlugin` | Derived — from hospital DB | ✅ computed on request | Lublin |
| `MockBoundaryPlugin` / `EventsPlugin` | In-memory | ✅ hackathon remnants | Mock |

### Key findings

**The plugin abstraction is real and clean.** `BasePlugin → fetch() → GeoJSON` works. New sources genuinely slot in with one file + one `registry.register()` line. This is worth keeping exactly as-is.

**Both live-data plugins are hardcoded to Lubelskie.** There is no `IMGW_VOIVODESHIP` config variable. The filter is a literal string comparison inside `_fetch_all_stations()` in `imgw_hydro.py` and inside `_fetch_lubelskie_stations()` in `gios.py`. Trivial fix, just hasn't been done.

**Weather data is not a plugin.** `WEATHER_DATA` in `routers/v1_layers.py` is a hardcoded Python list of 4 mock stations. It is not in the plugin registry, not live, and not configurable. It looks like a plugin from the outside but it is a constant.

**There is no scheduled background polling.** Every plugin only fetches when its `fetch()` is called by an HTTP request. IMGW and GIOŚ cache results for 5 min / 15 min respectively, but no background task runs on a timer. `SimulationPlugin` is the only thing with a background loop — and that is a demo animation, not a data ingestion scheduler. If no user hits a map endpoint for 15 minutes, IMGW data is simply not collected.

---

## Stage 2 — Ingestion / Processing

### The two disconnected paths

There are **two completely separate, non-communicating data paths**:

**Path A — Plugin GeoJSON (ephemeral, never persisted)**  
Plugins produce GeoJSON on every `fetch()` call. The data is returned as an HTTP response and then discarded. IMGW gauges, GIOŚ air quality, flood zones — all are stateless per-request reads with a short TTL cache. No history. No `gauge_readings` table. A gauge reading at alarm level produces a colored dot on the map and nothing else.

**Path B — EventRow (SQLite, write path)**  
`POST /api/events` writes `EventRow` to SQLite. `SimulationPlugin._execute_inject()` also writes `EventRow` rows directly inside its tick loop. These rows have `category`, `severity`, `status`, `description` — they are "classified incidents". They feed the Grafana dashboard and the text briefing.

**Path A and Path B are completely disconnected.** An IMGW gauge going to `"alarm"` level is invisible to the EventRow store. A GIOŚ station showing PM2.5 of 150 µg/m³ creates no event. The flood assessment service reads gauges from Path A's in-memory cache (`get_gauges_snapshot()`) and hospital rows from SQLite, computes a status — but the result is **never written anywhere**. It is recomputed on every HTTP request with a 2-minute cache.

### What the flood assessment actually does

`services/flood_assessment.py` is the most sophisticated piece of logic in the codebase. It fuses:
- IMGW gauge alert level (from Path A cache)
- ISOK flood zone classification per hospital
- 112 medical call density in a 15 km radius (from EventRow DB)
- Hospital overrides (generator state, road cut — in-memory dict)

The output is a `HospitalFloodStatus` per hospital: `operational / at_risk / evacuate`. This is good logic. The problem: it is entirely ephemeral. The result vanishes after 2 minutes and is never stored, never compared to previous assessments, never triggers anything downstream.

### What counts as "ingest" today

There is no ingestion pipeline that accepts free-text and classifies it in production. `routers/ingest.py` exists but is explicitly marked legacy in CLAUDE.md. `POST /api/events` requires the caller to supply pre-classified `category`, `severity`, `lat`, `lon` — there is no LLM in the write path.

---

## Stage 3 — Analysis / Thinking (LLM)

### What exists

**`services/assistant.py` — the only LLM call in production**

Takes a natural-language query ("show me hospitals near the fire"), calls OpenRouter with a structured JSON schema, returns a `ViewConfig` (which layers to show/hide on the map). This is **a UI configurator, not a crisis analyst**. It decides what to display; it does not analyze threats, generate new facts about the situation, or produce alerts.

**`services/briefing.py` — deterministic, explicitly no LLM**

Assembles text from templates + current data: active crises, affected facilities, evac counts, air quality, flood hospital status. The logic is rich and correct. Output goes to `services/tts.py` → ElevenLabs → MP3.

**`services/openrouter.py` — clean, reusable LLM client**

Well-structured, handles structured JSON output, handles model fallback, defensive JSON parsing for reasoning models. Ready to be called from new analysis hooks.

### What is missing from this stage

- No LLM reads sensor data and infers new facts (trend detection, escalation)
- No LLM generates draft communications for operators
- No LLM classifies incoming free-text or media articles
- The assistant has no memory of past events, no access to the EventRow history
- The briefing has no awareness of WCZK-specific reporting structure

---

## Stage 4 — Outputs

### What exists

| Output | Status | Notes |
|---|---|---|
| Map (Leaflet) | ✅ live | Consumes all plugin GeoJSON via `/api/layers/{id}/geojson` |
| REST API `/api/events` | ✅ live | Grafana-compatible flat JSON list |
| Voice briefing `/api/voice/briefing` | ✅ live | ElevenLabs TTS, text fallback |
| Crisis zone GeoJSON | ✅ live | Evac/warn radius polygons for Grafana |
| Affected facilities list | ✅ live | `/api/v1/crisis/affected` |
| PDF reports | ❌ missing | |
| Scheduled reports (06:30 / 18:30) | ❌ missing | No scheduler installed |
| Email delivery | ❌ missing | |
| Telegram delivery | ❌ missing | |
| WCZK operator panel | ❌ missing | Current UI is a technical demo map |
| Alert acknowledgement | ❌ missing | |

---

## The EventRow confusion

`EventRow` is one table serving three different purposes with different semantics:

1. **Raw simulation artifacts** — rows written by `SimulationPlugin._execute_inject()` at each tick. These are fake events for the demo.
2. **Classified crisis incidents** — rows that represent real (or operator-entered) significant occurrences: "industrial fire at Puławy".
3. **Sensor log entries** — `SimulationPlugin._persist_event()` writes a row every 10 seconds with PM2.5 readings. These are time-series data masquerading as events.

The missing fourth type — **raw gauge readings** from IMGW — never gets written at all because there is no mechanism to do so. This is the gap between Path A and Path B.

---

## The in-memory crisis_store problem

`services/crisis_store.py` is a plain Python dict. Active crisis events — including geometry, evac/warn radii, status — live only in process memory. A restart wipes all of them. For an operational system this is a blocker: the duty officer would lose the current picture on every deploy.

---

## Summary of structural decisions that need changing

| Issue | Severity | Fix |
|---|---|---|
| No `gauge_readings` / observations persistence | Critical | New table, DataWriter service |
| Path A (plugins) and Path B (events) are disconnected | Critical | Hook registry between them |
| No background scheduler | Critical | APScheduler in lifespan |
| `crisis_store` in-memory only | High | Persist to SQLite |
| `EventRow` conflates readings, incidents, artifacts | Medium | Add `observations` table, clean up EventRow semantics |
| Both live plugins hardcoded to Lubelskie | High | Config var `IMGW_VOIVODESHIP` |
| No output plugins (reports, alerts) | Medium | New `BaseReport`, `BaseAlert` abstractions |
| Weather data is a hardcoded constant, not a plugin | Low | Make it a plugin or a real API call |
