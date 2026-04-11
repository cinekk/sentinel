# SENTINEL Case Study: Industrial Fire and Air Quality Crisis — Lubelskie Voivodship

**ZESTAW D — Environmental Failure: Industrial Fire / Smog Event**  
**Classification: EXERCISE / TRAINING SCENARIO**  
**Prepared for:** Civil42 Hackathon, 11–12.04.2026

---

## Executive Summary

On 11 April 2026, a fire broke out in a warehouse storing industrial solvents and agricultural chemicals at the logistics terminal adjacent to Zakłady Azotowe Puławy S.A. Within 90 minutes, PM2.5 at the nearest GIOŚ station (Puławy-Centrum) exceeded 340 µg/m³ — 23x the WHO 24h guideline. A north-northwest wind at 18 km/h drove the plume directly toward a corridor containing three primary schools, a DPS care home, and the District Hospital in Puławy — all within 6 km of the fire origin.

SENTINEL integrated real-time GIOŚ, Airly, and IMGW data with a facility registry to generate a quantified plume projection and ranked action list within 4 minutes of alert. Crisis managers acting without SENTINEL spent 47 minutes in phone-based coordination before arriving at incomplete situational awareness.

---

## 1. Scenario Setup

**Incident location:** Logistics terminal at ul. Centralny Okrag Przemyslowy 14, Puławy (51.4163°N, 21.9688°E) — a 2.4-hectare warehouse on the southern edge of the Zakłady Azotowe Puławy industrial zone, storing Class 3 flammable liquids (acetone, methanol, toluene) and Class 8 corrosive materials.

**Weather (IMGW Station Puławy, 07:00 UTC):** Wind NNW 340° at 18 km/h (gusts 28 km/h), temperature 6°C, humidity 72%, mixing layer height 680 m (low — poor vertical dispersion), no precipitation expected until 16:00.

**Sensitive objects in plume corridor:**

| Object | Type | Distance | Population |
|---|---|---|---|
| SP nr 4 im. Bednarskiego (ul. Norwida 10) | Primary school | 1.2 km NNE | 420 students |
| DPS Puławy (ul. Leśna 7) | Care home (elderly) | 2.4 km NNE | 142 residents |
| PM nr 11 (ul. Lubelska 12) | Kindergarten | 1.8 km NNE | 90 children |
| SP nr 7 im. Kazimierza Wielkiego (ul. Piłsudskiego 28) | Primary school | 2.1 km NE | 380 students |
| SPZOZ Puławy (al. Jana Pawła II 10) | District hospital | 3.1 km NNE | 280 beds, 58 critical |
| LO im. Czartoryskiego (ul. Czartoryskich 5) | Secondary school | 3.4 km NE | 780 students |

---

## 2. Timeline: T+0 to T+4 Hours

**T+0 / 07:23** — Fire ignition. Forklift spark ignites acetone drum rack in Warehouse 3B. On-site suppression fails. PSP Puławy dispatched.

**T+12 / 07:35** — Roof collapse. Dense smoke column visible 40 km away. PM2.5 at GIOŚ Puławy-Centrum: 187 µg/m³ (was 12 µg/m³ at 07:00). GIOŚ Puławy-Azoty (400 m from fire): PM2.5 412 µg/m³, PM10 680 µg/m³.

**T+18 / 07:41 — SENTINEL alert generated** (4 min 12 sec processing time):
- Detects PM2.5 spike >3 standard deviations, sustained 5+ min at two adjacent sensors
- Gaussian plume model run using IMGW wind vector + mixing layer height
- Sensitive objects overlaid from TERYT/RSPO/MZ registries
- Claude AI generates ranked action list

SENTINEL output: DPS Puławy will reach PM2.5 >200 µg/m³ in est. 22 min; SP nr 4 in 18 min; hospital in 45 min. 6 MPK buses (360 capacity) available; evacuation would take multiple runs and more time than the shelter window. Recommendation: shelter-in-place schools and DPS immediately, seal hospital HVAC, pre-stage ALS ambulances outside plume.

