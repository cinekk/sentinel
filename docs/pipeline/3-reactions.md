# Stage 3 — Reactions

**Pipeline position:** Sources → Observations → **Reactions** → Outputs

> **TARGET DESIGN — nothing in this stage exists yet.**
> Every interface, hook, and scheduler job described here is the intended design.
> None of it is implemented in the codebase today.

---

## Purpose

Stage 3 is the event-driven layer between data persistence and downstream action. When Stage 2 (`DataWriter`) writes a new observation, or when a new `EventRow` is created, registered hooks are notified and can act on that fact — generate an alarm, dispatch an alert, or schedule a forecast computation.

The critical constraint: **hooks must never block the write path.** `DataWriter.write_observation()` must return in the same time it takes to insert a row. Hooks run asynchronously via `asyncio.create_task`; they may take seconds or minutes without affecting ingestion throughput.

**Why this matters now:** today, an IMGW gauge transitioning to `"alarm"` level produces a colored map dot and nothing else. No event is created, no duty officer is notified, no trend is checked. The `flood_assessment.py` logic is recomputed from scratch on every HTTP request and then discarded. Stage 3 closes this gap — a gauge going to alarm triggers the same analysis chain as an operator manually entering an incident.

---

## HookRegistry

`services/hooks.py` — approximately 40 lines, no dependencies beyond the `Observation` and `EventRow` models.

```python
import asyncio
import logging
from abc import ABC

from models import EventRow, Observation

logger = logging.getLogger(__name__)


class BaseHook(ABC):
    """Override either or both methods. Un-overridden methods are silent no-ops."""

    async def on_observation(self, obs: Observation) -> None:
        pass

    async def on_event(self, event: EventRow) -> None:
        pass


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: list[BaseHook] = []

    def register(self, hook: BaseHook) -> None:
        self._hooks.append(hook)

    async def fire_observation(self, obs: Observation) -> None:
        for hook in self._hooks:
            asyncio.create_task(self._safe_call(hook.on_observation, obs))

    async def fire_event(self, event: EventRow) -> None:
        for hook in self._hooks:
            asyncio.create_task(self._safe_call(hook.on_event, event))

    async def _safe_call(self, fn, arg) -> None:
        try:
            await fn(arg)
        except Exception:
            logger.exception("Hook %s failed for %s", fn, arg)


hook_registry = HookRegistry()
```

`_safe_call` is the isolation boundary. A hook that raises (SMTP timeout, DB lock, LLM error) is logged and silently dropped. The `DataWriter` caller never sees the exception.

`asyncio.create_task` means hooks are fire-and-forget. They outlive the call stack that triggered them. This has one consequence: hooks must open their own DB sessions — they cannot reuse the session from the `write_observation()` call that spawned them (see Design constraints below).

Hooks are registered in `main.py` lifespan alongside plugins, using `hook_registry.register()`.

---

## Planned hooks

### a. TrendDetectorHook

**File:** `services/hooks/trend_detector.py`  
**Fires on:** every `Observation` where `metric == "river_level_cm"`

This is the primary alarm generator for WCZK. The duty officer requirement is explicit: when a gauge is consistently rising, an alarm must be raised before the level crosses the statutory warning threshold — not after. Three consecutive rising readings at 30-minute intervals gives approximately 60 minutes of advance notice.

**Logic:**

```python
class TrendDetectorHook(BaseHook):
    async def on_observation(self, obs: Observation) -> None:
        if obs.metric != "river_level_cm":
            return

        # Read the three most recent readings for this station (including this one).
        # last_n returns newest-first; reverse to get chronological order.
        readings = await observations.last_n(obs.station_id, "river_level_cm", n=3)
        if len(readings) < 3:
            return  # not enough history yet

        levels = [r.value for r in reversed(readings)]  # oldest → newest
        if not (levels[0] < levels[1] < levels[2]):
            return  # not strictly rising

        # De-duplicate: one alarm per station per 3-hour window.
        recent = await observations.station_history(
            obs.station_id, "trend_alarm_fired", window_hours=3
        )
        if recent:
            return

        # Create the alarm event.
        meta = obs.metadata or {}
        river = meta.get("river", "nieznana rzeka")
        station_name = obs.station_name or obs.station_id

        event = EventRow(
            category="flood",
            severity="high",
            status="active",
            latitude=meta.get("lat", 0.0),
            longitude=meta.get("lon", 0.0),
            description=f"UWAGA POZIOM WODY WZRASTA — stacja {station_name}, {river}",
            source="sensor",
            model="trend_detector",
        )
        await crisis_store.add_event(event)

        # Sentinel observation used only for de-duplication.
        await data_writer.write_observation(
            station_id=obs.station_id,
            source="internal",
            metric="trend_alarm_fired",
            value=levels[2],
        )
```

The sentinel `trend_alarm_fired` observation is a lightweight de-duplication flag. It expires naturally with the 90-day retention policy. An alternative is a separate `alarm_state` table, but the observation approach reuses existing infrastructure with no new migration.

### b. AlertDispatchHook

**File:** `services/hooks/alert_dispatch.py`  
**Fires on:** every new `EventRow` where `severity in ("high", "critical")`

```python
class AlertDispatchHook(BaseHook):
    async def on_event(self, event: EventRow) -> None:
        if event.severity not in ("high", "critical"):
            return

        summary = f"[{event.severity.upper()}] {event.category} — {event.description}"

        # Deliver to all configured alert output plugins (Stage 4).
        for alert_plugin in alert_registry.plugins:
            await alert_plugin.send(subject=summary, body=_format_body(event))

        # For alarm-level events, generate a draft operator communication via LLM.
        if event.severity == "critical":
            draft = await _draft_communication(event)
            await crisis_store.attach_draft(event.id, draft)
```

