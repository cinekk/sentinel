# Problem Definition: SENTINEL — AI Situational Awareness Platform

**Version:** 1.0  
**Date:** 2026-04-11  
**Scenario:** ZESTAW D — Environmental Failure (Smog / Industrial Fire)  
**Context:** Polish voivodeship crisis management, Civil42 Hackathon

---

## 1. Problem Statement

During an acute environmental crisis — such as an industrial fire producing toxic smoke — a voivodeship crisis management officer in Poland has no single operational view that integrates air quality readings, real-time wind vectors, the locations of sensitive facilities (schools, care homes, hospitals), available transport assets, and population density into an actionable threat picture. Information is locked in six or more disconnected agency systems, accessible only by telephone. The officer must synthesize this picture manually, under acute time pressure, while simultaneously coordinating response. The result is delayed, inconsistent, and potentially life-threatening decisions.

---

## 2. Current State — The Information Landscape

### 2.1 Institutional Structure

Poland operates 16 voivodeships. Each Voivode heads a **Wydział Zarządzania Kryzysowego** (Crisis Management Cell), which is the operational nerve center during regional emergencies. The cell is staffed around the clock but is small — typically 5–15 officers depending on the voivodeship. The cell does not own the data it needs; it has authority over agencies that own it.

### 2.2 Data Fragmentation — Where the Numbers Live

| Data type | Custodian | Access method |
|---|---|---|
| Air quality (PM2.5, PM10, NO₂, SO₂) | GIOŚ | Public API, but no real-time alerting to crisis cells |
| Hyper-local particulate sensors | Airly (commercial) | Separate API, separate account, different data model |
| Wind speed, direction, precipitation, temperature | IMGW | Forecast API; no integration with pollution plume modeling |
| School locations and enrollment | RSPO (Schools Register) | Static registry; no real-time operational status |
| Care home (DPS) locations and resident counts | MRIPS | Static registry; updated annually |
| Hospital locations, capacity, bed counts | NFZ / MZ registries | Not real-time; capacity changes throughout the day |
| Road transport availability | GUS/REGON, carrier contracts | No live visibility; must be sourced by phone |
| Population density by area | GUS census data | Static; not event-aware |

### 2.3 The Current Operational Procedure

When a PM2.5 spike is detected or an industrial fire is reported, the procedure in practice is:

1. An officer receives a phone call or spots a citizen report.
2. Officer manually checks the GIOŚ portal in a browser.
3. Officer calls IMGW duty meteorologist to ask about wind direction and expected trajectory.
4. Officer calls local sanepid for health guidance thresholds.
5. Officer calls school superintendents or individual school principals to issue closure orders — one by one.
6. Officer calls DPS directors to advise sheltering-in-place or assess evacuation needs.
7. Officer calls hospital coordinators to check reception capacity.
8. Officer calls the regional transport authority or carrier companies to request buses.
9. Officer drafts a public alert and sends it through separate RCB channels.

Each telephone call takes 3–10 minutes. During an industrial fire, toxic concentrations can reach dangerous levels within **30–60 minutes** of ignition. The manual procedure consumes most or all of that window before a single protective action is taken.

---

## 3. The Core Gap — What SENTINEL Provides

The gap is not a shortage of data. The data exists. The gap is **the absence of a fused, spatially coherent, time-synchronized operational picture** that answers three questions simultaneously:

1. **Where is the threat going?** (wind + pollutant source → plume trajectory)
2. **Who is in the path?** (plume trajectory → sensitive object overlay → population density)
3. **What can be done right now, with resources available?** (threat zone + sensitive objects → prioritized action list)

SENTINEL is the integration layer that fuses these streams, computes the spatial dependencies between them in real time, and surfaces **recommendations — not data — to the decision-maker**.

The colonel does not need another dashboard with six tabs. He needs one screen that says: *"Wind is from the southwest at 18 km/h. The plume will reach SP-14 primary school in 22 minutes at current PM2.5 trajectory. That school has 340 children. The nearest DPS with 87 residents is already within the 200 µg/m³ isopleth. Recommended: immediate shelter-in-place for DPS, preemptive closure order for SP-14, alert bus carrier #3 for standby evacuation."*

---

## 4. Stakeholders Affected

### Primary Stakeholders

