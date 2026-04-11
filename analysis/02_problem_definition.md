# Problem Definition: SENTINEL — Inteligentna Mapa Województwa Lubelskiego

**Version:** 2.0  
**Date:** 2026-04-11  
**Primary Scenario:** ZESTAW D — Environmental Failure (Smog / Industrial Fire)  
**System Scope:** Geospatial Decision Dashboard for Marszałek Województwa Lubelskiego  
**Context:** Civil42 Hackathon — Special Challenge, Urząd Marszałkowski Województwa Lubelskiego

---

## 1. Problem Statement

### The Dual Problem

Województwo Lubelskie — 25,155 km², 213 gmin, 4 miasta na prawach powiatu, ~2.1 million inhabitants — generates vast amounts of operational data across dozens of disconnected systems. This data fragmentation creates two distinct problems:

**Problem A — Daily governance blindness.** The Marszałek and his staff lack a unified, spatial view of the voivodeship's current state. Data about healthcare, infrastructure, environment, education, and transport is scattered across BIP pages, PDF reports, separate agency portals, and Excel spreadsheets maintained by individual gminas. Preparing a regional overview requires hours of manual aggregation. When the Marszałek asks "what's the state of hospitals in powiat puławski?" — the answer takes hours, not seconds.

**Problem B — Crisis response latency.** During an acute environmental crisis — such as an industrial fire at Zakłady Azotowe Puławy producing toxic smoke — the crisis management team has no single operational view that integrates air quality readings, real-time wind vectors, the locations of sensitive facilities (schools, DPS care homes, hospitals), available transport assets, and population density into an actionable threat picture. Information is locked in six or more disconnected agency systems, accessible only by telephone. The operator must synthesize this picture manually, under acute time pressure, while simultaneously coordinating response. The result: delayed, inconsistent, and potentially life-threatening decisions.

**These are not two separate systems.** They are two modes of the same system — the same map, the same data layers, the same architecture. In steady-state, SENTINEL is a governance dashboard. When a crisis hits, it becomes a tactical command screen. The transition is seamless because the data is already integrated.

---

## 2. Current State — The Information Landscape of Lubelskie

### 2.1 Institutional Structure

The Urząd Marszałkowski Województwa Lubelskiego (seat: Lublin, ul. Artura Grottgera 4) manages the voivodeship through several departments. The Departament Bezpieczeństwa i Zarządzania Kryzysowego coordinates safety, emergency response, and inter-agency communication. This department is the operational owner of SENTINEL.

The voivodeship includes high-risk industrial assets (Zakłady Azotowe Puławy, Lubelski Węgiel Bogdanka), major river flood zones (Wisła, Bug, Wieprz), and a dispersed population with significant rural areas where official data channels are slow.

### 2.2 Data Fragmentation — Where the Numbers Live

| Data type | Custodian | Access method | Lubelskie specifics |
|---|---|---|---|
| Air quality (PM2.5, PM10, NO₂, SO₂) | GIOŚ | Public API, hourly, no push alerting | ~8 stations in Lubelskie; major gaps between Puławy and Chełm |
| Hyper-local particulate sensors | Airly (commercial) | Separate API, 5-min resolution | Dense in Lublin; sparse in rural powiatów |
| Wind, temperature, precipitation | IMGW | Forecast API, SYNOP observations | Station Lublin-Radawiec, Puławy; NWP model runs every 6h |
| School locations and enrollment | RSPO (MEN) | CSV/API, annual | ~1,800 schools and educational facilities in Lubelskie |
| DPS care homes | MRIPS | HTML table, no API, annual | ~60 DPS facilities across the voivodeship |
| Hospital locations and capacity | NFZ rejestr | JSON API, quarterly contracts | ~35 hospitals; key: SPZOZ Puławy, COZL Lublin, szpital Chełm |
| Road transport availability | GUS/REGON, local contracts | No live data; phone-based | MPK Lublin, PKS carriers, private operators |
| Population density | GUS census 2021 | WMS/WFS, static | 1km² grid; high density Lublin/Puławy, very low in eastern powiatów |
| Municipal reports, budgets, infrastructure | BIP pages of 213 gmin | HTML, PDF, XLSX — no standard format | Each gmina publishes differently; no aggregation exists |
| Social media signals | Facebook, X, local portals | No official monitoring | Lublin112, regional Facebook groups — often faster than official channels |

