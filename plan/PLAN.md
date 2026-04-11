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

- [x] `services/crisis_store.py` — in-memory CrisisEvent store (type, lat, lon, name, radii, status, source)
- [x] `services/spatial.py` — add `haversine()`, `circle_polygon()`, `facilities_in_zones()`
- [x] `routers/crisis.py` — `POST/GET/PATCH/DELETE /api/v1/crisis` + stats + affected + geojson endpoints
- [x] `routers/fires_compat.py` — `/api/v1/fires` alias (operator script compatibility)
- [x] `routers/v1_layers.py` — `/api/v1/layers/hospitals|schools|social-facilities|air-quality|weather`
- [x] `plugins/resources.py` — add `display_type` property (`"Szpital"`, `"Szkoła"`, `"DPS/Placówka"`)
- [x] `main.py` — register new routers (v0.5.0)

### Phase 4c — Unified Crisis/Simulation Architecture
> Goal: simulation writes to crisis_store; all alerts go through one path; ellipse zones replace circles for simulation
> Detail: `plan/phase-4c-unified-crisis.md`

- [x] `models.py` — add `zone_shape`, `semi_major_km`, `semi_minor_km`, `bearing_deg` to `CrisisEvent` / `CrisisEventCreate` / `CrisisEventPatch`
- [x] `services/spatial.py` — extend `facilities_in_zones` to handle ellipse shape; add `level` + `resource_name` to returned dicts; delete `check_intersections`
- [x] `plugins/simulation.py` — on start: `crisis_store.add(...)` with `zone_shape="ellipse"`; each tick: `crisis_store.patch(...)` growing ellipse; stop/reset update status; drop `self._alerts` and `self._threat_zone`
- [x] `routers/simulation.py` — drop `alerts` + `threat_zone` from `GET /api/simulation/state`
- [x] `frontend/app.js` — remove `renderAlertHud(state.alerts)` from simulation poll; add independent `/api/v1/crisis/affected` poller for HUD
- [ ] Smoke test: manual crisis event + simulation event both show in HUD via same endpoint

### Phase 5 — Real Air Quality Data (GIOŚ)
> Goal: real PM2.5/PM10 displayed alongside simulation — earns +10 bonus points

- [ ] `plugins/gios.py` — `GIOSPlugin`
  - [ ] Fetch PM2.5/PM10 from GIOŚ REST API (v1, no auth):
    - stations: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll`
    - sensors per station: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors/{stationId}`
    - readings: `GET https://api.gios.gov.pl/pjp-api/v1/rest/data/getData/{sensorId}`
    - AQ index: `GET https://api.gios.gov.pl/pjp-api/v1/rest/aqindex/getIndex/{stationId}`
  - [ ] Filter to stations in Lublin voivodeship (bbox filter by coords)
  - [ ] Returns GeoJSON FeatureCollection with sensor readings as properties
  - [ ] Cache with 10-min TTL (API is slow)
- [ ] Simulation synthetic PM layer displayed separately alongside real GIOŚ layer
- [ ] Smoke test: real station markers visible on map with PM2.5 values in popups

### Phase 6 — AI Classification & Voice
> Goal: every ingested event gets AI-classified; voice in/out works
> (Was Phase 4 — moved after data layers: demo needs visible objects before AI narrative)

- [ ] `services/llm.py` — `LLMRouter`
  - [ ] Try Anthropic Claude (`claude-sonnet-4-6`)
  - [ ] Fallback: Ollama at `OLLAMA_BASE_URL` with Qwen 2.5 14B
  - [ ] Log which model was used; include `model` field on every event
- [ ] `services/ai.py` — `classify_event(text, context) -> ClassificationResult`
  - [ ] Fields: `category`, `severity`, `summary`, `recommended_actions: list[str]`, `affected_radius_km`
  - [ ] For simulation ticks: generate narrative summary of current threat state
  - [ ] For targeted intersection alerts: specific recommendation per object type (e.g. "Zamknij szkołę X", "Ewakuuj DPS Y")
- [ ] `services/tts.py` — `ElevenLabs`
  - [ ] `synthesize(text) -> bytes` — TTS alert audio
  - [ ] `transcribe(audio_bytes) -> str` — STT from radio/voice
- [ ] `routers/ingest.py` — `POST /api/ingest` → classify → save → return `IngestResponse`
- [ ] `routers/voice.py` — `POST /api/voice` → STT → ingest pipeline

### Phase 7 — useMaps Integration
> Goal: all layers auto-pushed to useMaps; fallback is own Leaflet frontend

- [ ] `services/usemaps.py` — `UseMapsClient`
  - [ ] `authenticate(login, password) -> token` via `POST /api/auth/login`
  - [ ] `push_features(layer_id, geojson) -> None` — upsert features on a layer
  - [ ] Coordinate transform: WGS84 → EPSG:2180 (using `pyproj`)
  - [ ] Token refresh on 401
- [ ] `services/sync.py` — `SyncService`
  - [ ] On event creation: push updated layer to useMaps
  - [ ] On simulation tick: push `threat_zones` + `events` layers
  - [ ] `routers/sync.py` — `POST /api/sync` (force full resync of all layers)
- [ ] Layer mapping: define which plugin layers map to which useMaps layer IDs
- [ ] Add `pyproj` to `requirements.txt`
- [ ] **Fallback**: if useMaps credentials/URL unavailable, own Leaflet frontend is the demo surface — no demo blocker

### Phase 8 — Polish & Demo
> Goal: jury-ready demo; voice assistant; clean pitch flow

- [ ] Demo seed script `scripts/seed_demo.py` — loads preset Puławy fire scenario + 10 synthetic events
- [ ] **5-minute demo script** (in `plan/DEMO_SCRIPT.md`):
  - [ ] T+0:00 — show map with real GIOŚ air quality layer (baseline)
  - [ ] T+0:30 — trigger `POST /api/simulation/start` (Puławy fire)
  - [ ] T+1:00 — watch plume spread on map, synthetic PM2.5 layer updates
  - [ ] T+1:30 — threat zone reaches School X / DPS Y → alert fires → AI recommendation shown
  - [ ] T+2:00 — voice command: "ile łóżek szpitalnych w promieniu 30km?" → TTS response
  - [ ] T+2:30 — resource calculator result visible on map + spoken aloud
  - [ ] T+3:00 — show layer toggles (disable simulation, show only real GIOŚ) → "any data source, any frontend"
- [ ] Voice assistant endpoint: `POST /api/voice/command` — STT → parse intent → return action + TTS audio
  - [ ] Intents: "pokaż zagrożenia", "ile łóżek w promieniu 30km", "odczytaj status"
- [ ] `GET /api/health` — uptime, active plugins, LLM backend in use, last sync timestamp
- [ ] Error handling audit: every endpoint returns meaningful HTTP errors
- [ ] Dockerfile + `docker-compose.yml` (app + Ollama)
- [ ] `README.md` — how to run, env vars, demo walkthrough

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
