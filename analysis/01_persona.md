# Persona: Users of SENTINEL — Inteligentna Mapa Województwa Lubelskiego

## Two-Level User Model

SENTINEL serves two distinct users with different needs, rhythms, and decision scopes. The system must satisfy both — but only one is in front of the screen daily.

---

## A. Executive Sponsor: Marszałek Województwa Lubelskiego

### Identity

| Field | Detail |
|---|---|
| Title | Marszałek Województwa Lubelskiego |
| Role | Elected head of regional self-government (samorząd województwa) |
| Responsibility | Strategic management of voivodeship: budget, infrastructure, healthcare, culture, transport, EU funds, crisis coordination |
| Area | 25,155 km², 213 gmin, 20 powiatów, 4 miasta na prawach powiatu, ~2.1 mln mieszkańców |
| Seat | Urząd Marszałkowski, ul. Artura Grottgera 4, 20-029 Lublin |

### Relationship to the System

The Marszałek does not operate SENTINEL daily. He has better things to do — managing a region, attending sessions of the Sejmik, negotiating EU funding, visiting municipalities.

What the Marszałek needs from SENTINEL:

- **Briefing mode:** Walk into the conference room, glance at the big screen, understand the current state of the voivodeship in 60 seconds. "Is anything on fire — literally or figuratively?"
- **Crisis escalation:** When a serious event occurs, the Marszałek is briefed by the operator. SENTINEL is the single screen the operator shows him. It must be immediately legible — no explanation needed.
- **Political accountability:** After an incident, the Marszałek faces the Sejmik, media, and public. SENTINEL's audit log and timeline become his defense: "We knew at 07:41, we acted at 07:45, here is the data that drove the decision."
- **Showcase value:** The Marszałek wants to demonstrate that Lubelskie is digitally advanced, data-driven, modern. A working decision dashboard is a political asset during visits, inspections, and press events.

**The Marszałek evaluates SENTINEL on one criterion:** *"Does this make me look like I'm in control of my region?"*

---

## B. Primary Operator: Dyrektor Departamentu — Tomasz Kowalczyk

### 1. Identity

| Field | Detail |
|---|---|
| Name | Tomasz Kowalczyk |
| Age | 46 |
| Title | Dyrektor Departamentu Bezpieczeństwa i Zarządzania Kryzysowego, Urząd Marszałkowski Województwa Lubelskiego |
| Role | Head of the Security and Crisis Management Department — the Marszałek's trusted operator for all matters involving regional safety, emergency coordination, and situational awareness |
| Location | Lublin; area of responsibility covers entire Lubelskie voivodeship |
| Background | 12 years in Państwowa Straż Pożarna (PSP) including 4 years as zastępca komendanta powiatowego. Transitioned to Urząd Marszałkowski 8 years ago. Rose from specialist to department director. |
| Education | SGSP (Szkoła Główna Służby Pożarnej) — fire engineering. Postgraduate: Public Administration (UMCS Lublin). ECDL Advanced. |

### 2. Two Operating Modes

Tomasz lives in two realities. The system must serve both.

#### MODE 1: Steady-State — Daily Regional Oversight

**80% of Tomasz's time.** No crisis. The voivodeship runs.

In this mode, Tomasz uses SENTINEL to:

- **Monitor regional vital signs:** hospital bed utilization across the voivodeship, air quality trends, road incident counts, infrastructure status.
- **Prepare briefings for the Marszałek:** "Panie Marszałku, PM2.5 in Puławy has been elevated for three days — Zakłady Azotowe report planned maintenance, not an incident. Hospital occupancy in Lublin is at 87%, up from 79% last month. Two DPS facilities in powiat łukowski report staffing shortages."
- **Browse layers:** Flip between healthcare, transport, environment, education — the same map, different data overlays.
- **Answer ad-hoc questions from the Marszałek:** "How many schools are in powiat puławski?" → click, filter, answer. "What's the closest hospital to Janów Lubelski with an SOR?" → click, measure, answer.
- **Spot patterns:** "Air quality in Puławy is consistently worse on Tuesdays — is that correlated with a production schedule at Zakłady Azotowe?"
- **Verify data from BIP:** Municipal BIP pages publish reports as PDFs and HTML tables. Tomasz doesn't trust numbers he can't cross-reference. SENTINEL's scraped data lets him compare what gminas report vs. what sensor data shows.

