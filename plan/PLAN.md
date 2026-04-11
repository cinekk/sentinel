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
The frontend is just another consumer — it can be swapped for any GIS tool.
Demo scenario: **Zestaw D — industrial fire / smog crisis** in Lublin voivodeship.

---

## Architecture overview

```
[Plugins]                      [Core]                  [Output]
  SimulationPlugin  ──►
  GIOSPlugin        ──►   PluginRegistry          GET /api/events        → Grafana
  ManualIngestPlugin ──►  EventStore (SQLite)      GET /api/layers/{id}/geojson → map
  MockResourcePlugin ──►  ResourceStore            POST → useMaps API     (push sync)
  RadioPlugin (STT)  ──►  LayerCache               GET /api/simulation/*  → demo control

[AI]      LLMRouter: Claude → Ollama fallback
[Spatial] spatial.py: threat zone ∩ sensitive objects → targeted alerts
[STT]     ElevenLabs → voice ingest
[TTS]     ElevenLabs → broadcast alerts
[Frontend] frontend/index.html — Leaflet map, layer toggles, served via FastAPI /static
```

Coordinate system: internal WGS84 (EPSG:4326), transformed to EPSG:2180 on useMaps push.

---

## Phases

### Phase 1 — Core Foundation
> Goal: running FastAPI server, DB, plugin base, one working endpoint

- [x] `requirements.txt` + `.env.example`
- [x] `database.py` — SQLAlchemy async, SQLite, `EventRow`, `init_db()`
- [x] `models.py` — Pydantic schemas: `EventOut`, `EventCreate`, `IngestRequest`, `IngestResponse`, `ResourceOut`, `LayerMeta`, `SimulationConfig`, `ThreatZone`
- [x] `plugins/base.py` — `BasePlugin` ABC: `layer_id`, `layer_name`, `data_type`, `async fetch() -> GeoJSON FeatureCollection`
- [x] `plugins/__init__.py` + `PluginRegistry`
- [x] `routers/events.py` — `GET /api/events` (flat JSON, Grafana-ready)
- [x] `main.py` — FastAPI app, CORS, lifespan startup (`init_db`, register plugins), mount `/static`
- [x] Smoke test: server starts, `GET /api/events` returns `[]`

### Phase 2 — Thin Frontend
> Goal: map visible in browser showing Lublin voivodeship; proves API is consumable by any client

- [ ] `frontend/index.html` — single file, Leaflet from CDN, no build step
  - [ ] Lublin voivodeship + powiaty boundary rendered as base layer
  - [ ] Layer panel: lists all layers from `GET /api/layers`, toggle each on/off
  - [ ] Each layer fetched from `GET /api/layers/{id}/geojson` and rendered as GeoJSON overlay
  - [ ] Auto-refresh every 30s with last-updated timestamp visible
  - [ ] Powiat/gmina filter — click on area to filter events to that region
  - [ ] Popup on feature click: shows event/resource details
- [ ] `main.py` — serve `frontend/` as `StaticFiles` at `/`
- [ ] Smoke test: open browser, see map with voivodeship outline, toggle a layer

### Phase 3 — Simulation Engine
> Goal: triggerable fire scenario that generates live events and a spreading threat zone

- [ ] `plugins/simulation.py` — `SimulationPlugin`
  - [ ] Scenario config: source lat/lon, wind speed, wind direction, fire intensity, tick interval
  - [ ] Background async task: ticks every N seconds
  - [ ] Each tick: advance plume, emit synthetic PM2.5/PM10 readings, generate `EventRow`
  - [ ] Threat zone: directional ellipse polygon (source + wind vector + time elapsed)
  - [ ] On each tick: call `spatial.check_intersections(threat_zone, resources)` → emit targeted alerts
- [ ] `routers/simulation.py`
  - [ ] `POST /api/simulation/start` — accepts `SimulationConfig`, starts background task
  - [ ] `POST /api/simulation/stop`
  - [ ] `GET /api/simulation/state` — current tick, threat zone GeoJSON, active events count
- [ ] Preset scenario: industrial fire at Puławy (chemical plant area), wind NE at 15 km/h
- [ ] Simulation state persisted in-memory (reset on restart is fine for hackathon)

### Phase 4 — AI Classification & Voice
> Goal: every ingested event gets AI-classified; voice in/out works

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

### Phase 5 — Data Layers & Spatial Intelligence
> Goal: all map layers populated; real air quality data; threat zone triggers targeted alerts

- [ ] `plugins/gios.py` — `GIOSPlugin` (real data, earns bonus +10 for public source integration)
  - [ ] Fetch PM2.5/PM10 from GIOŚ REST API (v1, no auth required):
    - stations: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll`
    - sensors per station: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors/{stationId}`
    - readings: `GET https://api.gios.gov.pl/pjp-api/v1/rest/data/getData/{sensorId}`
    - AQ index: `GET https://api.gios.gov.pl/pjp-api/v1/rest/aqindex/getIndex/{stationId}`
  - [ ] Filter to stations in Lublin voivodeship (or nearest to Puławy for demo)
  - [ ] Returns GeoJSON FeatureCollection with sensor readings as properties
  - [ ] SimulationPlugin synthetic readings displayed as separate layer alongside real data