| Stakeholder | Role | Pain point |
|---|---|---|
| Voivodeship Crisis Management Officer (colonel / naczelnik) | Authorizes protective actions | No integrated situational picture; all synthesis is manual |
| Crisis cell duty officer | Monitors situation 24/7, first responder on shift | Switches between 6+ browser tabs and phone; high cognitive load |
| Local government (mayor / starosta) | Implements orders in their territory | Receives conflicting or delayed information from the voivodeship |

### Secondary Stakeholders

| Stakeholder | Exposure |
|---|---|
| School children and staff | Delayed closure = exposure to toxic concentrations |
| Care home residents (DPS) | Elderly, often mobility-impaired; late decisions are dangerous |
| Hospital patients and staff | May need to receive casualties while themselves in the threat zone |
| General public in the plume corridor | Depends on quality and timeliness of public alert |
| GIOŚ / IMGW staff | Currently field ad-hoc calls from crisis cells; structured API pull reduces their burden |
| Regional transport operators | Receive late, chaotic mobilization requests; better lead time improves response capacity |

---

## 5. Dependencies Between Data Sets

### 5.1 Wind + Air Quality → Threat Zone Definition

Wind data from IMGW provides **direction, speed, and turbulence class**. Air quality data from GIOŚ and Airly provides **current pollutant concentrations at fixed points**. Neither source alone produces a threat zone.

The dependency: current concentration at the source point, combined with wind vector and atmospheric stability class, allows plume dispersion modeling sufficient for a 30–60 minute horizon. The output is a **spatially bounded envelope** showing where PM2.5 will exceed WHO emergency thresholds.

Without the wind-quality join, an officer sees a high PM2.5 reading at station X but cannot determine whether the hazard is moving toward a school 3 km north or dissipating over an industrial zone 2 km east.

### 5.2 Threat Zone + Sensitive Object Layer → Population at Risk

Once the threat envelope is defined, it must be intersected with the spatial locations of schools, DPS care homes, and hospitals. The dependency: threat zone geometry + object coordinates → ranked list of at-risk facilities, ordered by: (a) time to exceedance, (b) number of vulnerable people, (c) shelter-in-place feasibility vs. evacuation need.

A school 800 meters downwind at 20 km/h will be reached in approximately 2.4 minutes. A DPS 3 km downwind will be reached in 9 minutes. The prioritization order is a function of the intersection — not of any single dataset.

### 5.3 Population Density + Sensitive Object Density → Prioritization Weight

A plume moving into a sparsely populated industrial buffer zone requires a different response than one moving into a dense residential area with two schools and a DPS. GUS population density + RSPO/MRIPS facility density → a **vulnerability index** per geographic cell within the threat envelope. This index weights the urgency of public alert, the scale of transport mobilization needed, and whether point evacuation or area shelter-in-place is the more protective action.

### 5.4 Hospital Capacity + Transport Availability + Evacuation Zone → Feasibility Constraint

The dependency chain:

1. Threat zone defines which DPS/schools require evacuation vs. shelter-in-place.
2. Each facility's resident/student count defines **transport demand** (bus seats needed).
3. Available transport contracts define **supply**.
4. If demand exceeds supply: the system must prioritize which facilities to evacuate first (highest vulnerability index).
5. Hospital capacity defines how many symptomatic individuals can be absorbed — constraining whether mass evacuation toward urban hospitals is safe or will overwhelm emergency medicine.

Breaking any link in this chain forces the officer to decide on evacuation without knowing whether the buses exist to execute it.

### 5.5 Temporal Dependency — Time as a Dimension Across All Chains

All chains are **time-sensitive**. The dependency: plume arrival time per facility + facility response time (how long to execute closure or evacuation) → **decision deadline**. If closing a school takes 15 minutes after the order is given, and the plume arrives in 18 minutes, the order must be given now. If the plume arrives in 40 minutes, there is a 25-minute window.

Without temporal modeling, every decision feels equally urgent — which means none feel tractable. With it, the officer sees a sequenced action queue with explicit deadlines.

---

## 6. The "So What" — Consequences of Missing Visibility

