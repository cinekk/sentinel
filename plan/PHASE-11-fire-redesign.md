# Phase 11 — Fire Simulation Redesign + UI Unification

> **Goal:** Rebuild the fire tab (SIM → POŻAR) to match the quality of the flood tab.
> Unify trigger UX for both scenarios. Allow both to run simultaneously.
> Voice briefing covers whichever scenarios are active.
>
> Scenario: **Pożar Zakładów Azotowych Puławy** — wiatr NE 15 km/h, rosnący obłok dymu,
> sukcesywne zagrożenie dla szkół, DPS i szpitala.

**Status:** 🔲 Not started

---

## What Phase 10 shipped (already on main)

Phase 10 is complete. Phase 11 builds directly on it — no dependency gap.

| Component | Shipped in Phase 10 |
|---|---|
| `FloodScenarioPlugin` | ✅ scripted 12-tick loop |
| `routers/flood_scenario.py` | ✅ `POST /start|stop|reset`, `GET /state` |
| Frontend flood controls | ✅ START/STOP/RESET + progress bar + narrative time in POWÓDŹ tab |
| Script act models | ✅ `GaugeOverrideAct`, `InjectEventsAct`, `HospitalOverrideAct`, `CrisisEventAct` |
| Mutual exclusion | ✅ **flood start → stops fire** (`routers/flood_scenario.py` L37-39) |

Phase 11 does **not** need to add flood frontend controls — they're done.
Phase 11 does need to **remove** the mutual exclusion.

---

## Architecture note: how fire impacts already flow

`SimulationPlugin.start()` writes a `CrisisEvent` with `zone_shape="ellipse"` to `crisis_store`.
Each tick patches the ellipse geometry (semi_major, semi_minor, bearing).

`GET /api/v1/crisis/affected` → calls `facilities_in_zones(active_crises, resources)` →
handles ellipse geometry → returns facilities with `level`, `action`, `crisis_id`.

**Conclusion: fire impacts are already computed in real-time. No new endpoint or service is needed.**

The fire tab panel just needs to **display** data that already flows through `crisis/affected`,
filtered by the active fire `crisis_id` (available from `GET /api/simulation/state`).

---

## Tasks

### 1. Remove mutual exclusion — `routers/flood_scenario.py`

Delete lines 36-39 from `start_flood_scenario()`:

```python
# DELETE these lines:
# Mutual exclusion: stop fire simulation if running
fire_plugin = registry.get("simulation_threat")
if fire_plugin and fire_plugin.running:
    fire_plugin.stop()
```

No reverse exists in `routers/simulation.py` (fire start never stopped flood) — nothing to change there.

After this change: both simulations can run concurrently. Each has its own crisis event in
`crisis_store` (`type="fire"` vs `type="flood"`), independent plugins, independent data.

---

### 2. Fire script layer — `plugins/simulation.py`

Add a lightweight `_FIRE_SCRIPT` list executed during `_advance()`. Injects real `EventRow`s
(112 calls, fire incidents) at key ticks — same `InjectEventsAct` pattern as `FloodScenarioPlugin`.

```python
from models import InjectEventsAct

_FIRE_SCRIPT: list[tuple[int, InjectEventsAct]] = [
    (2,  InjectEventsAct(n=3, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=1.5,
                         category="fire",    severity="high")),    # T+20min — straż
    (4,  InjectEventsAct(n=5, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=3.0,
                         category="medical", severity="high")),    # T+40min — zatrucia dymem
    (7,  InjectEventsAct(n=4, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=4.0,
                         category="medical", severity="critical")),# T+70min — presja szpitala
    (10, InjectEventsAct(n=2, lat=_PULAWY_LAT, lon=_PULAWY_LON, radius_km=1.0,
                         category="fire",    severity="critical")),# T+100min — wtórny zapłon
]
```

In `_advance()`, after patching the ellipse, add:

```python
acts_for_tick = [act for tick, act in _FIRE_SCRIPT if tick == self._tick]
for act in acts_for_tick:
    asyncio.create_task(self._execute_inject(act))
```

New private method `_execute_inject(act: InjectEventsAct)` — writes `act.n` `EventRow`s with
random jitter within `act.radius_km` (same logic already in `FloodScenarioPlugin._execute_act()`).

Also add `narrative_time_min` to `state` property:

```python
@property
def state(self) -> dict:
    elapsed_s = self._tick * self._config.tick_interval_seconds
    return {
        "running": self._running,
        "tick": self._tick,
        "narrative_time_min": round(elapsed_s / 60, 1),
        "config": self._config.model_dump(),
        "crisis_id": self._crisis_id,
    }
```

---

### 3. Frontend: Tab rename + reorder — `frontend/index.html`

