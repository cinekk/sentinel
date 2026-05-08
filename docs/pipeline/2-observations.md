# Stage 2 — Observations

**Pipeline position:** Sources → **Observations** → Reactions → Outputs

## Purpose

Stage 2 persists sensor readings as a time-series log so that Stage 3 hooks can react to new data and Stage 4 outputs can query history. It is the bridge between the live-fetch plugin layer (Stage 1) and any downstream logic that needs more than the current reading. This stage does not yet exist in the codebase. Its absence is the primary structural gap in the system.

---

## Current state

Two disconnected data paths exist today.

**Path A — ephemeral.** Plugins call external APIs, return GeoJSON, and discard the data. Every `fetch()` is stateless. IMGW gauge readings are cached for 5 minutes in memory; after that they are gone. A gauge that transitions to `"alarm"` level produces a colored map dot and nothing else — no row is written, no hook fires, no history accumulates.

**Path B — EventRow.** `POST /api/events` writes pre-classified incidents to SQLite. `SimulationPlugin` also writes `EventRow` rows directly at each tick. These rows have `category / severity / status / description` — they represent classified incidents or simulation artifacts, not raw sensor readings.

Path A and Path B are completely disconnected. A gauge going to alarm never produces an EventRow. `flood_assessment.py` reads gauges from Path A's in-memory cache and computes hospital risk status — but that result is never written anywhere; it is recomputed from scratch on every HTTP request.

**Current EventRow schema** (`database.py` / `models.py`):

| Field | Type | Notes |
|---|---|---|
| `id` | int | Auto-increment PK |
| `time` | datetime | UTC, defaults to now |
| `latitude` | float | |
| `longitude` | float | |
| `category` | str | `fire \| flood \| medical \| hazmat \| security \| infrastructure \| other` |
| `severity` | str | `low \| medium \| high \| critical` |
| `status` | str | `active \| resolved \| investigating` |
| `description` | str | Free text |
| `source` | str | `human \| sensor \| radio \| api \| simulation` |
| `model` | str | Which process created the row (`"manual"`, `"112_sim"`) |

The table conflates three different kinds of data: classified crisis incidents entered by operators, simulation demo artifacts, and periodic sensor log entries written by `SimulationPlugin` every 10 seconds. These have incompatible semantics in a single table.

---

## Target design

> **TARGET DESIGN — not yet implemented.**
> Everything in this section is the goal state. None of it exists in the codebase today.

### a. Observations table

A single table for all sensor readings. New sensor types (sea level, soil moisture, precipitation) add rows with a new `metric` value — no schema migration needed.

```sql
CREATE TABLE observations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at  DATETIME NOT NULL,
    station_id   TEXT NOT NULL,
    station_name TEXT,
    source       TEXT NOT NULL,   -- "imgw_hydro" | "gios" | "manual" | "simulation"
    metric       TEXT NOT NULL,   -- "river_level_cm" | "alert_level" | "pm25" | "pm10" | ...
    value        REAL,            -- numeric value when applicable
    text_value   TEXT,            -- categorical value: "normal" | "warning" | "alarm"
    metadata     TEXT             -- JSON: river name, voivodeship, unit, sensor model, etc.
);

CREATE INDEX idx_obs_station_metric_time
    ON observations(station_id, metric, recorded_at DESC);

CREATE INDEX idx_obs_source_time
    ON observations(source, recorded_at DESC);
```

Using a `metric` discriminator column rather than separate per-type tables avoids one migration per sensor type and keeps all time-series queries uniform. Type-specific fields that do not belong in every row (river name, voivodeship, measurement unit) go into the `metadata` JSON column.

### b. DataWriter service

`services/data_writer.py` is the only place that writes to `observations`. After inserting the row it fires `hook_registry.fire_observation(obs)` to notify Stage 3 hooks. The write and the hook dispatch are decoupled — hook failures never propagate back to the caller.

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
) -> Observation: ...
```

Example — what `IMGWHydroPlugin.poll()` would call per station:

```python
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
    text_value=s["alert_level"],   # "normal" | "warning" | "alarm"
    metadata={"river": s["river"]},
)
```

### c. Query helpers

`services/observations.py` — consumed by Stage 3 hooks and Stage 4 outputs:

```python
async def last_n(
    station_id: str, metric: str, n: int
) -> list[Observation]: ...

async def station_history(
    station_id: str, metric: str, window_hours: int
) -> list[Observation]: ...

async def latest_per_station(
    source: str, metric: str
) -> list[Observation]: ...
```

`last_n` feeds the trend detector (3 consecutive rising readings → alarm). `station_history` feeds the chart endpoints. `latest_per_station` feeds the morning/evening reports and the operator panel status table.

### d. New HTTP endpoints

```
GET /api/hydro/stations
    All stations with current level and trend direction.

GET /api/hydro/stations/{station_id}/history?window=24h|7d|30d
    Time-series array for chart rendering. Default window: 24h.

GET /api/observations?source=imgw_hydro&metric=river_level_cm&since=2026-05-08T00:00:00Z
    Generic query endpoint. All params optional; returns newest-first.
```

### e. Retention

Background task (`prune_old_observations`) prunes rows with `recorded_at < now() - 90 days`. Scheduled daily at 03:00 via APScheduler. No manual intervention needed.

---

## EventRow going forward

> **TARGET DESIGN — not yet implemented.**

`EventRow` stays but its meaning narrows. It is for classified crisis incidents only — things that a human operator or a Stage 3 hook has determined are significant enough to appear in the Grafana dashboard, the voice briefing, and the affected-facilities list.

Raw sensor readings go to `observations`, not `EventRow`.

Simulation tick writes that currently go to `EventRow` (`source="simulation"`) will move to `observations` with `source="simulation"`. They are time-series data; the `EventRow` table is the wrong container for them. The simulation will continue to write classified events (e.g. "Phase 3 — evacuation requested") to `EventRow` as before — those are incidents, not readings.
