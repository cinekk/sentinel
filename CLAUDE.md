# SENTINEL — AI Situational Awareness Platform

## Civil42 Hackathon, 11-12.04.2026

## Project

Dual-use platform for collecting and analyzing crisis events in real time.
Multi-source ingestion → AI classification → API → Grafana dashboard + Usemaps map.

## Quick Orient

- Entry point: `main.py` — app factory, plugin registry, DB seed, lifespan
- LLM calls: `services/openrouter.py` (OpenAI-compatible, structured output via json_schema)
- Crisis events: `routers/crisis.py` → `services/crisis_store.py`
- Voice briefing: `routers/voice.py` → `services/briefing.py` (deterministic) → `services/tts.py`
- Layer data: `routers/layers.py` + `routers/v1_layers.py` (consumed by Usemaps)
- External data: IMGW Hydro (water levels), GIOŚ (air quality) — fetched live by plugins
- Config: all env vars in `config.py` via pydantic-settings

## Stack

- Python 3.12 + FastAPI + Uvicorn
- OpenRouter API (`services/openrouter.py`) — OpenAI-compatible, structured output via json_schema
- SQLite + aiosqlite (dev and prod — no Postgres migration yet)
- ElevenLabs TTS
- Caddy reverse proxy (read_timeout 120s)

## Project Structure

```
main.py          # app factory, plugin registry, DB seed, lifespan
config.py        # all env vars via pydantic-settings
models.py        # SQLAlchemy + Pydantic schemas
database.py      # async SQLite engine, get_db

routers/         # one file per feature area (crisis, flood, layers, assistant, voice, ...)
services/        # business logic (openrouter, briefing, tts, flood_assessment, evacuation, ...)
plugins/         # data source plugins — each extends BasePlugin (see Plugin Architecture below)
frontend/        # single-file Leaflet SPA, no build step, served as static files by FastAPI
```

To see current structure: `find . -name "*.py" -not -path "./.venv/*" | sort`

## Plugin Architecture

Every data source is a plugin — a class extending `BasePlugin` (`plugins/base.py`).
Each plugin implements:
- `layer_id: str` — unique identifier
- `layer_name: str` — display name
- `fetch() -> GeoJSON FeatureCollection` — returns current data

Plugins register in `main.py` lifespan via `registry.register()`.
Data is served via `GET /api/layers/{layer_id}/geojson`.

To add a new data source: create a new file in `plugins/`, extend `BasePlugin`,
add one `registry.register()` line in `main.py`. Nothing else.

## API Contract

### GET /api/events

Returns flat JSON list of events for Grafana and Usemaps.
Fields: time, latitude, longitude, category, severity, status, description.

### POST /api/ingest

Accepts raw input (free text, sensor data, audio transcript).
Passes to AI classification, saves to DB.
Body: `{ "source": "human|sensor|radio|api", "payload": "...", "lat": 0.0, "lon": 0.0 }`

### GET /api/resources

Static resources (ambulances, fire trucks) with location. Mock for now.

### GET /api/health

Returns `{ "status": "ok", "plugins": [...] }` — use for health checks.

## AI/LLM Pipeline — Do Not Break

**Prompt (`services/assistant.py`)**
`SYSTEM_PROMPT` must not be changed without explicit instruction — changes cascade to
all downstream behavior (layer IDs, field names, frontend rendering).

**Three-way sync**
These three must always stay in sync — if one changes, update all three:
1. `_build_view_config_schema()` — enum of valid layer IDs
2. `services/layer_meta.py` — layer definitions
3. `_LAYER_KEYWORDS` in `services/assistant.py` — fallback keyword matching

**Output validation**
`_validate_and_normalize()` is the trust boundary — strips unknown layer IDs before
they reach the frontend. Do not remove or weaken it.

**Briefing → TTS**
Only pass output of `generate_briefing_text()` to TTS. Never raw user input,
crisis payload text, or LLM output. SSML injection risk.

## Demo Scenarios

**Zestaw D** (primary): Industrial fire + smog at Puławy chemical plant (Lublin voivodeship).
`SimulationPlugin` generates a spreading ellipse + PM2.5 plume. `spatial.py` intersects
threat zone with resource layers → targeted alerts. GIOŚ plugin fetches real PM2.5/PM10
alongside simulation data.

**Zestaw A** (secondary): Flood scenario — river water level rise, evacuation dispatch.

## Deployment

- Live: https://sentinel.xd.ventures
- Docker Compose: `app` service on port 8000, behind Caddy
- Auto-deploys on push to `main` via GitHub Actions (SSH deploy)
- Prod DB: `/app/data/sentinel.db` (not `./sentinel.db` — path differs from dev)
- Health check: `GET /api/health`

## Current State

Core platform is deployed and functional at https://sentinel.xd.ventures.
All original hackathon features are complete and shipped:
- Flood scenario simulation (`routers/flood_scenario.py`, `services/flood_assessment.py`)
- Voice briefing pipeline (`services/briefing.py`, `services/tts.py`)
- Plugin-based layer system (`plugins/`)

Active development:
- Svelte frontend rewrite — incremental migration, new UI served at `/svelte` in parallel with legacy map

For current phase plan and upcoming work: see `plan/svelte-dashboard.md`

## Coding Rules

- Type hints everywhere
- Async/await for all endpoints
- Short functions, single responsibility
- Don't over-engineer — working first, clean second
- Every endpoint returns a meaningful HTTP error if something fails

## Do Not

- Do not create `services/ai.py` or `services/llm.py` — LLM client is `services/openrouter.py`
- Do not add a build step to the frontend (no npm/webpack/bundler) — for now
- Do not use old GIOŚ API paths (`/pjp-api/rest/`) — retired 30.06.2025, use `/v1/rest/` only
- Do not call LLM in `services/briefing.py` — it is intentionally deterministic
- Do not pass raw user input or crisis payload text to TTS
- Do not amend existing commits — always create new ones
- Do not add `Co-Authored-By` trailers to commit messages
- Do not use `routers/ingest.py` as a pattern — it is legacy hackathon code

## Environment Variables

```
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=...
ELEVENLABS_API_KEY=...
DATABASE_URL=sqlite+aiosqlite:///./sentinel.db
USEMAPS_BASE_URL=...
USEMAPS_LOGIN=...
USEMAPS_PASSWORD=...
```
