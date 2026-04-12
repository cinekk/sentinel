# Phase 9 — Medical Crisis in Flood Conditions (Zestaw A)

> **Scenario:** Hospital network triage during active flooding — identify operational hospitals,
> flag those needing evacuation, surface available capacity for resource reallocation.

**Status:** 🔲 Not started

---

## Problem

ISOK flood zones tell us *risk*, not *current state*. To say "this hospital is in danger NOW"
we need live river levels from IMGW. Cross-referencing gauge readings with ISOK P=10%/P=1% zones
gives a real-time inundation proxy.

Generator state and personnel data is not available from open APIs today. We mock it now,
but the integration point is kept clean for future access to internal marszałek datasets.

---

## Architecture

```
[Data sources]                    [Services]              [Output]
  IMGWHydroPlugin  ──►
  (live gauges)        ──►  FloodAssessmentService  ──►  GET /api/flood/assessment
                                                    ──►  GET /api/layers/hospitals-status/geojson
  ISOK WMS (existing) ──►  (zone × gauge → risk)   ──►  GET /api/layers/gauges/geojson
  HospitalsPlugin ──►
  (beds, SOR, mock
   generator/staff)

  112 events (existing) ──►  demand pressure per hospital
```

---

## Tasks

### 1. IMGW Hydrology Plugin — `plugins/imgw_hydro.py`