### 2.3 The Current Operational Procedure

#### Steady-State (Daily Governance)

When the Marszałek or his staff need a regional picture:

1. Staff member opens 5–10 different web portals to check air quality, hospital data, road conditions.
2. Downloads PDF reports from BIP pages of relevant gminas.
3. Manually copies numbers into an Excel spreadsheet or PowerPoint presentation.
4. Cross-references data by eye — no spatial tools, no automated joins.
5. Presents to the Marszałek in a meeting — data is 1–3 days old by the time it's assembled.

**Time cost:** 2–4 hours per regional briefing. Questions asked in meetings get answered "later."

#### Crisis Mode (Active Incident)

When a PM2.5 spike is detected or an industrial fire is reported:

1. Duty officer receives a phone call or spots a citizen report.
2. Officer manually checks the GIOŚ portal in a browser.
3. Officer calls IMGW duty meteorologist to ask about wind direction and expected trajectory.
4. Officer calls school superintendents or individual school principals to issue closure orders — one by one.
5. Officer calls DPS directors to advise sheltering-in-place or assess evacuation needs.
6. Officer calls hospital coordinators to check reception capacity.
7. Officer calls transport operators to request buses.
8. Officer drafts a public alert and sends it through RCB channels.

Each telephone call takes 3–10 minutes. During an industrial fire, toxic concentrations can reach dangerous levels within **30–60 minutes** of ignition. The manual procedure consumes most or all of that window before a single protective action is taken.

---

## 3. The Core Gap — What SENTINEL Provides

### 3.1 Steady-State Gap

The gap in daily operations is the **absence of a spatial, multi-layer, auto-updated view of the voivodeship**. The Marszałek's staff cannot answer "what is the state of my region?" without hours of manual work. Data exists but is not integrated, not spatial, and not queryable.

SENTINEL fills this by providing:
- An interactive GIS map of Lubelskie with powiat/gmina boundaries
- Selectable data layers (healthcare, environment, education, transport, infrastructure)
- Auto-refreshed data from public APIs and scraped sources
- Click-to-filter on any administrative unit
- Resource calculators for ad-hoc queries

### 3.2 Crisis Gap

The gap in crisis response is the **absence of a fused, spatially coherent, time-synchronized operational picture** that answers three questions simultaneously:

1. **Where is the threat going?** (wind + pollutant source → plume trajectory)
2. **Who is in the path?** (plume trajectory → sensitive object overlay → population density)
3. **What can be done right now, with resources available?** (threat zone + sensitive objects → prioritized action list)

SENTINEL fills this by fusing data streams, computing spatial dependencies in real time, and surfacing **recommendations — not raw data — to the decision-maker**.

The operator doesn't need another dashboard with six tabs. He needs one screen that says: *"Wind is from the southwest at 18 km/h. The plume will reach SP nr 4 in 22 minutes at current PM2.5 trajectory. That school has 420 children. The nearest DPS with 142 residents is already within the 200 µg/m³ isopleth. Recommended: immediate shelter-in-place for DPS, preemptive closure order for SP nr 4, alert bus carrier for standby evacuation."*

### 3.3 The Unified Architecture Argument

The steady-state and crisis modes share:
- The same base map (Lubelskie, powiat/gmina boundaries)
- The same facility registries (schools, DPS, hospitals)
- The same data feeds (GIOŚ, IMGW, Airly)
- The same scraping pipeline (BIP, public sources)
- The same UI framework (responsive, large-screen, Polish)

The only difference is the **activation of real-time analysis layers** (plume model, vulnerability scoring, action queue) when a crisis threshold is crossed. This is not two systems — it is one system with an escalation mode.

