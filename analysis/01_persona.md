# Persona: Primary User of SENTINEL

## Marek Wiśniewski, Colonel (ret.) — Head of Crisis Management Division

---

### 1. Identity

| Field | Detail |
|---|---|
| Name | płk. Marek Wiśniewski (ret.) |
| Age | 54 |
| Title | Naczelnik Wydziału Zarządzania Kryzysowego, Mazowiecki Urząd Wojewódzki |
| Role | Head of Crisis Management Division, Masovian Voivodship |
| Location | Warsaw (Mazowieckie), area of responsibility: 5.2 million inhabitants, 38 counties, 314 municipalities |
| Background | 28 years in the Polish Armed Forces (engineering and logistics). Transitioned to civilian crisis management after retirement. 6 years in current role. |
| Education | Military University of Technology (WAT), postgraduate in Civil Security Management (SGSP) |

---

### 2. Goals and Motivations

Success is a crisis that never became a catastrophe. He measures this by whether his decisions — evacuation orders, resource deployments, public warnings — were issued early enough, to the right people, covering the right geographic scope.

He is appointed by the Voivode and legally accountable under the Ustawa o zarządzaniu kryzysowym. He is not a politician; his name goes on the orders.

**Core motivations:**
- Protect life first — specifically the populations that cannot protect themselves: children in schools, residents of care homes (DPS), patients in hospitals.
- Avoid over-reaction as much as under-reaction. A false alarm that shuts down 40 schools damages credibility with county heads and costs political capital he needs for real emergencies.
- Maintain command coherence. Multiple agencies operate simultaneously (PSP, police, medical rescue, municipalities). His job is to ensure they are not working from different pictures of reality.
- Be defensible. Every decision must be documented. If questioned later — by parliament, media, or a court — he must show the information he had, when he had it, and why he decided as he did.

---

### 3. Daily Responsibilities

**Steady-state:**
- Maintains the Voivodship Crisis Management Plan (updated annually, legally required).
- Oversees preparedness exercises with PSP, police, RCB, and county-level crisis teams.
- Reviews daily IMGW weather alerts and GIOŚ air quality bulletins.
- Coordinates with infrastructure operators on dependency mapping.
- Chairs monthly meetings of the Wojewódzki Zespół Zarządzania Kryzysowego.

**During active crisis (smog/industrial fire):**
- Convenes the crisis team in the operations room.
- Receives situation reports from PSP Incident Commander and county coordinators.
- Issues formal decisions (decyzje) and recommendations (zalecenia) to mayors and county heads.
- Coordinates resource requests exceeding county capacity.
- Communicates with RCB if escalation thresholds are met.
- Approves public warnings via regional alert system (RCB-Alert SMS, sirens).

---

### 4. Pain Points with the Current Situation

**Fragmented data, manual aggregation.** GIOŚ publishes PM2.5/PM10 on one website. IMGW is a separate portal. Hospital bed counts require calling the NFZ Mazovian Branch. Each source needs a different login, a different URL, a different person.

**No spatial integration.** He can look at an air quality map and a map of schools — in two separate browser tabs. There is no single view that says: "These 12 schools and 3 care homes are inside the contamination zone defined by current wind and PM10 readings."

**Latency.** By the time data is collected, manually cross-referenced, and presented to him, 45–90 minutes have passed. In a fast-moving industrial fire with shifting wind, that lag is the difference between an ordered evacuation and a chaotic one.

**No dependency mapping.** He knows the hospitals in the voivodship. He does not have a queryable picture of: which hospital has ICU capacity right now; which road routes to that hospital pass through the contamination zone; which transport operators have available buses.

**Situational awareness is person-dependent.** His best analyst knows how to pull all these sources together — but that knowledge lives in a person's head, not in a system.

**No audit trail in the tool.** Decisions are logged in separate Word documents or printed forms. No software timeline records: at 14:23 PM10 at station X crossed threshold Y; at 14:31 the team was notified; at 14:47 the school closure recommendation was issued.

---

### 5. Key Questions During a Smog / Industrial Fire Event

These are the literal questions he asks out loud, in order of priority:

1. "Where exactly is the contamination?" — What is the current perimeter? What will it look like in 2 hours given the wind forecast?
2. "What's inside the zone?" — How many schools, kindergartens, care homes, hospitals? How many people?
3. "How bad is the air?" — PM2.5/PM10 readings from nearest GIOŚ stations? Are we above WHO thresholds, Polish legal thresholds, or levels that trigger mandatory PSP response?
4. "What do hospitals have?" — Available beds in the affected and adjacent reception zone? ICU capacity?
5. "Can we move people?" — What transport assets are available? How long to deploy? Who owns them?
6. "What are we moving or protecting besides people?" — Cultural assets (museum collections, archives), livestock, hazardous materials that could compound the event.
7. "Who has already been notified?" — Have mayors and county heads received formal notification? Have schools been contacted?
8. "What's the weather doing in the next 6 hours?" — Will the zone expand, contract, or shift?
9. "Is this escalating to national level?" — Does this meet the threshold to notify RCB?

---

### 6. What "Visibility" Means Concretely

Marek uses "widoczność sytuacji" to mean one specific thing: **a single authoritative picture that everyone in the room is looking at simultaneously, updated automatically, without requiring a person to compile it.**

**Map layer (primary view):**
- Contamination zone polygon, auto-updated as wind/readings change, with 1-hour and 3-hour forecast overlays.
- Color-coded sensitive objects within and adjacent to the zone: schools (red), care homes (orange), hospitals (blue), critical infrastructure (yellow).
- Population density heatmap clipped to the zone.
- Available transport assets as icons with capacity labels.
- Road network with route viability indicators.

