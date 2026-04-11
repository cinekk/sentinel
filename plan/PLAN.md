# SENTINEL — Master Plan

> Civil42 Hackathon · 11–12.04.2026
> Prize target: Marszałek Województwa Lubelskiego (10 000 PLN) + ElevenLabs + Comtegra side quests

## What we're building

**SENTINEL** is a backend platform for real-time crisis situational awareness.
It powers a thin owned frontend and optionally syncs to external consumers:
- **Leaflet map** (owned) — primary demo surface; renders GeoJSON layers directly from our API
- **Grafana** dashboard — flat JSON events feed
- **useMaps** (TENTEC Polska GIS) — GeoJSON feature layers pushed via API (bonus, with fallback)

Core concept: **hexagonal architecture with pluggable data sources.**
Each plugin declares a layer, fetches/generates data, and the core serves it uniformly.
Demo scenario: **Zestaw D — industrial fire / smog crisis** in Lublin voivodeship.

---

## Architecture overview

```
[Plugins]                      [Core]                  [Output]
  SimulationPlugin  ──►
  GIOSPlugin        ──►   PluginRegistry          GET /api/events        → Grafana
  ResourcePlugin    ──►   EventStore (SQLite)      GET /api/layers/{id}/geojson → map
                    ──►  ResourceStore            POST → useMaps API     (push sync)
                    ──►  LayerCache               GET /api/simulation/*  → demo control

[AI]      LLMRouter: Claude → Ollama fallback
[Spatial] spatial.py: threat zone ∩ sensitive objects → targeted alerts
[STT]     ElevenLabs → voice ingest
[TTS]     ElevenLabs → broadcast alerts
[Frontend] frontend/index.html — Leaflet map, layer toggles, served via FastAPI /static
```

Coordinate system: internal WGS84 (EPSG:4326), transformed to EPSG:2180 on useMaps push.

---

## Phases

| Phase | File | Status |
|---|---|---|
| 1 — Core Foundation | *(completed, no separate file)* | ✅ Done |
| 2 — Thin Frontend | *(completed, no separate file)* | ✅ Done |
| 3 — Simulation Engine | *(completed, no separate file)* | ✅ Done |
| 4 — Resource Data Plugins | *(completed, no separate file)* | ✅ Done |
| 4b — Crisis API | *(completed, no separate file)* | ✅ Done |
| 5 — Real Air Quality (GIOŚ) | [PHASE-5-gios.md](PHASE-5-gios.md) | 🔲 Not started |
| 6 — AI Classification & Voice | [PHASE-6-ai-voice.md](PHASE-6-ai-voice.md) | 🔲 Not started |
| 7 — useMaps Integration | [PHASE-7-usemaps.md](PHASE-7-usemaps.md) | 🔲 Not started |
| 8 — Polish & Demo | [PHASE-8-demo.md](PHASE-8-demo.md) | 🔲 Not started |

---

## Completed phases summary

### Phase 1 — Core Foundation ✅
- `requirements.txt`, `.env.example`, `database.py`, `models.py`
- `plugins/base.py` — `BasePlugin` ABC + `PluginRegistry`
- `routers/events.py` — `GET /api/events`
- `main.py` — FastAPI app, CORS, lifespan startup

### Phase 2 — Thin Frontend ✅
- `frontend/index.html` — single-file Leaflet app, CDN, no build step
- Lublin voivodeship + powiaty boundary, layer panel, auto-refresh 30s, popups

### Phase 3 — Simulation Engine ✅
- `plugins/simulation.py` — background task, plume spreading, threat zone ellipse
- `routers/simulation.py` — start/stop/state endpoints
- `services/spatial.py` — `check_intersections(threat_zone, resources)`
- Preset: Puławy chemical plant, wind NE 15 km/h

