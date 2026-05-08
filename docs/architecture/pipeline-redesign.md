# Pipeline Redesign — Sentinel
**Date:** 2026-05-08  
**Context:** WCZK client requirements + de-facto analysis findings  
**Decision:** Restructure data flow; keep all existing components

---

## Guiding principles

1. Don't rewrite — restructure. The plugin fetch logic, flood assessment, briefing, TTS, FastAPI skeleton, and LLM client are all keepers.
2. Each phase ends with something observable running in production.
3. New stages are additive. Existing map endpoints and demo scenarios must keep working throughout.
4. No Redis, no Celery, no message queues — SQLite and asyncio are sufficient at WCZK scale.

---

## The four stages (revised naming)

```
┌─────────────────┐    poll()    ┌─────────────────┐    hooks     ┌─────────────────┐    triggers   ┌─────────────────┐
│   1. SOURCES    │ ──────────▶  │  2. OBSERVATIONS │ ──────────▶ │  3. REACTIONS   │ ──────────▶   │   4. OUTPUTS    │
│                 │              │                  │             │                 │               │                 │
│  BasePlugin     │   fetch()    │  observations    │             │  HookRegistry   │               │  LayerPlugin    │
│  (existing)     │ ──────────▶  │  table (new)     │             │  (new)          │               │  ReportPlugin   │
│                 │  (map only)  │                  │             │                 │               │  AlertPlugin    │
└─────────────────┘              └─────────────────┘             └─────────────────┘               └─────────────────┘
```

Each arrow is a distinct concern with its own triggering mechanism.

---

## Stage 1 — Sources

**What it is:** Data fetching from external APIs, files, and simulations. Returns structured data.

**What changes:**

Every source plugin gets an optional `poll()` method alongside the existing `fetch()`:

```python
class BasePlugin(ABC):
    # Existing — called by HTTP requests, returns GeoJSON for map display
    @abstractmethod
    async def fetch(self) -> dict: ...

    # New — called by APScheduler on a timer, writes to observations table
    async def poll(self) -> None:
        pass  # default: no-op; override in data-source plugins
```

`fetch()` keeps serving the map exactly as today. `poll()` is the new background ingest path. Plugins that are purely computed (HospitalStatusPlugin, TransportUnitsPlugin) don't need to implement `poll()`.

**Voivodeship config (immediate fix):**

```python
# config.py
imgw_voivodeship: str = "lubelskie"
gios_voivodeship: str = "lubelskie"
```

Both IMGW and GIOŚ plugins read from `settings.imgw_voivodeship` instead of hardcoded strings.

---

## Stage 2 — Observations

**What it is:** Unified time-series storage for all sensor readings, gauge levels, air quality measurements.

**Why a single table:**  
New sensor types (sea level, precipitation, soil moisture) should not require a new migration each time. A single `observations` table with a `metric` discriminator handles all numeric and categorical readings. Type-specific metadata (river name, voivodeship, sensor model) goes in a JSON column.

### Table design

```sql
CREATE TABLE observations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at  DATETIME NOT NULL,
    station_id   TEXT NOT NULL,
    station_name TEXT,
    source       TEXT NOT NULL,   -- "imgw_hydro", "gios", "manual", "simulation"
    metric       TEXT NOT NULL,   -- "river_level_cm", "alert_level", "pm25", "pm10", "sea_level_cm"
    value        REAL,            -- numeric value when applicable
    text_value   TEXT,            -- "normal"/"warning"/"alarm" — categorical values
    metadata     TEXT             -- JSON: river name, voivodeship, unit, etc.
);

CREATE INDEX idx_obs_station_metric_time
    ON observations(station_id, metric, recorded_at DESC);

CREATE INDEX idx_obs_source_time
    ON observations(source, recorded_at DESC);
```

**Retention:** background task prunes rows older than 90 days (runs daily).

### DataWriter service

`services/data_writer.py` — the only place that writes to `observations`:

```python
async def write_observation(
    station_id: str,
    station_name: str | None,
    source: str,
    metric: str,
    value: float | None = None,
    text_value: str | None = None,
    metadata: dict | None = None,
    recorded_at: datetime | None = None,
) -> Observation:
    # Writes row, then fires registered hooks
    obs = await _insert(...)
    await hook_registry.fire_observation(obs)
    return obs
```

**IMGWHydroPlugin.poll() example:**

```python
async def poll(self) -> None:
    stations = await _fetch_all_stations()
    for s in stations:
        await data_writer.write_observation(
            station_id=s["id"],
            station_name=s["name"],
            source="imgw_hydro",
            metric="river_level_cm",
            value=s["level_cm"],
            metadata={"river": s["river"], "voivodeship": settings.imgw_voivodeship},
        )
        await data_writer.write_observation(
            station_id=s["id"],
            station_name=s["name"],
            source="imgw_hydro",
            metric="alert_level",
            text_value=s["alert_level"],
            metadata={"river": s["river"]},
        )
```

### Query helpers