**Panel: Air quality — live readings**
- PM2.5 and PM10 from GIOŚ stations, with threshold indicators (green/amber/red) and trend arrows.
- Airly sensor readings to fill gaps between GIOŚ stations.
- IMGW wind speed, direction, precipitation — current and +3h.

**Panel: Sensitive objects summary (tabular)**
- Schools: address, pupil count, head teacher contact.
- Care homes: resident count, mobility status.
- Hospitals: available bed count (NFZ data), distance from zone center.

**Panel: Resources**
- Ambulances and current location.
- PSP HAZMAT units — status (free / committed / en route).
- Transport companies in the voivodship logistics registry: vehicle count, capacity, contact.

**Panel: Timeline / audit log**
- Chronological log: sensor reading → notification → decision → acknowledgment. Timestamps on everything.
- Doubles as post-incident documentation.

**What he does NOT want:**
- Raw data tables without spatial context.
- Dashboards requiring multiple tabs.
- Any widget requiring him to understand how it works before trusting it.
- Alerts without a clear recommended action.

---

### 7. Decision-Making Patterns

**T+0:** GIOŚ or PSP notification arrives. Duty officer activated. No public action yet.

**T+15–30 min:** First internal assessment. Team maps the zone and identifies sensitive objects. This is where the current 45-minute manual lag creates maximum pain.

**T+30–60 min:** Tiered recommendation:
- Level 1 (advisory): Notify mayors and county heads. No mandatory action.
- Level 2 (precautionary): Recommend school closures, restrict outdoor activities for DPS residents.
- Level 3 (directive): Order evacuation of specific facilities. Requires signed decyzja.

**Who he calls, in order:**
1. PSP Komenda Wojewódzka duty officer — situation at the source.
2. County heads (starostowie) in the affected area.
3. NFZ Mazovian Branch — hospital capacity check.
4. RCB — if escalation threshold is reached.
5. Voivode — briefing, not asking permission.
6. Regional media coordinator — if level 2 or above.

**Decision style:** Not a consensus-seeker in a crisis. Collects information fast, decides on available data, issues clear directives. Expects acknowledgment. Will change a decision if new data arrives, but will not wait for consensus before issuing the first one.

**National escalation triggers:** Event affecting more than one voivodship; PM10 sustained above 500 µg/m³ at multiple stations; confirmed fatalities; mass evacuation (>500 persons).

---

### 8. Technology Comfort Level and Constraints

**Comfort: Moderate-high within specific domains.** Competent with GIS-adjacent tools (ARCGIS-based voivodship planning systems). Fluent with Teams, Outlook, Word, Excel. Has used SZAFIR but found it poorly adapted to real-time decision-making. Not a developer.

**Hard constraints:**
- Must work on the government network in the operations room (security-restricted). Cloud tools need IT approval or local/intranet deployment.
- Must be readable on a 55" display shared by multiple people in the room.
- Must be readable by a 54-year-old under stress. He wears reading glasses. Tiny dense tables are a problem.
- Polish-language labels — he will not decode English terminology under pressure.
- No login friction during a crisis — accessible within 10 seconds.

**What he distrusts:**
- AI recommendations without a visible data source.
- Systems that fail silently — he must know immediately when a feed goes down.
- Dashboards that look impressive but cannot answer his specific questions.

---

### 9. Perfect Tool vs. Today's Reality

**What a perfect tool gives him:**

- One screen. One picture. Updated automatically. No compilation required.
- Contamination zone on a map with wind forecast baked in.
- Every school, care home, and hospital in the zone listed — with phone numbers, capacity, and status.
- Resource panel showing available transport and its distance from the zone.
- Timeline that is simultaneously his situational record and post-incident audit log.
- Recommendations that cite their sources: "Recommend school closure based on PM10 = 380 µg/m³ at station Warszawa-Ursynów (15 min ago), zone overlap with 14 schools, wind direction NE at 18 km/h."
- Dependency view: "Hospital X is in the zone; evacuation route via DK7 is also in the zone; alternative route via S8 is clear."

**What frustrates him today:**

- Being handed a printout during a crisis — any printout is already 20 minutes old.
- Calling the NFZ to ask about bed counts while managing an active event.
- Analysts spending the first hour of a crisis building a spreadsheet instead of advising him.
- Weather data without spatial context — a wind speed number means nothing without knowing where it pushes the contamination.
- After the crisis: spending days reconstructing the timeline from emails and hand-written notes for the after-action report.

**The one sentence that describes what he wants:**

> "I need to walk into the room, look at one screen, and in 90 seconds know: what is happening, where, how bad, and what I can do about it."

---

### Design Implications for SENTINEL

| Marek's Need | SENTINEL Feature Requirement |
|---|---|
| Zone visualization with forecast | Contamination polygon layer with IMGW wind integration and time-step projection |
| Sensitive objects in zone | Spatial join of GIOŚ readings with POI database (schools, DPS, hospitals) |
| Hospital capacity | Live or near-live NFZ bed data feed, fallback to last-known |
| Transport resources | Logistics registry integration with operator contact and vehicle capacity |
| Threshold-based alerts | PM2.5/PM10 thresholds triggering automatic zone assessment and notification drafts |
| Audit trail | Append-only event log with actor, timestamp, data snapshot |
| Source transparency | Every AI recommendation exposes the data inputs that produced it |
| Offline / intranet mode | API-first architecture with local deployment option |
| Large screen readability | High-contrast tactical UI, minimum 16px labels, color-coded severity |
| Polish UX | All labels and recommendations in Polish |