### Phase 4 — Resource Data Plugins ✅
- `plugins/resources.py` — `HospitalsPlugin`, `SocialPlugin`, `SchoolsPlugin`, `FireStationsPlugin`
- 1 791 total resources; 663 within 50 km of Puławy
- `routers/resources.py` — `/api/resources` + `/api/resources/calculator`
- Real Lublin voivodeship boundary from Nominatim OSM (16 814-point polygon)

### Phase 4b — Crisis API ✅
- `services/crisis_store.py` — in-memory CrisisEvent store (type, lat, lon, name, radii, status, source)
- `services/spatial.py` — `haversine()`, `circle_polygon()`, `facilities_in_zones()`
- `routers/crisis.py` — `POST/GET/PATCH/DELETE /api/v1/crisis` + stats + affected + geojson
- `routers/fires_compat.py` — `/api/v1/fires` alias (operator script compatibility)
- `routers/v1_layers.py` — `/api/v1/layers/hospitals|schools|social-facilities|air-quality|weather`
- `main.py` — register new routers (v0.5.0)

---

## Key API surface

```
GET  /api/events                          Grafana flat JSON feed
POST /api/events                          Manual event creation
POST /api/ingest                          Raw input → AI classify → save
GET  /api/layers                          Layer registry with metadata
GET  /api/layers/{id}/geojson             GeoJSON FeatureCollection
GET  /api/resources                       Flat resource list
GET  /api/resources/calculator            Resource count in radius
POST /api/simulation/start                Start fire scenario
POST /api/simulation/stop
GET  /api/simulation/state                Current threat zone + stats
POST /api/voice                           Audio → STT → ingest
POST /api/voice/command                   Voice command → action + TTS response
POST /api/sync                            Force push all layers to useMaps
GET  /api/health                          System status
GET  /                                    Leaflet map frontend
```

---

## Open questions

- [ ] useMaps layer IDs — need to be created in useMaps UI first; get IDs from teammate
- [ ] useMaps instance URL — confirm with teammate (env var `USEMAPS_BASE_URL`)
- [ ] Grafana exact datasource plugin — teammate to confirm; we expose both flat JSON and GeoJSON
- [ ] Ollama model availability on demo machine — confirm `qwen2.5:14b` is pulled

---

## Files index

```
sentinel/
  main.py
  models.py
  database.py
  config.py
  data.json                  hospitals (57), schools (1460), social_facilities (259)
  plugins/
    base.py                  BasePlugin ABC
    __init__.py              PluginRegistry
    mock_boundary.py         Lublin voivodeship boundary + powiaty centroids
    simulation.py            SimulationPlugin ✅
    resources.py             HospitalsPlugin, SocialPlugin, SchoolsPlugin, FireStationsPlugin ✅
    gios.py                  GIOSPlugin [Phase 5]
  routers/
    events.py                GET/POST /api/events ✅
    layers.py                GET /api/layers, GET /api/layers/{id}/geojson ✅
    simulation.py            simulation start/stop/state ✅
    resources.py             /api/resources + calculator ✅
    ingest.py                POST /api/ingest [Phase 6]
    voice.py                 POST /api/voice, /api/voice/command [Phase 6]
    sync.py                  POST /api/sync [Phase 7]
  services/
    spatial.py               check_intersections() ✅
    ai.py                    classify_event() [Phase 6]
    llm.py                   LLMRouter [Phase 6]
    tts.py                   ElevenLabs TTS+STT [Phase 6]
    usemaps.py               UseMapsClient [Phase 7]
    sync.py                  SyncService [Phase 7]
  frontend/
    index.html               Leaflet map ✅
    app.js                   ✅
    style.css                ✅
    geojson/
      lublin_voivodeship.geojson ✅
  scripts/
    seed_demo.py             [Phase 8]
  tests/
    conftest.py
    test_api.py
    test_plugins.py
    test_simulation.py       ✅
    test_spatial.py          ✅
  plan/
    PLAN.md                  ← this index
    PHASE-5-gios.md
    PHASE-6-ai-voice.md
    PHASE-7-usemaps.md
    PHASE-8-demo.md
    DEMO_SCRIPT.md           [Phase 8]
```
