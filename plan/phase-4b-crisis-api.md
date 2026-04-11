# Phase 4b — Grafana Crisis API (Lubelskie GIS Contract)

> Contract source: `docs/api-contract-lubelskie-gis.md`
> This phase adds a unified crisis event store + Grafana-facing read endpoints
> to satisfy the buddy's Grafana dashboard requirements.

---

## Context

A teammate's demo script manages fires via a `/api/v1/fires` CRUD contract (see contract doc).
Instead of a fire-specific store, we build a **generic crisis event store** at `/api/v1/crisis`.
This way our simulation engine and the operator's script both feed the same unified source.

The buddy's `/api/v1/fires` endpoints are exposed as thin compatibility aliases that delegate
to the crisis store with `type="fire"`. His script works unchanged.

---

## Architecture

```
Operator script                Our simulation
POST /api/v1/fires  ──►        SimulationPlugin
    (type=fire)                    │
         │                         ▼
         └─────────► CrisisStore (in-memory)
                         │
                         ▼
           /api/v1/crisis/*   (unified read endpoints)
           /api/v1/stats
           /api/v1/fires       (compat alias)
```

---

## Data Model: CrisisEvent

```python
class CrisisEvent:
    id: str              # 8-char hex, e.g. "3606afc2"
    type: str            # "fire", "chemical_spill", "flood", etc.
    lat: float
    lon: float
    name: str            # default: "Pożar" for fire
    evac_radius_km: float    # default: 5.0
    warn_radius_km: float    # default: 12.0
    status: str          # "active" | "extinguished"
    source: str          # "operator" | "simulation"
    created_at: float    # unix timestamp
```

Stored in-memory (dict[str, CrisisEvent]) — no DB needed for hackathon.

---

## Spatial Logic

**Replace km/111 approximation** with haversine in `services/spatial.py`:
```
a = sin²(Δlat/2) + cos(lat1)·cos(lat2)·sin²(Δlon/2)
d = 2R·arcsin(√a)    R = 6371 km
```
Accurate to < 0.5% vs ~5% error at 51°N with degree approximation.

**CRUD crisis events** → circular zones, haversine distance check.
**Simulation events** → keep ellipse (wind-blown plume is genuinely elliptical).
Simulation can also write a CrisisEvent with approximate circular radii for the stats/affected endpoints.

---

## Affected facility logic

Internal type → display name:
- `hospital` → `"Szpital"`
- `school` → `"Szkoła"`
- `social` → `"DPS/Placówka"`

Action matrix:

| Internal type | In evac zone | In warn zone |
|---|---|---|
| `hospital` | `EWAKUACJA` | `GOTOWOŚĆ` |
| `social` | `EWAKUACJA` | `GOTOWOŚĆ` |
| `school` | `ZAMKNIĘCIE` | `OSTRZEŻENIE` |

Deduplication: when a facility is in range of multiple fires, show it once (nearest fire).
Sort output by `distance_km` ascending.

---

## Files to create/modify

### New: `services/crisis_store.py`
In-memory dict of CrisisEvent. Methods: `add`, `get`, `list`, `patch`, `delete`, `list_active`.

### New: `routers/crisis.py`
```
POST   /api/v1/crisis                  create event (type, lat, lon, name, radii)
GET    /api/v1/crisis                  list all (?type=fire&status=active)
GET    /api/v1/crisis/{id}             single event
PATCH  /api/v1/crisis/{id}             update (radii, name, status)
DELETE /api/v1/crisis/{id}             delete

GET /api/v1/stats                      3-element array for Grafana stat panels
GET /api/v1/crisis/affected            affected facilities sorted by distance_km
GET /api/v1/crisis/affected-geojson    same as GeoJSON FeatureCollection
GET /api/v1/crisis/zones-geojson       zone polygons (evac + warn) per active event
GET /api/v1/crisis/fires-geojson       all active events as GeoJSON points
```

### New: `routers/fires_compat.py`
Thin alias: `POST/GET/PATCH/DELETE /api/v1/fires` → delegates to crisis store with `type="fire"`.
Ensures buddy's demo script works without changes.

### Modify: `services/spatial.py`
- Add `haversine(lat1, lon1, lat2, lon2) -> float`
- Add `circle_polygon(lat, lon, radius_km, n=64) -> list[list[float]]` for zone GeoJSON
- Add `facilities_in_zones(crisis_events, facilities) -> list[AffectedFacility]`
- Keep existing ellipse functions (used by simulation)

### Modify: `plugins/resources.py`
- Add `display_type` to GeoJSON properties: `"Szpital"`, `"Szkoła"`, `"DPS/Placówka"`
- Keep internal `type` slug for logic routing

### New: `routers/v1_layers.py`
```
GET /api/v1/layers/hospitals          → delegates to HospitalsPlugin
GET /api/v1/layers/schools            → delegates to SchoolsPlugin
GET /api/v1/layers/social-facilities  → delegates to SocialPlugin
GET /api/v1/layers/air-quality        → mock GIOŚ stations (5-6 hardcoded, realistic values)
GET /api/v1/layers/weather            → mock IMGW stations (3-4 hardcoded)
```
Note: `/api/v1/layers/air-quality` is a mock here. Phase 5 replaces it with real GIOŚ data.

### Modify: `main.py`
Register: `crisis_router`, `fires_compat_router`, `v1_layers_router`.

---

## Checklist

- [ ] `services/crisis_store.py` + Pydantic models in `models.py`
- [ ] `haversine()` + `circle_polygon()` in `services/spatial.py`
- [ ] `routers/crisis.py` — CRUD + stats + affected + geojson endpoints
- [ ] `routers/fires_compat.py` — `/api/v1/fires` alias
- [ ] `routers/v1_layers.py` — layer aliases + air quality + weather mocks
- [ ] `plugins/resources.py` — add `display_type` to properties
- [ ] `main.py` — register new routers
- [ ] Tests: crisis CRUD, haversine accuracy, affected facility logic, stats output shape
- [ ] Smoke test: `POST /api/v1/crisis` with Puławy coords → `GET /api/v1/crisis/affected` returns hospitals/schools

---

## Grafana endpoint summary

| Panel | Endpoint | Critical |
|---|---|---|
| Mapa sytuacyjna | `GET /api/v1/crisis/affected-geojson` | coordinates [lon,lat], name, type, action |
| Aktywne pożary | `GET /api/v1/fires` | id, name, status, evac/warn radius |
| Stat: pożary | `GET /api/v1/stats[2]` | value |
| Stat: ewakuacja | `GET /api/v1/stats[0]` | value |
| Stat: ostrzeżenie | `GET /api/v1/stats[1]` | value |
| Tabela działań | `GET /api/v1/crisis/affected` | action, type, name, distance_km |
| Jakość powietrza | `GET /api/v1/layers/air-quality` | name, pm25, pm10, status |
| Pogoda | `GET /api/v1/layers/weather` | name, temp_c, wind_dir, wind_speed_kmh, humidity_pct |