**Pain points in steady-state:**
- Data about the voivodeship lives in 30+ separate systems and portals. Each gmina has its own BIP. There is no single view.
- Preparing a briefing for the Marszałek takes 2-3 hours of manual data gathering.
- When the Marszałek asks a question in a meeting, Tomasz has to say "I'll check and get back to you" — because the data isn't at his fingertips.
- Social media sometimes surfaces problems before official channels. A Facebook post about a road collapse in gmina Kazimierz Dolny reached 2,000 shares before the powiat reported it.

#### MODE 2: Crisis — Active Incident Response

**20% of Tomasz's time, but 100% of its intensity.**

When an environmental crisis hits — industrial fire, severe smog, chemical spill — Tomasz becomes the operational coordinator. The Marszałek delegates tactical decisions to him and expects to be briefed, not consulted on every call.

In this mode, Tomasz uses SENTINEL to:

- **See the threat in space and time:** Where is the contamination now? Where will it be in 30 minutes? In 2 hours?
- **Identify who is at risk:** Which schools, DPS care homes, hospitals are in the plume path? How many people? How vulnerable?
- **Assess resources:** How many buses can we mobilize? What hospital capacity is available outside the zone? Where are PSP units?
- **Make triage decisions:** Shelter-in-place or evacuate? Which facility first? Can we move 142 elderly DPS residents, or do we seal the building?
- **Issue recommendations to the Marszałek:** "Panie Marszałku, proponuję ogłoszenie alertu RCB dla kodów pocztowych 24-100/110. Szkoły w strefie zagrożenia zamknięte, DPS Puławy w trybie shelter-in-place. Oto dane." The Marszałek signs off; Tomasz executes.
- **Document everything:** Every sensor reading, every recommendation, every decision — timestamped. This is Tomasz's post-incident audit trail. And the Marszałek's political shield.

**Pain points in crisis mode:**
- **Fragmented data, manual aggregation.** GIOŚ publishes PM2.5 on one website. IMGW is a separate portal. Hospital bed counts require calling NFZ. Each source: different login, different URL, different person to call.
- **No spatial integration.** He can look at an air quality map and a map of schools — in two separate browser tabs. There is no single view that says: "These 4 schools and 1 DPS are inside the contamination zone defined by current wind and PM10 readings."
- **Latency.** By the time data is collected, manually cross-referenced, and presented, 45–90 minutes have passed. In a fast-moving industrial fire with shifting wind, that lag is the difference between an ordered evacuation and a chaotic one.
- **No dependency mapping.** He knows the hospitals in the voivodeship. He doesn't have a queryable picture of: which hospital has capacity right now; which road routes pass through the contamination zone; which transport operators have available buses.
- **Situational awareness is person-dependent.** His best analyst knows how to pull all these sources together — but that knowledge lives in a person's head, not in a system.
- **No audit trail in the tool.** Decisions are logged in Word documents or printed forms. No software timeline records: at 14:23 PM10 at station X crossed threshold Y; at 14:31 the team was notified; at 14:47 the recommendation was issued.

### 3. Key Questions — By Mode

#### Steady-State Questions (daily/weekly)

1. "Jaki jest ogólny stan województwa?" — Any anomalies? Anything the Marszałek should know about?
2. "Jak wygląda jakość powietrza w regionie?" — Trends, hotspots, comparisons between powiat.
3. "Ile łóżek szpitalnych jest dostępnych w promieniu 30 km od Puław?" — Resource calculator.
4. "Co piszą ludzie o sytuacji w regionie?" — Social media signals: complaints, reports, photos of infrastructure damage.
5. "Pokaż mi powiat opolski" — Zoom, filter, inspect a specific area.
6. "Jakie dane opublikowała gmina Kazimierz Dolny w ostatnim kwartale?" — BIP scraping verification.