`_draft_communication` calls `services/openrouter.py`'s `chat_completion()` with a short structured prompt asking for a one-paragraph public communication draft. It passes only the event fields — not raw payload text or user input — to avoid SSML/prompt injection. The draft is stored against the event and surfaced in the operator panel for review before any send.

`alert_registry` is the Stage 4 alert plugin registry (email, Telegram). This hook is the bridge between Stage 3 (detected alarm) and Stage 4 (delivery channel). It does not know which channel is configured — it delegates entirely to Stage 4 plugins.

### c. ForecastHook — Phase 5 only

**File:** `services/hooks/forecast.py`

ForecastHook does **not** fire on every observation. At 80 stations × 48 readings per day, attaching forecasting logic to each `on_observation` call would be both expensive and pointless — a regression over 24 hours of data does not change meaningfully between consecutive readings.

Instead, ForecastHook runs on a schedule (APScheduler, every 30 minutes). It reads the last 24 hours of `river_level_cm` readings per station, fits a simple linear regression, and writes a `+12h_level_cm` prediction back to Stage 2 as a new observation with `source="forecast"`.

```python
# Scheduled — not triggered by on_observation
async def run_forecast_cycle() -> None:
    stations = await observations.latest_per_station("imgw_hydro", "river_level_cm")
    for station in stations:
        history = await observations.station_history(
            station.station_id, "river_level_cm", window_hours=24
        )
        if len(history) < 6:
            continue  # insufficient data
        predicted = _linear_extrapolation(history, horizon_minutes=720)
        await data_writer.write_observation(
            station_id=station.station_id,
            station_name=station.station_name,
            source="forecast",
            metric="+12h_level_cm",
            value=predicted,
        )
```

**Prerequisite:** ForecastHook requires at least 14 days of Phase 1 data to produce meaningful output. Activating it before that produces extrapolations from insufficient history and is likely to generate false alarms. It is deliberately deferred to Phase 5.

---

## APScheduler

The scheduler is an `AsyncIOScheduler` instance, created in `main.py` before the lifespan starts and started inside the lifespan alongside the plugin registry.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Europe/Warsaw")

# Stage 1 → Stage 2: poll sources on a fixed interval
scheduler.add_job(imgw_plugin.poll,  "interval", minutes=30, id="imgw_poll")
scheduler.add_job(gios_plugin.poll,  "interval", minutes=30, id="gios_poll")

# Stage 4: scheduled output triggers
scheduler.add_job(dispatch_morning_report, "cron", hour=6,  minute=30, id="morning_report")
scheduler.add_job(dispatch_evening_report, "cron", hour=18, minute=30, id="evening_report")

# Maintenance
scheduler.add_job(prune_old_observations, "cron", hour=3,  minute=0,  id="prune_obs")
```

All five jobs:

| Job ID | Trigger | What it does |
|---|---|---|
| `imgw_poll` | every 30 min | `IMGWHydroPlugin.poll()` → writes river level + alert level observations |
| `gios_poll` | every 30 min | `GIOSPlugin.poll()` → writes PM2.5, PM10, AQI observations |
| `morning_report` | 06:30 Warsaw | Generates and dispatches the WCZK morning situational report |
| `evening_report` | 18:30 Warsaw | Generates and dispatches the WCZK evening situational report |
| `prune_obs` | 03:00 daily | Deletes `observations` rows older than 90 days |

**Single-process assumption:** the voivodeship deployment runs a single Uvicorn process behind Caddy. `AsyncIOScheduler` is correct for this topology. No Redis, no Celery, no distributed lock needed. If a future deployment adds workers or load-balancing, this scheduler must be replaced with a persistent job queue — but do not over-engineer for a constraint that does not exist yet.

---

## Hook registration in main.py

Hooks are registered in the same lifespan block as plugins, after the plugin registry is populated:

```python
# main.py — inside lifespan()
from services.hooks import hook_registry
from services.hooks.trend_detector import TrendDetectorHook
from services.hooks.alert_dispatch import AlertDispatchHook

# ... plugin registry.register() calls ...

hook_registry.register(TrendDetectorHook())
hook_registry.register(AlertDispatchHook())

scheduler.start()
yield
scheduler.shutdown()
```

Order matters: `TrendDetectorHook` must be registered before `AlertDispatchHook` if you want a trend-detected alarm to immediately trigger alert dispatch in the same event cycle. Because hooks are `create_task`-fired (non-blocking), the sequencing is not guaranteed — but registering `TrendDetector` first makes the typical path correct.

---

## Design constraints

- **Idempotency.** A hook that fires twice for the same observation (e.g. because the process restarted mid-write) must not create duplicate alarms. `TrendDetectorHook` achieves this with the `trend_alarm_fired` sentinel observation. `AlertDispatchHook` should check for an existing `EventRow` with the same `model + description + time window` before creating a new one.

- **Hook failures must not propagate.** `_safe_call` catches all exceptions and logs them. A hook crashing (SMTP timeout, LLM rate limit, DB lock) must be observable in logs but must never surface to the caller of `write_observation()` or `fire_event()`.

- **DB session per hook invocation.** `asyncio.create_task` means a hook runs after the call stack that created it has returned — the DB session from `write_observation()` is likely already closed or in a different transaction. Hooks must open their own `async with get_db() as db:` sessions. Sharing a session across the write path and the hook is a use-after-close bug.

- **No blocking calls inside hooks.** Hooks run on the same event loop as the FastAPI server. A synchronous blocking call (e.g. a synchronous HTTP client, `time.sleep`) inside a hook will stall the entire server. Use `httpx.AsyncClient`, `aiosmtplib`, and `await asyncio.sleep` throughout.