`services/observations.py`:

```python
async def last_n(station_id: str, metric: str, n: int) -> list[Observation]: ...
async def station_history(station_id: str, metric: str, window_hours: int) -> list[Observation]: ...
async def latest_per_station(source: str, metric: str) -> list[Observation]: ...
```

These feed the trend detector, the chart endpoint, and the scheduled reports.

### New HTTP endpoints

```
GET /api/hydro/stations                              — all stations + current level + trend
GET /api/hydro/stations/{station_id}/history         — time-series for chart (?window=24h|7d|30d)
GET /api/observations?source=imgw_hydro&metric=river_level_cm&since=2026-05-08T00:00:00Z
```

---

## Stage 3 — Reactions (Hook Registry)

**What it is:** Event-driven triggers that fire when new data is written to observations or when new events are created. Hooks run asynchronously and do not block the write path.

### Hook registry

`services/hooks.py` — ~40 lines:

```python
class BaseHook(ABC):
    async def on_observation(self, obs: Observation) -> None:
        pass

    async def on_event(self, event: Event) -> None:
        pass


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: list[BaseHook] = []

    def register(self, hook: BaseHook) -> None:
        self._hooks.append(hook)

    async def fire_observation(self, obs: Observation) -> None:
        for hook in self._hooks:
            asyncio.create_task(self._safe_call(hook.on_observation, obs))

    async def fire_event(self, event: Event) -> None:
        for hook in self._hooks:
            asyncio.create_task(self._safe_call(hook.on_event, event))

    async def _safe_call(self, fn, arg) -> None:
        try:
            await fn(arg)
        except Exception:
            logger.exception("Hook %s failed for %s", fn, arg)
```

Hooks registered in `main.py` lifespan alongside plugins.

### Planned hooks

**`TrendDetectorHook`** — `services/hooks/trend_detector.py`  
Fires on every `river_level_cm` observation. Reads last 3 observations for the station. If all 3 are strictly rising → creates an `EventRow` with category=`flood`, severity=`high`, description=`"UWAGA POZIOM WODY WZRASTA — stacja {name}, {river}"`. De-duplication: one alarm per station per 3-hour window.

**`AlertDispatchHook`** — `services/hooks/alert_dispatch.py`  
Fires on every new `EventRow` where `severity in ("high", "critical")`. Calls configured alert outputs (email, Telegram). Alert content is a one-line summary; for alarm-level events also triggers a draft communication via OpenRouter.

**`ForecastHook`** — `services/hooks/forecast.py` (Phase 5)  
Fires on schedule (not on observation). Reads last 24h of readings per station, runs linear regression, writes `+12h_level_cm` observations. Does not block the write path.

### Scheduler

`APScheduler` (async-compatible) added to the FastAPI lifespan. Single-process assumption holds for the voivodeship deployment.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")

# Poll sources on a fixed schedule
scheduler.add_job(imgw_plugin.poll, "interval", minutes=30, id="imgw_poll")
scheduler.add_job(gios_plugin.poll, "interval", minutes=30, id="gios_poll")

# Scheduled output triggers
scheduler.add_job(dispatch_morning_report, "cron", hour=6, minute=30, id="morning_report")
scheduler.add_job(dispatch_evening_report, "cron", hour=18, minute=30, id="evening_report")

# Maintenance
scheduler.add_job(prune_old_observations, "cron", hour=3, minute=0, id="prune_obs")
```

---

## Stage 4 — Outputs

**What it is:** Everything downstream that consumes processed data and delivers it to a human or system.

### Three output plugin types

```python
class LayerPlugin(BasePlugin):
    """Existing behavior — serves GeoJSON on HTTP request. No changes."""
    async def fetch(self) -> dict: ...

class ReportPlugin(ABC):
    """Renders a report as bytes (PDF) or text (email body / Markdown)."""
    report_id: str

    async def generate(self, context: ReportContext) -> ReportOutput: ...

class AlertPlugin(ABC):
    """Delivers a notification to a channel."""
    channel_id: str  # "email", "telegram", "webhook"

    async def send(self, subject: str, body: str, attachments: list[bytes] = []) -> None: ...