**T+22 / 07:45** — Colonel Wiśniewski reviews SENTINEL dashboard: live plume cone on map, PM2.5 time series with 1-hour projection, color-coded sensitive object pins, resource panel showing bus availability and hospital bed counts. Issues three decisions in 6 minutes.

**T+28 / 07:51** — SP nr 4 shelter-in-place: 420 children moved to interior corridors, HVAC closed.

**T+35 / 07:58** — DPS Puławy protocol activated: 142 residents to central building, ventilation to recirculation, 27 respiratory-risk residents given supplemental O2. One ALS ambulance pre-staged at ul. Dęblińska (upwind), ready for the 14 DPS residents requiring medical-grade transport.

**T+42 / 08:05** — SENTINEL detects 08:00 IMGW NWP run shows wind backing to NW by 09:30, not 10:00 as previously forecast. Plume shifts 20° east. LO Czartoryskiego (780 students) now enters HIGH risk zone 35 min earlier than initial projection. SENTINEL auto-generates supplementary alert.

**T+42 / 08:05** — RCB text alert issued to Puławy residents (postal codes 08-400/403/404).

**T+50 / 08:13** — LO Czartoryskiego shelter-in-place ordered. Students remain in classrooms; outdoor break cancelled. PM2.5 at PuL001: 341 µg/m³ (peak).

**T+75 / 08:38** — Fire partially contained. SO2 release detected from sulfuric acid precursor barrels. SENTINEL expands hazard model; SPZOZ hospital activates CBRN air-intake protocol.

**T+150 / 09:53** — PM2.5 at PuL001: 67 µg/m³. Schools reopen interior circulation; outdoor activity restricted.

**T+240 / 11:23** — Fire extinguished. SENTINEL switches to post-incident monitoring mode. Zero injuries among protected populations.

---

## 3. Data Dependencies in Action

**Wind data → plume prediction:** SENTINEL consumed IMGW SYNOP at 10-minute intervals plus successive NWP model runs. The critical value was mixing layer height (680 m) — a low mixing layer concentrates pollutants near ground, amplifying PM2.5 concentrations by a factor of 3–5 compared to well-mixed conditions. Without this parameter, the plume severity would have been significantly underestimated.

**Wind forecast update → secondary school alert:** The difference between 780 students being warned (T+50) versus exposed during outdoor break (T+75) was SENTINEL automatically comparing the 08:00 NWP run to the 07:00 run, detecting the 30-minute wind shift acceleration. No manual workflow in current WCZK operating procedures would have triggered this comparison during an active incident.

**Hospital bed counts → do-not-evacuate decision:** SPZOZ Puławy peak exposure estimated at <200 µg/m³; building suitable for HVAC recirculation; 58 critical patients; nearest ICU alternative 43 km away (Lublin, 8 ICU beds available). SENTINEL made this risk-benefit calculation explicit at T+22. In the manual scenario, this formal decision was never made.

**Transport capacity → evacuation ruled out:** 6 buses (360 capacity) vs. 890 children across three sites requiring multiple runs. Each run longer than the available shelter window. SENTINEL's recommendation engine had simultaneous access to PM2.5 rise rate, bus availability, loading time estimates, and building shelter effectiveness. The correct shelter-in-place decision emerged from data, not default.

**DPS resident medical classification → ambulance staging:** 14 of 142 DPS residents flagged as requiring ALS transport (from pre-loaded resident registry). This drove pre-staging of one ALS unit at T+35 — available in 8 minutes if evacuation ordered. In the manual scenario, this information would have required a 10–15 minute conversation with the DPS director during the crisis.

---

## 4. Without SENTINEL vs. With SENTINEL

**Without SENTINEL (reconstructed from standard WCZK procedures):**

