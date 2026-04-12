# Phase 11 — Fire Simulation Redesign + UI Unification

> **Goal:** Rebuild the fire simulation tab (SIM → POŻAR) to match the quality of the flood
> simulation. Unify trigger mechanisms for both scenarios. Both simulations run concurrently.
> Voice briefing covers whichever scenarios are active.
>
> Scenario: **Pożar Zakładów Azotowych Puławy** — wiatr NE 15 km/h, rozprzestrzeniający się
> obłok dymu z PM2.5/PM10, sukcesywne zagrożenie dla szkół, DPS i szpitala.

**Status:** 🔲 Not started  
**Depends on:** Phase 9 complete (flood assessment), Phase 10 at least planned

---

## Current state

| | Fire (SIM) | Flood (POWÓDŹ) |
|---|---|---|
| Backend | `SimulationPlugin` — physics ellipse ✅ | `FloodAssessmentService` ✅, `FloodScenarioPlugin` ❌ (Phase 10) |
| Facility impact | `facilities_in_zones()` via crisis_store ✅ | `FloodAssessmentService` ✅ |
| API trigger | `POST /api/simulation/{start,stop,reset}` ✅ | No scripted scenario yet ❌ |
| Frontend controls | START/STOP/RESET + sliders ✅ | Override panel only, no scenario trigger ❌ |
| Facility status panel | ❌ missing | ✅ hospital table with AT_RISK/EVACUATE |
| Narrative time display | ❌ missing | ❌ missing (Phase 10) |
| Voice briefing | Partial (crises → affected counts) | ❌ flood hospitals not in briefing |

## Design decisions

1. **Fire keeps physics engine** — the ellipse plume is correct science; don't replace with scripts.
   Add a **lightweight script layer on top** for infrastructure events (facility overrides, 112 injections)
   at predetermined ticks — same pattern as Phase 10 flood, but simpler.

2. **Fire impact as a service** — new `services/fire_impact.py` analogous to `flood_assessment.py`.
   Derives facility status directly from `facilities_in_zones()` output (no overrides needed for fire —
   the physics ellipse is the ground truth). Classifies: inside ellipse → EVACUATE, approaching (1.5×) → AT_RISK.

3. **Concurrent scenarios** — Phase 10 planned mutual exclusion. User requirement overrides this:
   both scenarios MUST be able to run simultaneously (different geography, different impact domain).
   Phase 10's mutual-exclusion task is dropped. Briefing covers both.

4. **Flood scenario trigger in UI** — Phase 10's frontend task (START/STOP/RESET for flood) is
   brought forward here as a dependency: without it, Phase 11's "both triggerable from UI" goal is incomplete.

---

## Tasks

### 1. `services/fire_impact.py` — Fire Impact Assessment Service

New file, ~90 lines. Analogous pattern to `services/flood_assessment.py`.

```python
class FireFacilityImpact(BaseModel):
    facility_id: str
    name: str
    type: str           # "hospital" | "school" | "social"
    lat: float
    lon: float
    status: Literal["evacuate", "at_risk"]
    recommendation: str  # human-readable action
    distance_km: float
    crisis_id: str
```

Logic:
- `get_fire_impacts() -> list[FireFacilityImpact]`
  - Get all active fire crises from `crisis_store.list_active()` filtered `type="fire"`
  - Load all resource features from `hospitals`, `schools`, `social` plugins
  - Call `facilities_in_zones(fire_crises, resources)` — already handles ellipse geometry
  - Map `action="EWAKUACJA"` → `status="evacuate"`, `action="ZAMKNIĘCIE"/"OSTRZEŻENIE"` → `status="at_risk"`
  - Generate `recommendation` by facility type:
    - school → `"Zamknij placówkę, ewakuuj uczniów"`
    - social → `"Ewakuuj mieszkańców do strefy bezpiecznej"`
    - hospital → `"Przejdź w tryb gotowości, ogranicz przyjęcia"`
  - Cache TTL: 30 seconds
- `invalidate_fire_cache()` — clear cache (call after sim start/stop)

### 2. `GET /api/simulation/impacts` — new endpoint in `routers/simulation.py`