---

## 4. Stakeholders

### Primary Stakeholders

| Stakeholder | Role | Steady-state need | Crisis need |
|---|---|---|---|
| Marszałek Województwa | Executive sponsor, political accountability | Regional overview on demand | Briefing screen, audit trail for post-incident defense |
| Dyrektor Departamentu (Tomasz) | Daily operator, crisis coordinator | Multi-layer map, data queries, briefing prep | Threat visualization, action recommendations, decision log |
| Duty officer / analyst | Shift-based monitoring | Data feed health, anomaly flagging | Real-time updates, alert generation |

### Secondary Stakeholders

| Stakeholder | Exposure |
|---|---|
| Starostowie (powiat heads) | Receive instructions from voivodeship; need consistent, timely data |
| Wójtowie / burmistrzowie (gmina heads) | Implement local actions based on voivodeship recommendations |
| School directors | Need early warning to execute closure/shelter protocols |
| DPS directors | Need advance notice and transport coordination for vulnerable residents |
| Hospital administrators | Need to prepare for casualty reception or facility protection |
| GIOŚ / IMGW staff | Currently field ad-hoc calls; structured API pull reduces their burden |
| Regional transport operators | Receive late, chaotic mobilization requests; better lead time improves capacity |
| Media and public | Depend on timely, accurate public alerts |

---

## 5. Dependencies Between Data Sets

### 5.1 Wind + Air Quality → Threat Zone Definition

Wind data from IMGW provides direction, speed, and turbulence class. Air quality from GIOŚ and Airly provides current pollutant concentrations at fixed points. Neither source alone produces a threat zone.

The dependency: current concentration at the source, combined with wind vector and atmospheric stability class, allows plume dispersion modeling for a 30–60 minute horizon. Output: a spatially bounded envelope showing where PM2.5 will exceed emergency thresholds.

Without the wind-quality join, an operator sees a high PM2.5 reading at station X but cannot determine whether the hazard is moving toward a school 3 km north or dissipating over an industrial zone 2 km east.

### 5.2 Threat Zone + Sensitive Object Layer → Population at Risk

Once the threat envelope is defined, it must be intersected with spatial locations of schools, DPS, and hospitals. Output: ranked list of at-risk facilities, ordered by (a) time to exceedance, (b) number of vulnerable people, (c) shelter-in-place feasibility vs. evacuation need.

### 5.3 Population Density + Facility Density → Prioritization Weight

A plume moving into a sparsely populated rural buffer zone requires a different response than one moving into Puławy's city center with two schools and a DPS. GUS population density + facility density → a vulnerability index per geographic cell within the threat envelope.

### 5.4 Hospital Capacity + Transport + Evacuation Zone → Feasibility Constraint

1. Threat zone defines which facilities require evacuation vs. shelter-in-place.
2. Facility headcount defines transport demand (bus seats needed).
3. Available transport defines supply.
4. If demand exceeds supply: prioritize by vulnerability index.
5. Hospital capacity constrains whether mass evacuation toward hospitals is safe or will overwhelm emergency medicine.

### 5.5 Temporal Dependency — Time as a Dimension

All chains are time-sensitive. Plume arrival time per facility + facility response time → decision deadline. If closing a school takes 15 minutes after the order is given, and the plume arrives in 18 minutes, the order must be given now.

### 5.6 Steady-State Dependencies (New)

Even outside crisis, dependencies create value:
- Hospital bed occupancy + population density → healthcare coverage gaps
- Air quality trends + school locations → chronic exposure risk areas
- Transport availability + DPS locations → "white spots" where evacuation would be impossible
- BIP-reported infrastructure vs. sensor data → discrepancy detection

---

## 6. Consequences of Missing Visibility

### Crisis Consequences