#### Crisis Questions (during active incident)

1. "Gdzie dokładnie jest skażenie?" — Current perimeter. What will it look like in 30 minutes given the wind forecast?
2. "Co jest w strefie zagrożenia?" — How many schools, kindergartens, DPS, hospitals? How many people?
3. "Jak bardzo jest źle powietrze?" — PM2.5/PM10 readings from nearest stations. Are we above thresholds?
4. "Jakie mamy zasoby?" — Available beds, buses, ambulances, PSP units.
5. "Czy możemy ewakuować, czy zamykamy?" — Transport capacity vs. plume timing vs. population.
6. "Kto został już powiadomiony?" — Have mayors, powiat heads, school directors been notified?
7. "Jaka jest prognoza na najbliższe 6 godzin?" — Will the zone expand, contract, or shift?
8. "Czy to eskaluje do poziomu krajowego?" — Does this meet the threshold to notify RCB?

### 4. What "Good Dashboard" Means to Tomasz

#### Steady-state view (default):

- Map of Województwo Lubelskie with powiat/gmina boundaries.
- Color-coded indicators per region: green (normal), yellow (attention), red (action needed).
- Selectable layers: air quality, healthcare, transport, education, environment.
- Side panel: summary statistics for selected region.
- Top bar: last data update timestamp per source. Any source stale >1 hour is flagged.
- Quick search: type a gmina name → zoom and filter.

#### Crisis view (activated on alert or manual switch):

- Threat zone polygon on map, auto-updated as wind/readings change, with 1h and 3h forecast overlays.
- Color-coded sensitive objects within and near the zone: schools (red), DPS (orange), hospitals (blue), critical infrastructure (yellow).
- Population density heatmap clipped to the zone.
- Available transport assets as icons with capacity labels.
- Road network with route viability.
- AI-generated action list with data sources cited.
- Timeline / audit log — every data point, recommendation, and decision timestamped.

#### What Tomasz does NOT want:

- Raw data tables without spatial context.
- Dashboards requiring multiple tabs or windows.
- Any widget requiring explanation before use.
- AI recommendations without visible data sources.
- English-language labels — he works under stress in Polish.
- Systems that fail silently — he must know immediately when a data feed goes down.

### 5. Technology Comfort and Constraints

**Comfort:** Moderate-high within specific domains. Competent with GIS-adjacent tools (used ARCGIS in PSP, familiar with geoportal.gov.pl). Fluent with MS Office, Teams, basic data analysis in Excel. Not a developer. Can read a chart and a map; will not read documentation.

**Hard constraints:**
- Must work on the Urząd Marszałkowski network. Cloud tools need IT approval or local deployment.
- Must be readable on a 55" display in the conference room (briefing the Marszałek) AND on a tablet (walking between offices).
- Must be readable by a 46-year-old under stress. High-contrast, large labels, no tiny dense tables.
- **Polish-language labels** — nie będzie dekodował angielskiej terminologii pod presją.
- No login friction — accessible within 10 seconds. During a crisis, every second counts.

**What he distrusts:**
- AI recommendations without a visible data source — "skąd to wiesz?"
- Systems that look impressive in demo but cannot answer his specific question.
- Dashboards that work with demo data but break on real feeds.
- Any system that requires a developer to maintain after the hackathon team leaves.

### 6. Decision-Making Patterns

**In steady-state:** Tomasz is methodical. He prepares, cross-references, verifies before briefing the Marszałek. He won't present data he can't defend. Time scale: hours to days.

**In crisis:** Tomasz is decisive. Collects information fast, decides on available data, issues clear recommendations. Expects acknowledgment. Will update a recommendation if new data arrives, but will not wait for perfect information before issuing the first one. Time scale: minutes.

**Escalation chain:**
1. Tomasz assesses the situation using SENTINEL.
2. Issues immediate protective recommendations (shelter-in-place, closures) within his authority.
3. Briefs Marszałek with SENTINEL dashboard — "this is the situation, this is what I recommend."
4. Marszałek approves escalation (RCB alert, formal orders).
5. Tomasz coordinates execution.