```python
@router.get("/impacts")
async def get_fire_impacts() -> list[FireFacilityImpact]:
    from services.fire_impact import get_fire_impacts
    return await get_fire_impacts()
```

Returns `[]` when simulation not running (no active fire crises).

Also extend `GET /api/simulation/state` to include `narrative_time_min`:

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

### 3. Fire script layer — `plugins/simulation.py` (light extension)

Add a hardcoded `_FIRE_SCRIPT` — list of `(tick, act)` pairs injecting 112 calls at key ticks.
No infrastructure overrides needed for fire (ellipse geometry handles facility classification).

```python
_FIRE_SCRIPT: list[tuple[int, dict]] = [
    (2,  {"n": 3,  "category": "fire",    "severity": "high"}),    # T+20min first responder calls
    (4,  {"n": 5,  "category": "medical", "severity": "high"}),    # T+40min smoke inhalation
    (7,  {"n": 4,  "category": "medical", "severity": "critical"}),# T+70min hospital pressure
    (10, {"n": 2,  "category": "fire",    "severity": "critical"}),# T+100min secondary ignition
]
```

Each act at tick N injects N EventRows near the source (same `InjectEventsAct` logic as Phase 10).
Extend `_advance()` in `SimulationPlugin` to check `_FIRE_SCRIPT` and execute matching acts.

Also call `invalidate_fire_cache()` after each tick advance.

### 4. Frontend: Tab rename + reorder — `frontend/index.html`

**Tab button order** (line 62–85 currently):

Current: WARSTWY | AI | SIM | LOG | POWÓDŹ  
New:     WARSTWY | AI | POŻAR | POWÓDŹ | LOG

Changes:
- Rename tab button label: `SIM` → `POŻAR` (keep `data-tab="sim"` unchanged — minimises JS changes)
- Move the LOG button to after the POWÓDŹ button
- Move the `<div data-panel="log">` to after `<div data-panel="flood">` in the HTML

```html
<!-- After change, tab bar order: -->
<button class="stab active" data-tab="layers">WARSTWY</button>
<button class="stab"        data-tab="ai">AI</button>
<button class="stab"        data-tab="sim">POŻAR          <!-- renamed, same data-tab -->
  <span class="stab-badge stab-badge--sim" id="sim-tab-badge">●</span>
</button>
<button class="stab stab--flood" data-tab="flood">POWÓDŹ</button>
<button class="stab"        data-tab="log">LOG            <!-- moved last -->
  <span class="stab-badge" id="events-count-badge">0</span>
</button>
```

### 5. Frontend: Fire tab UI redesign — `frontend/index.html` + `frontend/app.js`

Replace the current SIM panel content. Keep sliders and controls; add:

**a) Status header with narrative time**

```html
<div class="sim-group-header">
  <span class="section-label">Symulacja pożaru — Puławy</span>
  <span id="sim-narrative-time" class="sim-narrative-time">—</span>  <!-- "T+40 min" -->
  <span id="sim-dot"></span>
  <span id="sim-label" class="sim-status-label">Gotowa</span>
</div>
```

**b) Affected facilities panel** (new, below controls)

```html
<div class="sim-group" id="fire-impacts-group">
  <div class="sim-group-header">
    <span class="section-label">Obiekty w strefie</span>
    <span class="stab-badge stab-badge--evac" id="fire-evac-count">0</span>
    <span class="stab-badge stab-badge--warn" id="fire-atrisk-count">0</span>
  </div>
  <div id="fire-impact-list" class="fire-impact-list">
    <div class="empty-state">Symulacja nieaktywna</div>
  </div>
</div>
```

**c) PM2.5 sensor mini-table** (new, below impacts)

```html
<div class="sim-group" id="fire-sensors-group">
  <div class="sim-group-header">
    <span class="section-label">Czujniki PM2.5</span>
  </div>
  <div id="fire-sensor-table" class="fire-sensor-table"></div>
</div>
```

**d) `app.js` changes** for fire tab:

- In `pollSimulation()` (already polling `/api/simulation/state`):
  - Read `state.narrative_time_min` → update `#sim-narrative-time` (format: `T+{N} min`)
  - If running: call `pollFireImpacts()` after state poll
- New `pollFireImpacts()`:
  ```js
  async function pollFireImpacts() {
    const res = await fetch(`${API}/api/simulation/impacts`);
    const impacts = await res.json();
    renderFireImpacts(impacts);
  }
  ```
- New `renderFireImpacts(impacts)`:
  - Group by status (evacuate first, then at_risk)
  - Build rows: type icon + name + status badge + recommendation
  - Update `#fire-evac-count` and `#fire-atrisk-count` badges
  - Empty state: "Brak obiektów w strefie" when no impacts
- Sensor data: pull from layer `simulation_threat` GeoJSON features where `type="sensor"`:
  - Already fetched as a map layer; read from `layerData["simulation_threat"]` if available
  - Build mini-table: Czujnik 1..5 / PM2.5 value / color-coded by threshold (>50=warn, >150=alert, >250=crit)

### 6. Frontend: Flood tab — add scenario controls — `frontend/index.html` + `frontend/app.js`

> This is Phase 10 task 5 (frontend integration), brought forward as dependency.

**Add at the top of the flood panel** (before AI Assessment section):

```html
<div class="flood-section flood-section--scenario">
  <div class="flood-section-header">
    <span class="section-label">Scenariusz: Powódź Puławy</span>
    <span id="flood-scenario-narrative" class="sim-narrative-time">—</span>  <!-- "T+1h20min" -->
    <span id="flood-scenario-dot" class="sim-dot"></span>
    <span id="flood-scenario-label" class="sim-status-label">Gotowy</span>
  </div>
  <div class="sim-controls">
    <button class="sim-btn primary" id="btn-flood-start">▶ START</button>
    <button class="sim-btn danger"  id="btn-flood-stop">■ STOP</button>
    <button class="sim-btn"        id="btn-flood-reset">↺ RESET</button>
  </div>
  <div class="flood-tick-bar">
    <div id="flood-tick-progress" class="flood-tick-fill"></div>
    <span id="flood-tick-label" class="flood-tick-label">Tick 0 / 12</span>
  </div>
</div>
```

**`app.js` additions:**
- Wire `#btn-flood-start` → `POST /api/flood-scenario/start`
- Wire `#btn-flood-stop` → `POST /api/flood-scenario/stop`
- Wire `#btn-flood-reset` → `POST /api/flood-scenario/reset`
- New `pollFloodScenario()`: `GET /api/flood-scenario/state`
  - Update dot, label, narrative time display (`T+{N*10}min` where tick_interval=15s → 10min narrative)
  - Update progress bar: `(tick/12) * 100%`
  - When running: trigger `pollFloodAssessment()` refresh (currently 5min → reduce to 15s when scenario active)
- Add to main poll interval (alongside simulation poll)

**Note:** `POST /api/flood-scenario/start|stop|reset` and `GET /api/flood-scenario/state` are Phase 10
backend tasks. This phase only adds the frontend controls; Phase 10 must be done first or in parallel.

### 7. Concurrent scenario support — remove mutual exclusion

Phase 10 spec (Integration section, last task) required:
> "start() on one should stop() the other"

**Drop this requirement.** Both scenarios:
- Operate on independent data stores (fire → crisis_store ellipse, flood → IMGW overrides + hospital overrides)
- Have independent crisis event types (`type="fire"` vs `type="flood"`)
- Have independent frontend panels
- Voice briefing handles both (see task 8)

No code change needed if Phase 10 hasn't implemented mutual exclusion yet.
If it was already implemented: remove the cross-stop call from `FloodScenarioPlugin.start()` and `SimulationPlugin.start()`.

### 8. Voice briefing — `services/briefing.py` + `routers/voice.py`

**Problem:** Current briefing only covers fire (via `active_crises` → affected facilities).
When both scenarios active, flood hospitals (EVACUATE/AT_RISK) are not mentioned.

**`services/briefing.py` — extend `BriefingContext`:**

