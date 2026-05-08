# Event Ingestion

## Current State

There is **no AI-powered event ingestion**. The original hackathon plan included
a `POST /api/ingest` endpoint that would accept raw text, classify it via LLM,
and persist the result. This was not implemented — `routers/ingest.py` and
`services/ai.py` do not exist.

`IngestRequest` and `IngestResponse` in `models.py` are dead code from that
original design. They are not imported or used anywhere.

Events enter the system through two active paths:

---

## Path 1 — Manual: `POST /api/events`

**Router:** `routers/events.py`

The caller supplies a fully pre-classified event. No LLM involved.

**Request (`EventCreate`):**
```json
{
  "latitude": 51.4158,
  "longitude": 21.9698,
  "category": "flood",
  "severity": "critical",
  "status": "active",
  "description": "Osoba uwięziona w budynku · woda do 1p.",
  "source": "human",
  "model": "manual",
  "time": "2026-04-19T14:32:00Z"   // optional — defaults to now
}
```

**Response (`EventOut`):** Same fields plus `id: int`.

**Other endpoints on the same router:**
- `GET /api/events` — returns all events ordered by time desc
- `DELETE /api/events` — deletes all events (used to reset between demo runs)

---

## Path 2 — Simulation: `CallGenerator`

**Service:** `services/call_generator.py`

Writes `EventRow` records directly to the DB at 30-second intervals.
Simulates a flood crisis unfolding over 6 phases (~24 ticks = ~12 minutes
of wall time, representing ~6 hours of narrative time).

All simulation events are tagged `source="simulation"`, `model="112_sim"`.
They are bulk-deleted on `reset()` via `DELETE FROM events WHERE source = 'simulation'`.

**Phases:**

| Phase | Ticks | Character |
|---|---|---|
| 0 | 0–3 | Normal scattered medical calls |
| 1 | 4–7 | First riverside calls, minor flooding |
| 2 | 8–11 | Cluster near Puławy/Wisła, roads blocked |
| 3 | 12–15 | Evacuation requests, dialysis/oxygen patients |
| 4 | 16–19 | Hospital flood zone vicinity, ZRM response slowing |
| 5 | 20+ | Sectors cut off, no ZRM response available |

Each tick generates 2–4 events. Locations are randomly drawn from a pool of
12 flood-prone sites in Lublin voivodeship, with ±1.5 km jitter. ZRM unit
names are randomly assigned from a pool of 7 units.

**Control:** `CallGenerator` is started/paused/reset via `routers/emergency_calls.py`
(not `routers/events.py`). The generator instance is a module-level singleton
at `services.call_generator.generator`.

---

## EventRow Schema

Defined in `database.py` (SQLAlchemy) and mirrored in Pydantic models in `models.py`.

| Field | Type | Notes |
|---|---|---|
| `id` | int | Auto-increment primary key |
| `time` | datetime | UTC. Defaults to `now()` if not supplied |
| `latitude` | float | |
| `longitude` | float | |
| `category` | str | See enum below |
| `severity` | str | See enum below |
| `status` | str | See enum below |
| `description` | str | Free text |
| `source` | str | See enum below |
| `model` | str | Which process created the event |

**Enums:**

```python
EventCategory = "fire" | "flood" | "medical" | "hazmat" | "security" | "infrastructure" | "other"
EventSeverity = "low" | "medium" | "high" | "critical"
EventStatus   = "active" | "resolved" | "investigating"
EventSource   = "human" | "sensor" | "radio" | "api" | "simulation"
```

The `model` field was originally intended to record which LLM classified the
event. Since no LLM classification exists, it is set to `"manual"` for
operator-created events and `"112_sim"` for simulation events.

---

## Dead Code

These exist in `models.py` but are imported and used nowhere:

- `IngestRequest` — original hackathon ingest payload schema
- `IngestResponse` — original hackathon classification result schema

These can be removed when the event ingestion feature is eventually built or
confirmed as permanently out of scope.