| Failure mode | Mechanism | Consequence |
|---|---|---|
| Late school closure | Operator didn't know PM2.5 trajectory; called school 25 min after plume arrived | 300–600 children exposed above acute health threshold |
| DPS shelter-in-place not ordered | DPS location not cross-referenced against threat zone | Elderly residents with respiratory conditions exposed; potential fatalities |
| Transport mobilized too late | Availability unknown; 40 minutes spent making calls | Buses arrived after peak exposure |
| Hospital overwhelmed | No advance warning; no visibility into simultaneous demand | ED unable to absorb casualties; triage breakdown |
| Public alert mis-targeted | No spatial model; alert sent to entire voivodeship | Alert fatigue; future alerts ignored |
| Post-incident accountability failure | No timestamped record of what was known and when | Legal and administrative exposure; inability to improve procedures |

### Steady-State Consequences

| Failure mode | Mechanism | Consequence |
|---|---|---|
| Marszałek blindsided in Sejmik session | No prepared regional overview; staff couldn't aggregate data in time | Political embarrassment; loss of credibility |
| Infrastructure problem missed | Gmina BIP report buried in a PDF nobody read | Problem escalates; more expensive to fix later |
| Social media crisis | Citizen reports went viral before official channels noticed | Marszałek appears unaware of his own region |
| Resource misallocation | No visibility into regional capacity patterns | Decisions made on incomplete data; suboptimal budget allocation |

---

## 7. Success Metrics

### 7.1 Steady-State Metrics

| Metric | Target |
|---|---|
| Time to prepare regional briefing for Marszałek | From 2–4 hours to < 5 minutes (dashboard is always ready) |
| Time to answer Marszałek's ad-hoc question in a meeting | From "I'll check later" to < 30 seconds (click-to-filter) |
| Number of data sources integrated in one view | > 8 (vs. 0 today) |
| Data freshness (worst-case source staleness) | < 1 hour for sensor data, < 1 week for registries |

### 7.2 Crisis Metrics

| Metric | Target |
|---|---|
| Time from first PM2.5 alert to first protective action recommendation | < 3 minutes |
| Number of telephone calls required to establish situation picture | Reduced from ~8 to 0 for data gathering |
| Percentage of at-risk facilities identified before plume arrival | > 95% |
| Decision recommendation accuracy | Officer judges recommendation "actionable as-is" |

### 7.3 System Reliability

| Metric | Target |
|---|---|
| Data ingestion latency (GIOŚ/Airly/IMGW to SENTINEL) | < 60 seconds |
| System availability during crisis declaration | > 99.5% |
| AI classification accuracy on event type | > 90% on test set |

---

## 8. Scope Boundaries

| Out of scope | Rationale |
|---|---|
| Automatically issuing formal orders (decyzje) | Legal authority belongs to the Marszałek/Wojewoda; requires separate legal framework |
| Replacing GIOŚ, IMGW, or Airly sensor networks | SENTINEL consumes their data; does not generate measurements |
| Real-time hospital bed management | NFZ clinical systems are regulated; SENTINEL queries a static or periodic proxy |
| Long-range (multi-day) dispersion forecasting | Problem is acute response, 0–6 hour horizon |
| Multi-voivodeship coordination | Primary scope is Lubelskie; expansion is a future extension |
| Replacing the operator's judgment | SENTINEL produces recommendations, not orders |

---

## Summary

SENTINEL solves **two expressions of the same underlying problem: the fragmentation of voivodeship operational data across disconnected systems**.

In steady-state, this fragmentation makes the Marszałek's staff blind to the current state of their own region — unable to answer basic questions without hours of manual work, unable to detect problems until they escalate, unable to brief leadership with confidence.

In crisis, the same fragmentation forces manual assembly of a situational picture under acute time pressure, producing delayed and potentially incomplete protective actions.

SENTINEL is one system that addresses both modes: a GIS-based, multi-layer, auto-updated decision dashboard for Województwo Lubelskie that seamlessly escalates from governance overview to crisis command screen when conditions demand it. The value is not in new sensors or algorithms — it is in the **integration layer** that connects existing data sources, computes their spatial and temporal dependencies, and surfaces actionable intelligence to the people who need it.
