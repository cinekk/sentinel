# Phase 11 — Hospital Layer UX + Transfer Recommendations

## Problem statement

Two separate issues degrade the hospital workflow during flood scenarios:

1. **Layer collision** — `hospitals` (base) and `hospitals-status` (flood assessment) render
   markers at identical coordinates. Leaflet stacks them; whichever is on top eats the click.
   The other layer's popup becomes unreachable.

2. **Missing transfer guidance** — when a hospital status is `evacuate`, the operator has no
   in-app signal for where patients should go. The decision is made ad-hoc.

---

## Part A — Tab-aware layer switching + enriched status layer

### Concept

Each sidebar tab "owns" a canonical set of layers. When a tab becomes active, its layers
appear; conflicting layers from other tabs hide. The user never has to manually toggle.

For hospitals specifically:

| Tab active | `hospitals` | `hospitals-status` |
|---|---|---|
| Any tab except flood | ✅ visible | hidden |
| Flood tab | hidden | ✅ visible (enriched) |

The status layer supersedes the base layer when flood context is active — it carries all
base hospital fields *plus* flood-specific fields, so nothing is lost.

### Backend changes

**`plugins/resources.py` — `HospitalStatusPlugin.fetch()`**

Merge base hospital fields into every `hospital_status` feature's `properties`:

```python
# fields to copy from HospitalsPlugin's hospital row
BASE_FIELDS = [
    "name", "short_name", "hospital_type", "operator", "nfz_contract",
    "street", "city", "postal_code", "has_sor", "has_izba_przyjec",
    "sor_throughput_per_day", "beds_total_physical", "icu_oiom_beds",
    "operating_rooms", "ct_24_7", "helipad", "backup_power",
    "backup_power_fuel_hours", "phone_24h_sor", "specializations",
]
```

Pull them from `HospitalsPlugin` (already in DB via `HospitalRow`) using the same
`hospital_id` key that `assess_hospitals()` returns.

### Frontend changes

**`frontend/app.js`**

1. Add a `TAB_LAYER_RULES` constant mapping tab name → `{show: [], hide: []}`:

```js
const TAB_LAYER_RULES = {
  flood:  {
    show: ['hospitals-status', 'gauges', 'flood_zones', 'events'],
    hide: ['hospitals'],
    // note: show-only — these layers are NOT hidden when leaving the flood tab
  },
  events: { show: ['hospitals'], hide: ['hospitals-status'] },
  // other tabs: no change (undefined = leave as-is)
};
```

`flood` tab `show` layers and their rationale:
- `hospitals-status` — flood-coloured hospital markers (replaces base `hospitals`)
- `gauges` — river water levels (Poziomy rzek / IMGW)
- `flood_zones` — ISOK hazard zone polygons (Strefy zagrożenia powodziowego)
- `events` — crisis events feed; relevant context during active flood scenario

`flood_zones`, `gauges`, and `events` are **show-only**: they are enabled on flood tab entry
but not hidden when leaving the tab (operator may want to keep them visible).

2. Replace the ad-hoc `click` listener on the flood stab (app.js:1714) with a generic
   `applyTabLayerRules(tab)` helper called from the shared `.stab` click handler at the
   top of the file.

3. On page load, call `applyTabLayerRules` for the initially-active tab (Events) so
   `hospitals-status` starts hidden.

---

## Part B — Hospital transfer / handoff recommendations

### Concept

When a hospital's status is `evacuate`, the system recommends 2-3 receiver hospitals
sorted by: (a) `can_receive == true`, (b) proximity, (c) available beds.

Two surfaces:

**Map** — dashed polyline from evacuating hospital to each recommended receiver.
A small label on the line: `→ X km · Y łóżek`.

**Flood tab table** — new column "Przekierowanie" (Transfer). For `evacuate` rows, a
comma-separated list of short names of recommended receivers. For other statuses, empty.

### Backend changes

**New endpoint: `GET /api/flood/transfer-recommendations`**

```python
class TransferTarget(BaseModel):
    hospital_id: str
    name: str
    short_name: str
    lat: float
    lon: float
    distance_km: float
    available_beds: int

class TransferRecommendation(BaseModel):
    from_hospital_id: str
    from_name: str
    from_lat: float
    from_lon: float
    status: str          # "evacuate" | "at_risk"
    targets: list[TransferTarget]  # top-3, sorted by distance
```

Logic (`services/flood_assessment.py` or new `services/transfer.py`):
- Only return entries for hospitals where `status in ("evacuate", "at_risk")`
- Candidates = hospitals where `can_receive == True` and `status == "operational"`
- Sort candidates by Haversine distance from source hospital
- Return top 3

**`plugins/resources.py` — `HospitalStatusPlugin`**

Add `transfer_targets: list[str]` (short names) to each `evacuate` feature's properties
so the map layer itself carries the data needed for the popup (avoids a second API call).

### Frontend changes

**Map — dashed transfer lines**

- After loading `hospitals-status` GeoJSON, if the flood tab is active, call the
  `/api/flood/transfer-recommendations` endpoint.
- For each recommendation, draw `L.polyline([[from_lat, from_lon], [to_lat, to_lon]], { dashArray: '6 4', color: '#f59e0b', weight: 1.5 })` into a dedicated `transferLinesLayer`.
- `transferLinesLayer` is shown/hidden together with `hospitals-status` (same tab rules).
- Tooltip on the line: `"→ Szpital X · 12 km · 42 łóżka"`.

**Flood tab table**

- Add column header "Przekierowanie" after the existing columns.
- For `evacuate` rows, populate from `transfer_targets` property (already in GeoJSON).
- Style: small `<span>` pills, same amber color as `at_risk` status badge.

---

## Implementation order

1. `HospitalStatusPlugin` — enrich properties with base hospital fields
2. `services/transfer.py` — `get_transfer_recommendations()` logic
3. `routers/flood.py` — wire `GET /api/flood/transfer-recommendations`
4. `frontend/app.js` — `TAB_LAYER_RULES` + `applyTabLayerRules()`
5. `frontend/app.js` — transfer polylines on map
6. `frontend/app.js` — "Przekierowanie" column in flood table

## Files touched

```
plugins/resources.py            HospitalStatusPlugin.fetch() — enrich + add transfer_targets
services/transfer.py            NEW — get_transfer_recommendations()
routers/flood.py                add GET /api/flood/transfer-recommendations
frontend/app.js                 TAB_LAYER_RULES, applyTabLayerRules(), transfer lines, table column
```

## Observable output (done criteria)

- Switching to the flood tab hides base hospital markers; status-coloured markers appear.
- Switching away from flood tab reverses this.
- Status layer popups show full hospital detail (address, beds, SOR, backup power).
- `evacuate` hospitals have dashed amber lines pointing to their top-3 receivers.
- Flood table "Przekierowanie" column shows receiver names for evacuating hospitals.
