# Phase 4c — Unified Crisis/Simulation Architecture

## Problem

Two parallel systems are doing the same thing:

| | Simulation | Crisis API |
|---|---|---|
| Intersection fn | `check_intersections` | `facilities_in_zones` |
| Zone shape | Ellipse (wind-driven) | Circle (fixed radii) |
| Alert source | `plugin.state["alerts"]` | `crisis_store` |
| Frontend polls | `/api/simulation/state` | `/api/v1/crisis/affected` (unused by frontend) |

Testing via `/simulation/state` means we're testing code that never runs in production. The frontend shows
alerts from a path that doesn't exist for real events.

## Goal

**Simulation is a data source, not a parallel control plane.**

When the simulation starts, it writes a `CrisisEvent` into `crisis_store`. Each tick updates that event's
ellipse geometry. The frontend polls `/api/v1/crisis/affected` for all alerts — simulation and real events
go through the same path.

`check_intersections` (ellipse, simulation-only) is deleted.
`facilities_in_zones` (spatial.py) is extended to handle both circle and ellipse zones.

---

## Changes

### 1. `models.py` — Add ellipse fields to CrisisEvent

```python
class CrisisEvent(BaseModel):
    id: str
    type: str
    lat: float
    lon: float
    name: str
    evac_radius_km: float = 5.0
    warn_radius_km: float = 12.0
    zone_shape: Literal["circle", "ellipse"] = "circle"
    semi_major_km: float | None = None   # ellipse only — downwind extent
    semi_minor_km: float | None = None   # ellipse only — crosswind extent
    bearing_deg: float | None = None     # ellipse only — wind direction (0=N)
    status: str = "active"
    source: str = "operator"
    created_at: float
```

`CrisisEventCreate` and `CrisisEventPatch` get the same four new optional fields.

`evac_radius_km` / `warn_radius_km` are kept for circle events and as the "tight / buffer" threshold for
ellipse alert levels:
- inside ellipse → level `"inside"` (maps to EWAKUACJA / ZAMKNIĘCIE)
- inside 1.5× ellipse → level `"approaching"` (maps to GOTOWOŚĆ / OSTRZEŻENIE)

### 2. `services/spatial.py` — Ellipse support in `facilities_in_zones`

Replace the haversine-only check with a shape-aware check:

```python
def _facility_alert_level(facility_coords, event) -> str | None:
    """Return 'inside', 'approaching', or None."""
    if event.zone_shape == "ellipse" and event.semi_major_km:
        # reuse _point_in_ellipse with 1× and 1.5× scale
        ...
    else:
        # existing haversine + evac_radius / warn_radius logic
        d = haversine(...)
        if d <= event.evac_radius_km: return "inside"
        if d <= event.warn_radius_km: return "approaching"
        return None
```

`facilities_in_zones` calls this helper instead of inline haversine.

Also: add `level` and `resource_name` fields to the returned dicts (aliases for `zone`→level mapping and
`name`) so the frontend HUD works without changes to `app.js`.

```python
results.append({
    ...existing fields...,
    "level": "inside" if zone == "evac" else "approaching",   # HUD compat
    "resource_name": props.get("name", ""),                   # HUD compat
})
```

Delete `check_intersections` — no longer needed.

### 3. `plugins/simulation.py` — Write to crisis_store

```python
import services.crisis_store as store
from models import CrisisEventCreate, CrisisEventPatch

def start(self, config):
    ...
    event = store.add(CrisisEventCreate(
        type="fire",
        lat=config.source_lat,
        lon=config.source_lon,
        name="Pożar Zakładów Azotowych Puławy",
        zone_shape="ellipse",
        semi_major_km=0.1,
        semi_minor_km=0.05,
        bearing_deg=config.wind_direction_deg,
        source="simulation",
    ))
    self._crisis_id = event.id

def _tick(self):
    # grow ellipse each tick
    semi_major = self.tick * SPREAD_RATE_KM_PER_TICK * config.fire_intensity
    semi_minor = semi_major * 0.45   # crosswind ~45% of downwind
    store.patch(self._crisis_id, CrisisEventPatch(
        semi_major_km=semi_major,
        semi_minor_km=semi_minor,
        bearing_deg=config.wind_direction_deg,
    ))
    # no more self._alerts or self._threat_zone

def stop(self):
    if self._crisis_id:
        store.patch(self._crisis_id, CrisisEventPatch(status="resolved"))
    ...

def reset(self):
    if self._crisis_id:
        store.delete(self._crisis_id)
        self._crisis_id = None
    ...
```

`state` property keeps: `running`, `tick`, `config`, `crisis_id`.  
Drops: `alerts`, `threat_zone` (those now come from the crisis API).

### 4. `frontend/app.js` — Switch alert source

Remove from simulation poll:
```js
renderAlertHud(state.alerts || []);
```

Add a separate poller (same 5s interval, independent of simulation running):
```js
async function pollAlerts() {
  const res = await fetch(`${API}/api/v1/crisis/affected`);
  const alerts = await res.json();
  renderAlertHud(alerts);
}
setInterval(pollAlerts, 5000);
pollAlerts();
```

The HUD already reads `a.level` and `a.resource_name` — those fields are now provided by
`facilities_in_zones` (step 2 above). No other frontend changes needed.

### 5. `routers/simulation.py` — Drop alerts from state endpoint

`GET /api/simulation/state` returns: `running`, `tick`, `config`, `crisis_id`.  
Remove the `alerts` and `threat_zone` fields from the response.

---

## What stays the same

- `/api/v1/crisis/affected` — same endpoint, same shape, now used by frontend
- `/api/v1/crisis/zones-geojson` — still renders the ellipse as a visual layer (currently renders circles
  from `circle_polygon`; stretch: render actual ellipse polygon here too)
- Simulation start/stop/reset control endpoints — unchanged
- HUD and alert modal in frontend — unchanged

---

## Out of scope (later)

- Real wind data from IMGW API — simulation currently uses fixed config wind direction; swap the source
  when real data available, the ellipse model stays the same
- `zones-geojson` rendering actual ellipse polygon (currently circles) — acceptable for demo

---

## Smoke test

1. Start server, open frontend — HUD is empty (no active crises)
2. `POST /api/simulation/start` → check `GET /api/v1/crisis` returns one ellipse event with `source="simulation"`
3. Wait 3 ticks → `GET /api/v1/crisis/affected` returns facilities in zone
4. HUD on frontend shows alerts
5. `POST /api/simulation/stop` → crisis event status = `"resolved"`, HUD clears
6. `POST /api/v1/crisis` (manual fire event, circle) → `GET /api/v1/crisis/affected` returns facilities — same path, same HUD