```

### Planned output plugins

**Report plugins:**
- `WCZKMorningReport` — IMGW warnings + last 12h events + high-risk districts. Renders to PDF (WeasyPrint + Jinja2 template).
- `WCZKEveningReport` — day summary + manual operator notes + trend extrapolation.
- Both are triggered by the scheduler AND by `POST /api/wczk/reports/generate` for on-demand.

**Alert plugins:**
- `EmailAlert` — `aiosmtplib`, sends HTML email with optional PDF attachment.
- `TelegramAlert` — direct HTTPS to Bot API, one-line threshold alerts.

**Operator panel:**
- Route `/wczk` — FastAPI-served HTML, no build step (same pattern as current frontend).
- Sections: status strip, active alerts with acknowledge button, station table, report preview, settings, manual notes.
- `POST /api/wczk/alerts/{event_id}/acknowledge` — marks event as `investigating`.

---

## What changes vs. what stays

### Keep exactly as-is
- `plugins/base.py` — `BasePlugin` interface (extended, not replaced)
- `plugins/imgw_hydro.py` — fetch logic and status mapping (add `poll()`, fix voivodeship)
- `plugins/gios.py` — fetch logic (add `poll()`, fix voivodeship)
- `plugins/simulation.py` — demo scenario (unaffected)
- `services/flood_assessment.py` — multi-signal fusion logic (unaffected)
- `services/spatial.py` — geometric helpers (unaffected)
- `services/openrouter.py` — LLM client (unaffected, gains new callers)
- `services/briefing.py` — deterministic briefing (unaffected, gains observations data)
- `services/tts.py` + `routers/voice.py` — voice output (unaffected)
- All existing map endpoints and GeoJSON routes (unaffected)

### Extend
- `plugins/imgw_hydro.py` — add `poll()`, read voivodeship from config
- `plugins/gios.py` — add `poll()`, read voivodeship from config
- `config.py` — add `IMGW_VOIVODESHIP`, `GIOS_VOIVODESHIP`, `ALERT_EMAIL_*`, `TELEGRAM_*`
- `main.py` lifespan — add scheduler start, hook registration
- `services/briefing.py` — optionally enrich with observations history for trend sentences

### Add
- `models.py` / `database.py` — `observations` table, `Observation` model
- `services/data_writer.py` — single write path for observations
- `services/observations.py` — query helpers (last_n, history, latest_per_station)
- `services/hooks.py` — `HookRegistry`, `BaseHook`
- `services/hooks/trend_detector.py`
- `services/hooks/alert_dispatch.py`
- `services/wczk_report.py` — report content logic (deterministic, like briefing.py)
- `services/alerts.py` — email + Telegram delivery
- `routers/hydro.py` — station history endpoints
- `routers/wczk.py` — operator panel API
- `frontend/wczk.html` — operator panel UI
- Jinja2 + WeasyPrint for PDF generation

### Change semantics
- `services/crisis_store.py` — persist to SQLite instead of in-memory dict. `CrisisEvent` table. Keep the same API surface so callers don't change.
- `EventRow` — remove the "sensor log" usage (SimulationPlugin tick writes). Those become `observations` rows with `source="simulation"`. EventRow stays for classified incidents only.

---

## Implementation order

### Phase 1 — Foundation (prerequisite for everything else)
1. Add `observations` table to `database.py` + `models.py`
2. `services/data_writer.py` — write + hook fire
3. `services/hooks.py` — registry + `BaseHook`
4. `services/observations.py` — query helpers
5. Voivodeship config vars in `config.py`
6. `plugins/imgw_hydro.py` — add `poll()`, fix voivodeship
7. APScheduler in `main.py` lifespan — IMGW poll every 30 min
8. `routers/hydro.py` — `/api/hydro/stations` + `/api/hydro/stations/{id}/history`
9. Map popup: click a gauge station → show 24h chart

**Observable deliverable:** Live W-M stations with real alert levels, clickable time-series charts.

### Phase 2 — Reactions
1. `services/hooks/trend_detector.py` — 3-rising-readings alarm
2. Persist `crisis_store` to SQLite
3. `EventRow` write fires `hook_registry.fire_event()`
4. `services/wczk_report.py` — morning/evening report content
5. `services/alerts.py` — email delivery
6. `services/hooks/alert_dispatch.py` — email on high/critical event
7. APScheduler — 06:30 morning report, 18:30 evening report

**Observable deliverable:** Duty officer receives email at 06:30 and 18:30. Immediate email when 3-rising-readings alarm fires.

### Phase 3 — Operator Panel
1. `routers/wczk.py` — acknowledge endpoint, recipients CRUD, manual notes
2. `frontend/wczk.html` — operator panel UI (no build step)
3. PDF report generation (WeasyPrint + Jinja2)
4. Telegram alert plugin
5. `GIOSPlugin.poll()` + scheduler

**Observable deliverable:** A URL the director can bookmark. No code knowledge needed.

### Phase 4 — Media Monitoring + RCB (see wczk-analysis/implementation-plan.md)

### Phase 5 — ML Prediction +12h (requires 14 days of Phase 1 data)

---

## Risk notes

**SQLite WAL under concurrent writes:** APScheduler writes observations every 30 min; HTTP requests read. SQLite WAL mode handles this fine. No locking issues expected at this poll frequency.

**APScheduler in single-process:** Correct assumption for voivodeship deployment. If the client ever wants multi-process, replace with a persistent job queue — but don't over-engineer now.

**Hook failures must not block writes:** `_safe_call` wraps every hook in try/except + `create_task`. A hook crashing (e.g., email SMTP timeout) must never propagate back to `DataWriter.write_observation()`.

**WeasyPrint system dependencies:** Requires Cairo + Pango on the Docker image. Add to Dockerfile before Phase 3, not during.