```python
@dataclass
class BriefingContext:
    active_crises: list[CrisisEvent] = field(default_factory=list)
    affected: list[dict] = field(default_factory=list)
    sim_state: dict | None = None
    flood_scenario_state: dict | None = None       # NEW
    flood_hospitals: list[dict] = field(default_factory=list)  # NEW — HospitalFloodStatus dicts
    air_quality: list[dict] = field(default_factory=list)
    weather: list[dict] = field(default_factory=list)
```

**`generate_briefing_text()` additions:**

After the existing fire crises loop, add a flood section:

```python
# Flood scenario section
if ctx.flood_scenario_state and ctx.flood_scenario_state.get("running"):
    t_min = ctx.flood_scenario_state.get("narrative_time_min", 0)
    parts.append(
        f"Jednocześnie aktywna symulacja powodzi — czas narracyjny plus {t_min:.0f} minut."
    )
    evacuate = [h for h in ctx.flood_hospitals if h.get("status") == "evacuate"]
    at_risk   = [h for h in ctx.flood_hospitals if h.get("status") == "at_risk"]
    if evacuate:
        names = ", ".join(h["name"] for h in evacuate[:3])
        parts.append(
            f"Szpitale wymagające natychmiastowej ewakuacji: {names}."
        )
    if at_risk:
        names = ", ".join(h["name"] for h in at_risk[:3])
        parts.append(
            f"Szpitale w podwyższonej gotowości: {names}."
        )
    if not evacuate and not at_risk:
        parts.append("Szpitale w regionie powodzi pozostają operacyjne.")
elif not ctx.active_crises and not (ctx.flood_scenario_state or {}).get("running"):
    # override the "Brak aktywnych zagrożeń" only when truly nothing is active
    pass  # existing else branch handles this
```

**`routers/voice.py` — extend `voice_briefing()`:**

```python
@router.post("/briefing", response_model=BriefingResponse)
async def voice_briefing() -> BriefingResponse:
    active = store.list_active()

    affected: list[dict] = []
    if active:
        facilities = await _load_resource_features()
        affected = facilities_in_zones(active, facilities)

    sim_plugin   = registry.get("simulation_threat")
    flood_plugin = registry.get("flood_scenario")        # NEW

    # Load flood hospitals if scenario running or if any hospital at risk
    flood_hospitals: list[dict] = []
    flood_state = flood_plugin.state if flood_plugin else None
    if flood_state and flood_state.get("running"):        # NEW
        from services.flood_assessment import get_assessment
        statuses = await get_assessment()
        flood_hospitals = [
            s.model_dump() for s in statuses
            if s.status in ("evacuate", "at_risk")
        ]

    ctx = BriefingContext(
        active_crises=active,
        affected=affected,
        sim_state=sim_plugin.state if sim_plugin else None,
        flood_scenario_state=flood_state,               # NEW
        flood_hospitals=flood_hospitals,                 # NEW
        air_quality=await get_air_quality_data(),
        weather=WEATHER_DATA,
    )
    ...
```

**Key guarantee:** If only fire is running → briefing unchanged (no flood section added).
If only flood is running → crisis loop produces nothing (no fire crises), flood section fires.
If both running → fire crisis section + flood section, sequential.

---

## File change summary

| File | Change |
|---|---|
| `services/fire_impact.py` | **NEW** — `FireFacilityImpact`, `get_fire_impacts()`, cache |
| `routers/simulation.py` | Add `GET /api/simulation/impacts`; add `narrative_time_min` to state |
| `plugins/simulation.py` | Add `_FIRE_SCRIPT` + execution in `_advance()`; add `narrative_time_min` to `state` |
| `services/briefing.py` | Extend `BriefingContext`, add flood section to template |
| `routers/voice.py` | Pull flood scenario state + assessments, pass to `BriefingContext` |
| `frontend/index.html` | Rename SIM→POŻAR button, reorder tabs, fire facility panel, sensor table, flood scenario controls |
| `frontend/app.js` | `pollFireImpacts()`, `renderFireImpacts()`, PM2.5 sensor table, `pollFloodScenario()`, flood controls wiring |

**Not changed:** `plugins/simulation.py` physics engine, `services/flood_assessment.py`, crisis API, any existing tests.