- [ ] `plugins/resources.py` — `MockResourcePlugin`
  - [ ] Hospitals in Lublin voivodeship (15–20 entries): name, beds, SOR, generator status, coords
  - [ ] Schools + care homes (DPS): name, capacity, coords
  - [ ] Fire stations (PSP/OSP): name, unit type, coords
- [ ] `services/spatial.py` — `check_intersections(threat_zone: Polygon, resources: list[Resource]) -> list[Alert]`
  - [ ] Uses Shapely for polygon intersection
  - [ ] Returns one alert per affected object: object name, type, recommended action
  - [ ] Action mapping: school → "Zamknij i ewakuuj", DPS → "Ewakuacja priorytetowa", hospital → "Przygotuj przyjęcie rannych / ewakuacja jeśli w strefie"
- [ ] `routers/layers.py`
  - [ ] `GET /api/layers` — list all registered layers with metadata + last updated timestamp
  - [ ] `GET /api/layers/{layer_id}/geojson` — GeoJSON FeatureCollection for that layer
- [ ] `routers/resources.py`
  - [ ] `GET /api/resources` — flat list (Grafana)
  - [ ] `GET /api/resources/calculator?lat=&lon=&radius_km=&type=` — count resources in radius (bonus +10)
- [ ] Static GeoJSON: Lublin voivodeship boundary + powiaty + gminy (GUGiK BDOT public data, 213 gminas)
- [ ] `routers/events.py` — add `POST /api/events` (manual event creation)
- [ ] Add `shapely` to `requirements.txt`

### Phase 6 — useMaps Integration
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

### Phase 7 — Polish & Demo
> Goal: jury-ready demo; voice assistant; clean pitch flow

- [ ] Demo seed script `scripts/seed_demo.py` — loads preset Puławy fire scenario + 10 synthetic events
- [ ] **5-minute demo script** (in `plan/DEMO_SCRIPT.md`):
  - [ ] T+0:00 — show map with real GIOŚ air quality layer (baseline)
  - [ ] T+0:30 — trigger `POST /api/simulation/start` (Puławy fire)
  - [ ] T+1:00 — watch plume spread on map, synthetic PM2.5 layer updates
  - [ ] T+1:30 — threat zone reaches School X → alert fires → AI recommendation shown
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

## Side quests coverage

| Quest | How SENTINEL covers it | Points |
|---|---|---|
| **Marshal (10k PLN)** | Owned Leaflet map + layers + simulation + resources + threat zones + voice | Main prize |
| **ElevenLabs** | STT voice ingest + TTS alert broadcast + voice command assistant | Side quest |
| **Comtegra** (offline LLM) | `LLMRouter` Ollama fallback — system fully operational without internet | Side quest |

### Marshal bonus features coverage

| Bonus | Implementation | Points |
|---|---|---|
| Public data scraping | `GIOSPlugin` — real PM2.5/PM10 from `powietrze.gios.gov.pl` | +10 |
| Resource calculator | `GET /api/resources/calculator` + map UI widget | +10 |
| Voice assistant | `POST /api/voice/command` + ElevenLabs TTS | +10 |
| Social media agents | Not planned — skip | — |

**Projected score: ~84/100 base + 30 bonus = ~114/140**

---

## Key API surface (final)

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

## Open questions / decisions deferred

- [ ] useMaps layer IDs — need to be created in useMaps UI first; get IDs from teammate
- [ ] useMaps instance URL — confirm with teammate (env var `USEMAPS_BASE_URL`)
- [ ] Grafana exact datasource plugin — teammate to confirm; we expose both flat JSON and GeoJSON
- [ ] Gminy GeoJSON source — GUGiK BDOT10k download or GUGIK WFS API
- [ ] Ollama model availability on demo machine — confirm `qwen2.5:14b` is pulled
- [ ] GIOŚ station IDs near Puławy — use `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll`, filter by city/coords

---

## Files index

```
sentinel/
  main.py                    FastAPI app, CORS, startup, static mount
  models.py                  Pydantic schemas
  database.py                SQLite setup, get_db
  plugins/
    base.py                  BasePlugin ABC
    __init__.py              PluginRegistry
    simulation.py            SimulationPlugin (synthetic fire scenario)
    gios.py                  GIOSPlugin (real PM2.5/PM10 from GIOŚ API)
    resources.py             MockResourcePlugin (hospitals, schools, DPS, PSP)
  routers/
    events.py                GET/POST /api/events
    layers.py                GET /api/layers, GET /api/layers/{id}/geojson
    resources.py             GET /api/resources, GET /api/resources/calculator
    simulation.py            POST /api/simulation/start|stop, GET /api/simulation/state
    ingest.py                POST /api/ingest
    voice.py                 POST /api/voice, POST /api/voice/command
    sync.py                  POST /api/sync
  services/
    ai.py                    classify_event() → ClassificationResult
    llm.py                   LLMRouter (Claude → Ollama)
    tts.py                   ElevenLabs TTS + STT
    spatial.py               check_intersections(threat_zone, resources) → list[Alert]
    usemaps.py               UseMapsClient (auth, push, coord transform)
    sync.py                  SyncService
  frontend/
    index.html               Leaflet map, layer toggles, region filter, auto-refresh
  scripts/
    seed_demo.py             Load Puławy fire scenario + synthetic events
  plan/
    PLAN.md                  ← this file
    DEMO_SCRIPT.md           5-minute jury demo walkthrough
```