- [ ] `IMGWHydroPlugin(BasePlugin)`
  - layer id: `"gauges"`, name: `"Poziomy rzek (IMGW)"`
  - Fetch all hydrological stations: `GET https://hydro.imgw.pl/api/station/`
    - Filter to Lublin voivodeship rivers (Wisła, Wieprz, Bug, Bystrzyca)
    - Bbox: lat 50.4–51.8, lon 21.5–24.1
  - Per station fetch: `GET https://hydro.imgw.pl/api/station/{id}/`
    - Extract: current water level (`stan`), warning threshold (`ostrzezenie`), alarm threshold (`alarm`)
  - Compute `alert_level`: `"normal"` / `"warning"` / `"alarm"` / `"unknown"`
  - Returns GeoJSON FeatureCollection — properties: `station_name`, `river`, `level_cm`,
    `warning_cm`, `alarm_cm`, `alert_level`, `updated_at`
  - Cache with 5-min TTL (live data, but don't hammer the API)
- [ ] Register in `main.py` plugin registry

> **Note:** Verify exact IMGW API URL and response shape before coding — the endpoint above
> is based on the public hydro.imgw.pl portal. Alternative: `https://hydro2.imgw.pl/api/`.

---

### 2. Hospital Status Extension — `data.json` + `plugins/resources.py`

Extend hospital records with two mock fields:

```json
{
  "name": "Szpital ...",
  "lat": ..., "lon": ...,
  "beds": 120, "sor": true,
  "generator_state": "ok",        // "ok" | "degraded" | "offline"
  "personnel_pct": 85             // 0–100, % of normal staffing
}
```

- [ ] Add `generator_state` and `personnel_pct` to all hospitals in `data.json`
  - Default: `generator_state="ok"`, `personnel_pct=85`
  - 2–3 hospitals near flood-prone areas get degraded values for demo realism
- [ ] `HospitalsPlugin` exposes these fields in GeoJSON properties

**Future hook:** If `HOSPITAL_STATUS_API_URL` env var is set, override mock data with response
from that URL (marszałek internal dataset). Structure: same field names. No auth assumed initially.

---

### 3. Flood Assessment Service — `services/flood_assessment.py`

Core logic. Returns a status per hospital.

```python
class HospitalFloodStatus(BaseModel):
    hospital_id: str
    name: str
    lat: float
    lon: float
    status: Literal["operational", "at_risk", "evacuate"]
    risk_factors: list[str]          # human-readable reasons
    beds: int
    sor: bool
    generator_state: str
    personnel_pct: int
    nearest_gauge: str | None        # station name
    nearest_gauge_level: str | None  # "normal" / "warning" / "alarm"
    demand_112: int                  # medical 112 calls within 15 km, last 2h
    can_receive: bool                # operational + demand < threshold + beds > 20
```

**Status logic:**
```
EVACUATE  = hospital in ISOK P=10% zone AND nearest gauge at "alarm"
            OR generator_state == "offline"
            OR road_cut (hospital in ISOK P=1% zone)

AT_RISK   = hospital in ISOK P=10% zone AND nearest gauge at "warning"
            OR generator_state == "degraded"
            OR demand_112 > HIGH_DEMAND_THRESHOLD (configurable, default 10)

OPERATIONAL = everything else
```

**Inputs:**
- Hospital list from `HospitalsPlugin`
- Gauge readings from `IMGWHydroPlugin`
- ISOK flood zone polygons (see task 4)
- 112 events from `EventStore` (filter category=`"medical"`, last 2h, within 15 km)

- [ ] Implement `assess_hospitals() -> list[HospitalFloodStatus]`
- [ ] Cache with 2-min TTL (gauges update every 10–15 min, but 112 events are live)

---

### 4. ISOK Flood Zone Data — `data/isok_flood_zones.geojson`

We already have WMS proxy for ISOK rendering. For *intersection logic*, we need the actual
zone polygons locally (can't do point-in-polygon against a WMS).

- [ ] Download/embed simplified ISOK P=10% and P=1% flood zone polygons for Lublin voivodeship
  - Source: KZGW ISOK WFS or pre-clipped GeoJSON from previous WMS research
  - If WFS is unavailable: use bounding polygons of Vistula/Wieprz floodplains as proxy
  - Acceptable polygon resolution: 100–500m detail (demo quality)
- [ ] `services/flood_zones.py` — loads the GeoJSON once at startup, exposes
  `point_in_flood_zone(lat, lon) -> Literal["p1", "p10", None]`
- [ ] Used by `FloodAssessmentService`

---

### 5. Hospital Status GeoJSON Layer — `plugins/resources.py`

New layer: `"hospitals-status"` (separate from existing `"hospitals"` layer).

- [ ] `HospitalStatusPlugin(BasePlugin)` — or add as second layer to existing `HospitalsPlugin`
  - Calls `FloodAssessmentService.assess_hospitals()`
  - Returns GeoJSON with status-colored markers
  - Properties include all `HospitalFloodStatus` fields for popup display
  - `marker_color`: `"green"` / `"orange"` / `"red"` based on status

---

### 6. Flood Assessment API — `routers/flood.py`

```
GET  /api/flood/assessment          Full hospital status list (JSON)
GET  /api/flood/summary             AI-generated situation report
POST /api/hospitals/{id}/override   Manual status override (generator down, road cut, etc.)
```

- [ ] `GET /api/flood/assessment` — returns `list[HospitalFloodStatus]`
- [ ] `GET /api/flood/summary` — calls LLM with assessment data → returns:
  ```json
  {
    "evacuate": ["Szpital A — flood risk + alarm gauge"],
    "at_risk": ["Szpital B — high 112 demand"],
    "redirect_to": ["Szpital C (Zamość, 450 beds, low demand)"],
    "narrative": "Sytuacja powodziowa wymaga ewakuacji 1 placówki..."
  }
  ```
- [ ] `POST /api/hospitals/{id}/override` — accepts `generator_state`, `personnel_pct`, `road_cut`
  - Stores in-memory override dict (reset on server restart; demo-appropriate)
  - FloodAssessmentService checks overrides before mock data

---

### 7. Frontend — Flood Dashboard Mode

- [ ] New sidebar tab: **"Infrastruktura Medyczna"** (alongside existing tabs; if 5 tabs overflow, consider scrollable tab bar or compact icon+label layout)
- [ ] **Hospital status panel** (table in sidebar):
  - Columns: Szpital | Status | Łóżka | SOR | Rzeka | 112 (2h)
  - Color-coded status badges
  - "Ewakuuj" / "Przyjmuje" action labels
- [ ] **Gauge panel** — list of top 5 gauges by alert level, with level bar
- [ ] Map additions:
  - ISOK flood zone overlay (WMS — already implemented, just toggle on for this mode)
  - `hospitals-status` layer (replaces plain hospitals layer in this mode)
  - `gauges` layer (IMGW stations, colored dots)
  - 112 medical call heatmap (filter existing 112 layer to medical category)
- [ ] **AI summary box** — fetches `/api/flood/summary`, displays narrative + bullet lists
  - Refresh button; auto-refresh every 5 min
- [ ] Manual override UI (operator panel, collapsible):
  - Per-hospital: generator toggle, road cut toggle
  - Updates via `POST /api/hospitals/{id}/override`

---

### 8. Demo Seed — `scripts/seed_flood_demo.py`

- [ ] Inject synthetic medical 112 events near at-risk hospitals (high density = overwhelmed)
- [ ] Set 1–2 hospitals to degraded/offline generator via override API
- [ ] Set 1–2 IMGW gauges to alarm level (or use mock override if live data is calm)
  - Override endpoint: `POST /api/gauges/{id}/override` — mock level for demo
- [ ] Verify AI summary produces meaningful output

---

## Data gaps & assumptions

| Gap | Assumption |
|---|---|
| Generator state | Mocked in `data.json`; real data via `HOSPITAL_STATUS_API_URL` env var |
| Personnel % | Mocked; same hook as generator |
| Road accessibility | Simplified: hospital in ISOK P=1% zone → road cut flag |
| Current flood extent | IMGW gauge alarm + ISOK zone overlap as proxy |
| ISOK vector polygons | Download from WFS or embed pre-clipped GeoJSON |

---

## Smoke test

1. Server starts with IMGW plugin → `GET /api/layers/gauges/geojson` returns station points
2. `GET /api/flood/assessment` → returns list, all `"operational"` (calm weather)
3. Manually set gauge override to `"alarm"` for Wisła/Puławy station
4. Assessment recomputes → hospitals in ISOK P=10% near that gauge → `"at_risk"` or `"evacuate"`
5. `GET /api/flood/summary` → LLM returns sensible recommendation
6. Frontend Zestaw A tab shows colored hospitals + gauge levels
7. Operator sets `road_cut=true` on one hospital → status flips to `"evacuate"`
8. AI summary updates to reflect evacuation recommendation

---

## Out of scope

- Real-time road flooding data (no open API available)
- Actual ISOK WFS polygon download (use pre-clipped static file)
- Personnel/generator real-time feeds (future marszałek API integration)
- Multi-day flood prediction (requires hydrological modeling)