- T+31: GIOŚ portal accessed; shows data from 07:30 (10-min lag). PM2.5 95 µg/m³ visible — still rising but officer doesn't know the rate.
- T+30: Deputy mayor reached by phone. Doesn't know which schools are downwind — has no wind data.
- T+46: School district coordinator begins calling principals. SP nr 4 reached at T+46 — children have breathed PM2.5 >200 µg/m³ in open corridors for 17 minutes.
- T+54: DPS director reached by main reception.
- T+119: RCB alert sent — governor authorization took 25 minutes beyond the request. Alert is 100 minutes late.
- T+42: LO Czartoryskiego never warned. Wind shift never detected. 780 students take outdoor break at T+42 in PM2.5 ~220 µg/m³.
- Hospital: Never formally assessed. No decision made.
- Ambulances: Not pre-staged. Would require 20 min response if DPS evacuation ordered.

**With SENTINEL:**

One screen replaced 14 separate phone calls, three browser windows, and a paper map. Left panel: live plume cone on Usemaps map, updated every 5 minutes. Center: three PM2.5 time series with WHO/Polish threshold lines and 1-hour projections. Right: Claude-generated action list with object name, address, headcount, estimated time window, required resource. Bottom: bus count, ambulance positions, hospital bed capacity. Automatic alert on NWP forecast change.

---

## 5. Key Decisions — Data That Drove Each

| Decision | SENTINEL time | Manual time | Gap |
|---|---|---|---|
| SP nr 4 shelter-in-place | T+28 (07:51) | T+86 (08:49) | 58 min |
| DPS Puławy shelter-in-place | T+35 (07:58) | T+54 (08:17) | 19 min |
| Hospital: do not evacuate | T+22 (07:45) | Never made | Structural gap |
| ALS ambulances pre-staged | T+35 (07:58) | Not done | Preparedness |
| LO Czartoryskiego warned | T+50 (08:13) | Never | Critical near-miss |
| RCB public alert | T+42 (08:05) | T+142 (09:45) | 100 min |

---

## 6. Outcome and Lessons

**Results:** 0 injuries among 1,814 people in sensitive objects. LO Czartoryskiego near-miss prevented by automated wind forecast monitoring. Hospital not evacuated (correct — shelter-in-place was adequate, avoided transport risk for 58 critical patients). All 142 DPS residents accounted for.

**Key findings:**

1. **Wind forecast updates during active incidents are structurally invisible in manual operations.** No WCZK protocol triggers a duty officer to monitor successive NWP runs for changes affecting an ongoing incident. SENTINEL's continuous consumption of IMGW API data and automatic comparison of forecast runs is the only mechanism that caught the plume shift to LO Czartoryskiego.

2. **PM2.5 rise rate is the actionable variable, not the current reading.** At T+12 the value (187 µg/m³) could be read as "elevated but not at threshold." The rate (+28 µg/m³/5 min) implied DPS would exceed 200 µg/m³ in 22 minutes — before any manual notification chain could complete.

3. **Transport/capacity constraints must be computed against plume timing, not assessed separately.** The shelter-in-place decision for schools was correct but needed to be made with knowledge that evacuation was infeasible given bus capacity, headcount, and the time window. SENTINEL made this explicit; the manual scenario arrived at the same outcome by default.

4. **The "do nothing" decision about the hospital needed to be made explicitly.** SENTINEL forced a formal assessment at T+22. If conditions had worsened, the manual scenario had no mechanism to bring the hospital into the response before it was too late.

5. **Pre-loaded registries with vulnerability classification are the rate-limiting factor.** Every location-specific SENTINEL recommendation depended on the pre-loaded facility database (TERYT, RSPO, MZ bed registry, DPS resident medical classification). Stale or incomplete registry data directly degrades recommendation quality. This is a data governance problem, not a technical one.

---

*End of Case Study — SENTINEL, ZESTAW D: Environmental Failure / Industrial Fire*  
*Version 1.0 | 2026-04-11 | Classification: EXERCISE / TRAINING*
