# Sentinel — User Personas

> How the same pluggable pipeline serves two distinct client profiles.

---

## Client A — Regional Resource Coordinator

### Role

Manages what resources are available and where across a voivodeship. Makes allocation decisions when demand exceeds supply. Accountable for voivodeship-level consequences of a crisis.

This is not an incident commander. Firefighters, police, and medical teams manage the scene. Client A manages the consequences and the resources.

| Incident Commander | Client A (Resource Coordinator) |
|---|---|
| "What is happening right now?" | "What do I have available and where?" |
| Manages the incident | Manages consequences and resources |
| Needs live incident feed | Needs inventory + allocation logic |
| Spatial awareness of the event | Spatial awareness of the resources |

### Mental Model

"Houston for the voivodeship." NASA Mission Control model: aggregate go/no-go status across domains, not granular event monitoring. Flight Director, not analyst.

### Decision Types

Three concrete examples that define what the interface must support:

- **Museum fire:** Which transport companies can move artwork? Where are their vehicles? Which roads are passable?
- **Medical crisis:** Which hospitals have available beds? What specializations are available? Where to route incoming patients?
- **Flood:** Which ZRM units are free? Which routes are blocked? Which hospitals are at risk?

In every case: inventory first, allocation second.

### What They Need from the Pipeline

**Stage 1 — Sources**
Live resource status: transport vehicle locations, hospital bed counts, ZRM unit availability, route conditions.

**Stage 3 — Reactions**
ThresholdBreached events (river levels, air quality) surfaced as domain status changes. Not raw sensor readings — domain-level signals that affect resource availability or demand.

**Stage 4 — Outputs**
- Domain switcher dashboard: four domains (Medical, Transport, Environment, Infrastructure), one at a time
- KPI strip per domain: resource availability counts, not threat counts ("ZRM available: 8/12", not "active fires: 2")
- Resource inventory panel: list of resources by domain, status, location
- Passive map: shows where resources are, reacts to selection, never auto-refreshes
- Demand queue: incoming resource requests with Assign and Defer actions

### What They Explicitly Do Not Need

- Incident command feed or live telemetry from the scene
- Automated alerts to schools, hospitals, or citizens
- Operational decisions (those belong to the incident commander)
- Multi-user role system (near-term)

---

## Client B — Flood Duty Officer

### Role

Duty officer at a regional crisis management center. Responsible for daily monitoring of flood and hydrological conditions across the voivodeship. Produces morning and evening situation reports. Escalates to county emergency managers when conditions warrant.

This is a structured, repeating daily workflow — not ad-hoc response. The job has a known rhythm: check conditions, generate report, distribute, escalate if needed.

### Decision Types

- Escalating to county emergency managers (PCZK) when gauge readings breach thresholds
- Dispatching resources when conditions meet defined criteria
- Maintaining a situation log for handoff between shifts
- Drafting communications to local government units (JST)

### What They Need from the Pipeline

**Stage 1 — Sources**
- IMGW HYDRO gauge readings refreshed every 30 minutes
- IMGW hydro warnings and narrative bulletins
- Alert level classification: normal / warning / alarm per gauge station

**Stage 2 — Observations**
- Historical gauge readings persisted to database (not just live snapshot)
- Trend data: water level trajectory over last 24h, 7 days, 30 days
- Time-series charts per station for visual trend analysis

**Stage 3 — Reactions**
- Trend alarm: three consecutive rising readings triggers "UWAGA POZIOM WODY WZRASTA"
- Scheduled report generation at 06:30 and 18:30 daily (deterministic template, no LLM)
- ThresholdBreached events routed to alert delivery

**Stage 4 — Outputs**
- Morning and evening PDF reports delivered by email at scheduled times
- Immediate alert on threshold breach (email; SMS and Telegram on roadmap)
- Operator panel with gauge map, trend charts, and situation log
- Acknowledgement workflow: duty officer confirms awareness of an alert and can add manual notes
- Draft communications for PCZK/JST (LLM-assisted, not auto-sent)

### What They Explicitly Do Not Need

- Resource allocation interface (transport, ZRM, hospitals)
- General-purpose event feed unrelated to hydrology
- The domain switcher UI (single-domain workflow)

---

## Same Pipeline, Different Output Plugins

Both clients are served by the same Stage 1–3 infrastructure. Stage 1 (Sources) runs the IMGW Hydro plugin for both — the same gauge data feeds Client B's daily reports and Client A's Environment domain KPIs. Stage 2 (Observations) adds time-series persistence for Client B without touching Client A's data path. Stage 3 (Reactions) fires ThresholdBreached for both, but the hooks differ: Client A's hook updates a domain status tile; Client B's hook triggers a scheduled report and an email alert. The difference between the two deployments is entirely in Stage 4 output plugin configuration — Client A gets the domain switcher dashboard, Client B gets the operator panel with scheduled reports and alert delivery. The pipeline itself does not change.