| Failure mode | Mechanism | Consequence |
|---|---|---|
| Late school closure | Officer did not know PM2.5 trajectory; called school 25 minutes after plume arrived | 300–600 children exposed to concentrations above acute health threshold |
| DPS shelter-in-place not ordered | DPS location not cross-referenced against threat zone | Elderly residents with respiratory conditions exposed; potential fatalities |
| Transport mobilized too late | Transport availability not known; officer spent 40 minutes making calls | Buses arrived after peak exposure; evacuation could not proceed |
| Hospital overwhelmed | No advance warning; no visibility into simultaneous demand from multiple facilities | Emergency departments unable to absorb symptomatic cases; triage breakdown |
| Public alert mis-targeted | No spatial model of threat zone; alert sent to entire voivodeship | Alert fatigue; future alerts ignored; unnecessary economic disruption |
| Missed PM2.5 peak at unmeasured location | Relying only on GIOŚ fixed stations; no interpolation from Airly sensors | Hazardous conditions in residential area not detected until symptomatic reports |
| Post-incident accountability failure | No timestamped record of what the officer knew and when | Legal and administrative exposure; inability to improve procedures |

The worst-case scenario is not just a health outcome. It is a preventable mass casualty event in a care home, followed by a parliamentary inquiry, in which the investigation reveals that all the data needed to act was available in real time — just not fused into a usable picture.

---

## 7. Success Metrics — How Would the Colonel Know the System Is Working?

### 7.1 Operational Metrics

| Metric | Target | Measurement |
|---|---|---|
| Time from first PM2.5 alert to first protective action recommendation | < 3 minutes | Timestamp in SENTINEL event log |
| Number of telephone calls required to establish situation picture | Reduced from ~8 to 0 for data gathering | Officer self-report; call log review |
| Percentage of at-risk facilities identified before plume arrival | > 95% | Post-event comparison of SENTINEL output vs. actual plume footprint |
| Decision recommendation accuracy | Officer judges recommendation "actionable as-is" | Post-incident review survey |

### 7.2 Outcome Metrics

| Metric | Target |
|---|---|
| Mean time between pollution event onset and protective action order issued | Reduction of > 50% vs. baseline (manual procedure) |
| Number of facilities that received advance warning before exceedance | All facilities within modeled threat zone |
| Post-event documentation completeness | Full timestamped log of sensor readings, AI recommendations, and officer decisions — exportable for after-action review |

### 7.3 System Reliability Metrics

| Metric | Target |
|---|---|
| Data ingestion latency (GIOŚ/Airly/IMGW to SENTINEL) | < 60 seconds |
| System availability during crisis declaration period | > 99.5% |
| AI classification accuracy on crisis event type | > 90% on test set of historical incidents |

---

## 8. Scope Boundaries — What This Problem Is NOT

| Out of scope | Rationale |
|---|---|
| Automatically placing telephone calls or sending orders to agencies | Legal authority to issue orders belongs to the Voivode; automation of official orders requires a separate legal framework |
| Replacing GIOŚ, IMGW, or Airly sensor networks | SENTINEL consumes their data; it does not generate new physical measurements |
| Real-time hospital bed management | NFZ clinical systems are regulated and complex; SENTINEL queries a static or periodically updated proxy |
| Long-range (multi-day) dispersion forecasting | The problem is acute crisis response, 0–6 hour horizon; long-range modeling is a different problem |
| National-level coordination across multiple voivodeships | Primary user is the single voivodeship cell; multi-voivodeship coordination is a future extension |
| Replacing the crisis management officer's judgment | SENTINEL produces recommendations, not orders. The officer decides. The system's job is to ensure the officer decides with full situational awareness in the minimum possible time. |

---

## Summary

The problem SENTINEL solves is **the fragmentation of crisis-relevant data across disconnected agency systems, which forces crisis management officers to manually assemble a situational picture under acute time pressure, producing delayed and potentially incomplete protective actions**.

The scenario of an industrial fire or severe smog event is a precise and tractable test case: the data is available, the dependencies between datasets are well-defined, the decision space (close / shelter / evacuate / alert) is bounded, and the time horizon is short enough that the difference between a 3-minute and a 30-minute situational picture is measurable in health outcomes.

SENTINEL's value is not in the sensors or the APIs. It is in the **inference layer** that connects them — the spatial join, the temporal modeling, the vulnerability weighting — and in surfacing that inference as an actionable, time-sequenced recommendation to the one person who has the authority and the obligation to act.