### 7. Context for Bonus Features

These aren't abstract feature requests. They come from Tomasz's real pain points:

| Bonus Feature | Tomasz's Need |
|---|---|
| **Scraping public data sources** | "Gminy w Lubelskim publikują dane o infrastrukturze, budżetach, zagrożeniach na swoich BIP-ach — jako PDF-y, tabelki HTML, pliki XLSX. Nie mam czasu tego ręcznie zbierać z 213 stron." |
| **Social media agents** | "W 2024 informacja o awarii wodociągów w Świdniku pojawiła się na Facebooku 20 minut przed oficjalnym zgłoszeniem. Ludzie wrzucają zdjęcia, filmiki — to jest najszybszy sensor jaki mam, ale nie mam jak tego monitorować." |
| **Resource calculators** | "Marszałek pyta: ile łóżek szpitalnych jest w promieniu 30 km od Puław? Ile autobusów MPK Lublin może oddelegować? Pojemność magazynów przeciwpowodziowych nad Wisłą? Muszę to policzyć ręcznie za każdym razem." |
| **Voice assistant** | "Na sali konferencyjnej stoję przy dużym ekranie, w jednej ręce telefon, w drugiej dokumenty. Chcę powiedzieć: 'Pokaż powiat puławski', 'Jaki jest PM2.5 w Puławach?', 'Włącz warstwę szpitali' — bez szukania myszy." |

### 8. What Tomasz Wants to See in the Demo

This is what he — and by proxy, the jury member from the Urząd Marszałkowski — expects when he sits down to the 5-minute presentation:

1. **"Pokaż mi mapę mojego województwa."** — Lubelskie, z powiatami i gminami. Nie genericza mapa Polski.
2. **"Kliknę powiat puławski — co tu jest?"** — Zoom, filtr, dane o powiecie.
3. **"Włącz warstwę jakości powietrza."** — GIOŚ stations, Airly sensors, current readings, color-coded.
4. **"A teraz pokaż mi co się dzieje, gdy zaczyna się pożar w Zakładach Azotowych."** — Transition to crisis mode. Plume appears. Schools, DPS, hospital highlighted. AI recommendation generated.
5. **"Skąd bierzesz te dane?"** — Source transparency. Every number has a provenance.
6. **"Czy mogę to obsługiwać głosem?"** — Voice command demo.
7. **"A co z danymi, które nie mają API?"** — Show scraping module pulling from a gmina BIP page.

---

## Design Implications for SENTINEL

| User Need | SENTINEL Feature |
|---|---|
| Marszałek: 60-second briefing | Clean default view with regional health indicators, no interaction needed to understand state |
| Tomasz steady-state: layer browsing | Multi-layer toggle with persistent map, selectable data overlays |
| Tomasz steady-state: ad-hoc queries | Click-to-filter on powiat/gmina, resource calculators, search |
| Tomasz steady-state: data verification | Scraped BIP data with source links and timestamps |
| Tomasz steady-state: signal monitoring | Social media feed with geolocation pins on map |
| Tomasz crisis: threat visualization | Plume polygon with wind-driven forecast, auto-updated |
| Tomasz crisis: who is at risk | Spatial join of threat zone with school/DPS/hospital registry |
| Tomasz crisis: resource assessment | Transport capacity, hospital beds, PSP units — live or near-live |
| Tomasz crisis: action recommendations | AI-generated prioritized action list with cited data sources |
| Tomasz crisis: audit trail | Append-only event log: sensor → recommendation → decision → acknowledgment |
| Both: source transparency | Every AI output exposes the data inputs that produced it |
| Both: large screen readability | High-contrast, min 16px labels, color-coded severity, responsive layout |
| Both: Polish UX | All labels, recommendations, and voice commands in Polish |
| Both: voice control | Polish-language voice commands for map navigation, layer toggle, data readout |
| Both: offline resilience | Visible staleness indicators per data source; no silent failures |
