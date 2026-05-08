# Evacuation Dispatch

## Purpose

Given a list of hospital flood assessments, produces a full dispatch picture:
which transport units to send where, in what order, and with what ETA.

Driven entirely by rule-based logic — no LLM. Inputs come from
`services/flood_assessment.assess_hospitals()`.

---

## Entry Point

```python
get_evacuation_dispatch(
    statuses: list[HospitalFloodStatus],
    transfer_map: dict[str, str] | None = None,
) -> list[HospitalEvacOrder]
```

Only hospitals with `status == "evacuate"` or `status == "at_risk"` produce
orders. `operational` hospitals are included in the unit pool but not assigned orders.

`transfer_map` is an optional `hospital_id → transfer target name` dict.
If provided, it appears in the order as `transfer_target`.

---

## Output: `HospitalEvacOrder`

```python
hospital_id: str
name: str
lat: float
lon: float
priority: str           # "NATYCHMIASTOWE" | "PILNE" | "PLANOWE"
patient_groups: list[PatientGroup]
assigned_units: list[TransportUnit]
units_needed: int       # total units required
units_available: int    # units actually assigned
deficit: int            # units_needed - units_available (0 = fully covered)
transfer_target: str | None
```

---

## Priority Classification

| Condition | Priority |
|---|---|
| `evacuate` + generator offline OR in ISOK P=1% zone | `NATYCHMIASTOWE` |
| `evacuate` (other reasons) | `PILNE` |
| `at_risk` | `PLANOWE` |

Orders are processed in priority order so the nearest units go to the
most critical hospitals first.

---

## Patient Groups

Derived from `beds_total_physical` and `personnel_pct` (used as occupancy proxy):

```
occupancy = min(personnel_pct / 100, 0.95) × 0.90
total_patients = beds × occupancy

icu       = max(1, round(total × 5%))   → requires unit type S (specjalistyczny)
ward      = round(total × 60%)          → requires unit type P (podstawowy)
ambulatory = remainder                  → requires unit type T (transportowy)
```

**Unit types and capacities:**

| Type | Name | Capacity | Speed |
|---|---|---|---|
| S | Specjalistyczny | 1 patient/trip | 70 km/h |
| N | Neonatologiczny | 1 patient/trip | 65 km/h |
| P | Podstawowy | 2 patients/trip | 75 km/h |
| T | Transportowy | 4 patients/trip | 90 km/h |

Units needed per group = `ceil(patient_count / unit_capacity)`.

---

## Unit Pool Generation

The transport unit pool is generated from all hospitals (including operational ones)
via `generate_unit_pool(bases)`:

- Each hospital with `sor=True` contributes 2 units; others contribute 1
- Unit types cycle through: 40% T, 30% P, 20% S, 10% N (`_TYPE_CYCLE`)
- Unit positions are jittered ±0.05° lat / ±0.08° lon from the hospital
- ~10% of units are randomly marked `unavailable` (seeded with `random.Random(42)` — deterministic per run)
- Unit IDs: `LU-{type}-{idx:02d}` (e.g. `LU-T-01`, `LU-S-03`)

---

## Unit Assignment

Greedy nearest-first per patient group:

1. Hospitals sorted by priority (NATYCHMIASTOWE first, then by risk factor count)
2. For each hospital, for each patient group:
   - Filter pool: correct unit type + `status="available"` + not already taken
   - Sort by haversine distance from hospital
   - Take the first N needed
   - Mark taken (no unit assigned twice across hospitals)
3. ETA = `ceil(distance × 1.35 / speed × 60)` minutes — road distance multiplier 1.35×

---

## Example Response Shape

```json
[
  {
    "hospital_id": "szp_pulawy_001",
    "name": "SP ZOZ Puławy",
    "priority": "NATYCHMIASTOWE",
    "patient_groups": [
      {"category": "icu", "label": "OIT / OIOM", "count": 3, "required_unit_type": "S", "units_needed": 3},
      {"category": "ward", "label": "Oddział ogólny", "count": 72, "required_unit_type": "P", "units_needed": 36},
      {"category": "ambulatory", "label": "Ambulatoryjni", "count": 45, "required_unit_type": "T", "units_needed": 12}
    ],
    "assigned_units": [
      {"unit_id": "LU-S-03", "unit_type": "S", "distance_km": 4.2, "eta_minutes": 6, "status": "available"},
      ...
    ],
    "units_needed": 51,
    "units_available": 38,
    "deficit": 13,
    "transfer_target": "Szpital Lublin"
  }
]
```

A non-zero `deficit` means the unit pool is exhausted for that type — the
gap represents unmet evacuation capacity that needs external resource allocation.

---

## Relationship to Flood Assessment

```
assess_hospitals()                     → list[HospitalFloodStatus]
    ↓
get_evacuation_dispatch(statuses)      → list[HospitalEvacOrder]
```

The evacuation dispatch is stateless — it does not cache results. Call
`assess_hospitals()` first to get fresh statuses, then pass them to
`get_evacuation_dispatch()`. The assessment cache (2 min TTL) handles
rate-limiting the expensive DB and gauge queries.
