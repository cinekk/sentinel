# Phase 12 — Evacuation Command Window (Transport Sanitarny)

## Problem statement

When hospitals reach `evacuate` status during a flood scenario, the operator sees a
transfer recommendation on the map (dashed lines) but has no operational dispatch view:

- How many patients need to be moved, and of what acuity?
- What transport units are available, what type are they, and can they reach in time?
- Is the total transport capacity sufficient for the load?

The current UI forces the operator to mentally reconcile map lines with a static table.
A dedicated **Ewakuacja** panel provides an actionable dispatch picture in one place.

---

## Polish EMS transport unit types

| Code | Full name | Use case |
|------|-----------|----------|
| **T** | Podstawowy transport sanitarny | Non-urgent, ambulatory patients; low-acuity transfers |
| **N** | Specjalistyczny transport sanitarny | Neonates, fragile/ventilated patients requiring special equipment |
| **P** | Podstawowy Zespół Ratownictwa Medycznego | BLS team (2 paramedics); stable but monitored patients |
| **S** | Specjalistyczny Zespół Ratownictwa Medycznego | ALS team (doctor + paramedic); critical / ICU patients |

Matching logic (evac need → required unit type):
- ICU / OIOM patients → **S**
- Neonates → **N**
- Stable ward patients → **P**
- Ambulatory / social care overflow → **T**

---

## Backend changes

### `services/evacuation.py` — NEW

```python
class TransportUnit(BaseModel):
    unit_id: str
    call_sign: str        # e.g. "LU-P-04"
    unit_type: str        # T | N | P | S
    lat: float
    lon: float
    status: str           # available | en_route | unavailable
    distance_km: float    # from evacuation source hospital
    eta_minutes: int      # road-time estimate (1.2× straight-line at 70 km/h)

class PatientGroup(BaseModel):
    category: str         # icu | neonates | ward | ambulatory
    count: int
    required_unit_type: str   # S | N | P | T
    units_needed: int     # ceil(count / CAPACITY[unit_type])

class HospitalEvacOrder(BaseModel):
    hospital_id: str
    name: str
    lat: float
    lon: float
    priority: str             # NATYCHMIASTOWE | PILNE | PLANOWE
    patient_groups: list[PatientGroup]
    assigned_units: list[TransportUnit]   # units matched to this hospital
    units_needed: int         # total units needed
    units_available: int      # total assigned
    deficit: int              # units_needed - units_available (0 = OK)
    transfer_target: str | None   # short name of receiving hospital
```

**Patient count derivation** (from existing hospital data):
```python
PATIENT_RATIOS = {
    "icu":        0.05,   # 5% of physical beds are OIOM/ICU → unit S
    "neonates":   0.03,   # 3% neonatal → unit N (only if has neonatal ward)
    "ward":       0.60,   # 60% standard ward → unit P
    "ambulatory": 0.32,   # 32% can walk / low-acuity → unit T
}
UNIT_CAPACITY = {"S": 1, "N": 1, "P": 2, "T": 4}
```

`evacuate_count = beds_total_physical * occupancy_rate` where `occupancy_rate` is
drawn from the hospital's current `personnel_pct` field (proxy for load level).

**Transport unit generation** (mock, spatially realistic):
- Seed units from fire station + hospital coordinates in the voivodeship (already in data.json)
- Assign type mix per station: ~40% T, 30% P, 20% S, 10% N
- Each station contributes 1–3 units depending on population weight
- Total pool: ~80–120 units across voivodeship
- Distance/ETA: Haversine × 1.35 (road factor) ÷ 70 km/h

**`services/evacuation.py` public API:**
```python
def get_evacuation_dispatch(assessed_hospitals: list[dict]) -> list[HospitalEvacOrder]:
    """Build full dispatch picture for all hospitals in evacuate/at_risk status."""
```

### `routers/flood.py` — new endpoint

```
GET /api/flood/evacuation-dispatch
```

Returns `list[HospitalEvacOrder]` — only hospitals with `status in ("evacuate", "at_risk")`.
Calls `assess_hospitals()` then passes result to `get_evacuation_dispatch()`.

---

## Frontend changes

### New "Ewakuacja" sub-tab in Powódź dashboard

Add a tab row inside `.flood-content`:

```
[Ocena]  [Wskaźniki]  [Ewakuacja ●]
```

The `●` badge (red dot) appears when any hospital is in `evacuate` status.

### Evacuation panel layout

```
┌─────────────────────────────────────────────────────┐
│  EWAKUACJA MEDYCZNA          [2 szpitale · 847 pac.] │
├─────────────────────────────────────────────────────┤
│  ┌── Szpital Jana Bożego ─────────────────────────┐ │
│  │  🔴 NATYCHMIASTOWE  →  SP ZOZ Puławy (23 km)   │ │
│  │  ─────────────────────────────────────────────  │ │
│  │  ICU / OIOM    12 pac.   wymaga  12×S           │ │
│  │  Oddział       180 pac.  wymaga  90×P            │ │
│  │  Ambulatoryjni  55 pac.  wymaga  14×T            │ │
│  │  ─────────────────────────────────────────────  │ │
│  │  Dostępne jednostki:                            │ │
│  │  ┌──────────────────────────────────────────┐  │ │
│  │  │ S  LU-S-02  ●wolna  4.2 km  ~4 min       │  │ │
│  │  │ S  LU-S-07  ●wolna  7.1 km  ~6 min       │  │ │
│  │  │ P  LU-P-11  ●wolna  2.8 km  ~3 min       │  │ │
│  │  │ T  LU-T-03  ●en route  …                  │  │ │
│  │  └──────────────────────────────────────────┘  │ │
│  │  ⚠ Brakuje: 8×S  (niedobór krytyczny)          │ │
│  └──────────────────────────────────────────────  │ │
└─────────────────────────────────────────────────────┘
```

### Unit type badge colors

| Type | Color |
|------|-------|
| S | `--red` (critical) |
| N | `--purple` (specialist) |
| P | `--amber` (basic team) |
| T | `--text-mid` (transport) |

### `frontend/app.js`

1. `async function loadEvacuationDispatch()` — fetches `/api/flood/evacuation-dispatch`,
   renders hospital evacuation cards into `#flood-evac-list`.

2. `function renderEvacCard(order)` — builds one hospital card (patient groups table +
   unit list + deficit warning).

3. `function renderUnitRow(unit)` — one unit row: type badge, call sign, status dot,
   distance, ETA.

4. Badge update: after each `loadFloodAssessment()`, count hospitals with `evacuate` status
   and toggle the `●` badge on the "Ewakuacja" tab.

5. `refreshFloodTab()` — add `await loadEvacuationDispatch()` to the cycle (only when
   evac tab is visible, to avoid wasted fetches).

### `frontend/style.css`

- `.evac-hospital-card` — card container, left border colored by priority
- `.evac-priority-badge` — `NATYCHMIASTOWE` / `PILNE` / `PLANOWE` with matching color
- `.evac-patient-row` — compact table row: category | count | units needed
- `.evac-unit-row` — unit entry: type badge | call sign | status dot | distance | ETA
- `.evac-deficit-warning` — red warning strip when `deficit > 0`
- `.evac-tab-badge` — red dot indicator on the tab label

---

## Implementation order

1. `services/evacuation.py` — patient derivation + unit generation + dispatch logic
2. `routers/flood.py` — wire `GET /api/flood/evacuation-dispatch`
3. `frontend/index.html` — Ewakuacja sub-tab structure + `#flood-evac-list` container
4. `frontend/style.css` — evac panel styles
5. `frontend/app.js` — `loadEvacuationDispatch()`, render functions, tab badge, refresh hook

## Files touched

```
services/evacuation.py          NEW — dispatch logic, unit generation
routers/flood.py                add GET /api/flood/evacuation-dispatch
frontend/index.html             Ewakuacja sub-tab tab + container
frontend/style.css              evac panel component styles
frontend/app.js                 loadEvacuationDispatch(), render functions, badge
```

## Observable output (done criteria)

- "Ewakuacja" sub-tab appears in Powódź dashboard; red dot appears when hospital is in `evacuate`.
- Each evacuating hospital shows patient groups (ICU / ward / ambulatory) with counts and unit requirements.
- Available transport units listed with type (S/N/P/T), call sign, distance, ETA.
- Deficit warning shown when available units < required.
- Panel updates on each flood tab auto-refresh cycle.