**Button bar** — two changes:
1. Label `SIM` → `POŻAR` (keep `data-tab="sim"` and `data-panel="sim"` — no JS changes needed)
2. Move LOG button to after POWÓDŹ button

Current order: `WARSTWY | AI | SIM | LOG | POWÓDŹ`  
New order:     `WARSTWY | AI | POŻAR | POWÓDŹ | LOG`

Also move `<div class="tab-panel tab-panel--log" data-panel="log">` to after the flood panel in HTML.

---

### 4. Frontend: Fire tab UI redesign — `frontend/index.html` + `frontend/app.js`

Keep existing sliders (wind speed, direction, intensity) and START/STOP/RESET controls.
Add three new sections below:

**a) Narrative time in the header:**

```html
<div class="sim-group-header">
  <span class="section-label">Symulacja pożaru — Puławy</span>
  <span id="sim-narrative-time" class="sim-narrative-time" style="display:none"></span>
  <span id="sim-dot"></span>
  <span id="sim-label" class="sim-status-label">Gotowa</span>
</div>
```

**b) Affected facilities panel:**

```html
<div class="sim-group" id="fire-impacts-group">
  <div class="sim-group-header">
    <span class="section-label">Obiekty w strefie</span>
    <span class="stab-badge stab-badge--evac" id="fire-evac-count" style="display:none"></span>
    <span class="stab-badge stab-badge--warn" id="fire-warn-count" style="display:none"></span>
  </div>
  <div id="fire-impact-list" class="fire-impact-list">
    <div class="empty-state">Symulacja nieaktywna</div>
  </div>
</div>
```

**c) PM2.5 sensors panel:**

```html
<div class="sim-group" id="fire-sensors-group">
  <div class="sim-group-header">
    <span class="section-label">Czujniki PM2.5</span>
  </div>
  <div id="fire-sensor-table" class="fire-sensor-table"></div>
</div>
```

**`app.js` changes:**

In `pollSimulation()` (already polls `/api/simulation/state`):
- Show/hide `#sim-narrative-time`, update to `T+{N} min` from `state.narrative_time_min`
- If `state.crisis_id` is set: call `renderFireImpacts(state.crisis_id)`
- Else: clear fire impact panel

New `renderFireImpacts(crisisId)`:
```js
// Uses data already polled by pollAlerts() — no extra fetch
function renderFireImpacts(crisisId) {
  const fireImpacts = (_lastAlerts || []).filter(a => a.crisis_id === crisisId);
  const evac = fireImpacts.filter(a => a.level === 'inside');
  const warn = fireImpacts.filter(a => a.level === 'approaching');
  // render rows, update badge counts
}
```

`_lastAlerts` is the cached result from `pollAlerts()` (already populated every 5s from
`GET /api/v1/crisis/affected`). **No additional fetch.**

`renderAlertHud()` already calls `renderAlertHud(alerts)` with all impacts — the fire tab panel
is just a second, always-visible rendering of the same data, scoped to the fire crisis.

PM2.5 sensors: data lives in the `simulation_threat` GeoJSON layer (already loaded as a map
layer). Read from `layerData["simulation_threat"]?.features` where `props.type === "sensor"`.

---

### 5. Voice briefing — `services/briefing.py` + `routers/voice.py`

**Problem:** Current briefing covers fire via `active_crises` → `facilities_in_zones()` (correct).
What it doesn't cover: flood hospital status (EVACUATE/AT_RISK hospitals from flood scenario).

**`services/briefing.py` — extend `BriefingContext`:**

```python
@dataclass
class BriefingContext:
    active_crises: list[CrisisEvent] = field(default_factory=list)
    affected: list[dict] = field(default_factory=list)
    sim_state: dict | None = None
    flood_scenario_state: dict | None = None          # NEW
    flood_hospitals: list[dict] = field(default_factory=list)  # NEW
    air_quality: list[dict] = field(default_factory=list)
    weather: list[dict] = field(default_factory=list)
```

**`generate_briefing_text()` — add flood section after the existing crises loop:**

```python
# Flood scenario section (appended after fire section if both active)
if ctx.flood_scenario_state and ctx.flood_scenario_state.get("running"):
    t_min = ctx.flood_scenario_state.get("narrative_time_min", 0)
    parts.append(
        f"Jednocześnie aktywna symulacja powodzi — "
        f"czas narracyjny plus {t_min:.0f} minut."
    )
    evacuate = [h for h in ctx.flood_hospitals if h.get("status") == "evacuate"]
    at_risk   = [h for h in ctx.flood_hospitals if h.get("status") == "at_risk"]
    if evacuate:
        names = ", ".join(h["name"] for h in evacuate[:3])
        parts.append(f"Szpitale wymagające natychmiastowej ewakuacji: {names}.")
    if at_risk:
        names = ", ".join(h["name"] for h in at_risk[:3])
        parts.append(f"Szpitale w podwyższonej gotowości: {names}.")
    if not evacuate and not at_risk:
        parts.append("Szpitale w regionie powodzi pozostają operacyjne.")
```