---

## UI: Expected tab experience after this phase

### POŻAR tab (was SIM)

```
[ Symulacja pożaru — Puławy ]     T+40 min    ● AKTYWNA
  [▶ START] [■ STOP] [↺ RESET]
  Wiatr km/h [====15====]
  Kierunek°  [=====45 (NE)====]
  Intensywność [=1=]

[ Obiekty w strefie ]     🔴 2 ewakuacja   🟠 5 zagrożenie
  🔴 DPS Puławy ul. Piaskowa    EWAKUACJA   Ewakuuj mieszkańców
  🔴 SP nr 4 Puławy             EWAKUACJA   Zamknij, ewakuuj uczniów
  🟠 Szpital Puławy             GOTOWOŚĆ    Ogranicz przyjęcia
  🟠 ZSZ Puławy                 ZAGROŻENIE  Zamknij placówkę

[ Czujniki PM2.5 ]
  Czujnik 1   347 µg/m³   🔴
  Czujnik 2   289 µg/m³   🔴
  Czujnik 3   112 µg/m³   🟠
  Czujnik 4    48 µg/m³   🟡
  Czujnik 5    18 µg/m³   🟢
```

### POWÓDŹ tab (top section added)

```
[ Scenariusz: Powódź Puławy ]    T+1h20min    ● AKTYWNA
  [▶ START] [■ STOP] [↺ RESET]
  [████████████░░░░] Tick 8 / 12

[ Ocena AI ]  ↺
  ...existing content...

[ Rzeki — poziomy alarmowe ]
  ...existing content...

[ Szpitale ]
  ...existing content...
```

### Tab bar

```
WARSTWY | AI | POŻAR ● | POWÓDŹ ! | LOG 47
```

---

## Voice briefing: dual-scenario example

When both fire (T+40min) and flood (T+1h20min) are running:

> *"Briefing sytuacyjny, godzina 14:23.*
>
> *Aktywne zagrożenie: Pożar Zakładów Azotowych Puławy. Lokalizacja: 51.42 stopni północ, 21.97
> stopni wschód. Strefa ewakuacji: 2 kilometry. Strefa ostrzeżenia: 5 kilometrów. W strefie
> zagrożenia znajduje się 7 obiektów wrażliwych, w tym 1 szpital, 3 szkoły i 3 placówki opieki
> społecznej. 2 obiekty wymagają natychmiastowej ewakuacji. Jakość powietrza w rejonie zagrożenia:
> PM2.5 347 mikrogramów na metr sześcienny. Norma: 25. Status: bardzo zły. Kierunek wiatru: NE,
> prędkość 15 kilometrów na godzinę.*
>
> *Jednocześnie aktywna symulacja powodzi — czas narracyjny plus 80 minut. Szpitale wymagające
> natychmiastowej ewakuacji: Szpital w Puławach. Szpitale w podwyższonej gotowości: Szpital
> Rejonowy w Dęblinie.*
>
> *Koniec briefingu."*

---

## Smoke tests

1. Start server → open UI → verify tab order: WARSTWY, AI, POŻAR, POWÓDŹ, LOG
2. `POST /api/simulation/start` → POŻAR tab shows T+0min, dot turns active
3. Wait 3 ticks → "Obiekty w strefie" panel populates with ≥1 facility
4. `GET /api/simulation/impacts` → non-empty list
5. Verify facility recommendations are type-appropriate
6. `POST /api/simulation/stop` → impacts clear, narrative time stays visible
7. Start flood scenario → POWÓDŹ tab shows tick progress, narrative time
8. **Both running simultaneously:** start fire then flood → both dots active, neither stops the other
9. `POST /api/voice/briefing` with both running → response text contains both fire section and flood hospital section
10. `POST /api/simulation/reset` → crisis event deleted, impacts=[], narrative=—

---

## Out of scope

- Configurable fire scenario parameters beyond existing sliders
- Fire-specific hospital "override" panel (ellipse geometry is sufficient ground truth)
- Offline LLM fallback for briefing (Phase 6)
- useMaps sync for fire impact layer (Phase 7)