The existing `else: "Brak aktywnych zagrożeń..."` branch must check both crises AND flood state:

```python
# Change final else condition:
elif not ctx.active_crises and not (ctx.flood_scenario_state or {}).get("running"):
    parts.append("Brak aktywnych zagrożeń. System monitoringu w trybie czuwania.")
```

**`routers/voice.py` — extend `voice_briefing()`:**

```python
flood_plugin = registry.get("flood_scenario")
flood_state  = flood_plugin.state if flood_plugin else None

flood_hospitals: list[dict] = []
if flood_state and flood_state.get("running"):
    from services.flood_assessment import get_assessment
    statuses = await get_assessment()
    flood_hospitals = [
        s.model_dump() for s in statuses
        if s.status in ("evacuate", "at_risk")
    ]

ctx = BriefingContext(
    ...existing fields...,
    flood_scenario_state=flood_state,
    flood_hospitals=flood_hospitals,
)
```

**Guarantee:** If only fire running → briefing unchanged (no flood section).
If only flood running → crises loop empty, flood section fires.
If both → fire section then flood section, sequential, ElevenLabs reads naturally.

---

## File change summary

| File | Change | Lines est. |
|---|---|---|
| `routers/flood_scenario.py` | Delete 3 lines (mutual exclusion) | -3 |
| `plugins/simulation.py` | Add `_FIRE_SCRIPT` + `_execute_inject()` + `narrative_time_min` in state | +35 |
| `services/briefing.py` | Extend `BriefingContext` + flood section in template | +25 |
| `routers/voice.py` | Load flood scenario state + assessment, pass to context | +15 |
| `frontend/index.html` | Rename SIM→POŻAR, reorder tabs, add narrative time + facility panel + sensor panel | +30 |
| `frontend/app.js` | `renderFireImpacts()` from `_lastAlerts`, PM2.5 sensor table, narrative time display | +60 |

**Not touched:** `services/fire_impact.py` (doesn't exist, not needed),
`services/flood_assessment.py`, `services/spatial.py`, crisis API, any existing tests.

---

## How data flows — summary

```
SimulationPlugin
  tick N → patches ellipse in crisis_store → facilities_in_zones()
                                           → GET /api/v1/crisis/affected
                                                ↓
                                           renderAlertHud()    (HUD overlay, existing)
                                           renderFireImpacts() (POŻAR tab panel, new)

  tick N → _FIRE_SCRIPT → InjectEventsAct → EventRow in DB
                                          → event log (existing)
                                          → demand_112 counters (existing)
```

No new service layer. No new endpoint. Same data, second render target.

---

## UI: Expected POŻAR tab

```
[ Symulacja pożaru — Puławy ]   T+40 min   ● AKTYWNA
  [▶ START] [■ STOP] [↺ RESET]
  Wiatr km/h  [===15===]
  Kierunek°   [===45 (NE)===]
  Intensywność [=1=]

[ Obiekty w strefie ]   🔴 2   🟠 5
  DPS Puławy ul. Piaskowa   EWAKUACJA    0.8 km
  SP nr 4 Puławy            EWAKUACJA    1.1 km
  Szpital Puławy            ZAMKNIĘCIE   1.9 km
  ZSZ Puławy                OSTRZEŻENIE  2.4 km
  …

[ Czujniki PM2.5 ]
  Czujnik 1   347 µg/m³   ████
  Czujnik 2   289 µg/m³   ███
  Czujnik 3   112 µg/m³   ██
  Czujnik 4    48 µg/m³   █
  Czujnik 5    18 µg/m³   ▌
```

---

## Smoke tests

1. Start server → tab order: WARSTWY, AI, POŻAR, POWÓDŹ, LOG ✓
2. `POST /api/simulation/start` → POŻAR tab: dot active, T+0 min, empty facility list
3. Wait 3 ticks → `GET /api/v1/crisis/affected` has fire entries; POŻAR panel populates
4. `POST /api/flood-scenario/start` → **fire sim still running** (no mutual exclusion)
5. Both dots active simultaneously ✓
6. `POST /api/voice/briefing` → response text contains fire section AND flood section ✓
7. Flood only: stop fire → briefing has only flood section, no "Brak zagrożeń" ✓
8. Neither: stop both → briefing: "Brak aktywnych zagrożeń" ✓
9. Fire only with tick_interval=2 (fast) → PM2.5 sensor table updates each poll ✓
