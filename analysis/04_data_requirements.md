# Data Requirements & Dependency Analysis

**Version:** 1.0  
**Date:** 2026-04-11  
**Scenario:** ZESTAW D — Environmental Failure (Smog / Industrial Fire)  
**System:** Geospatial Decision Dashboard for Marszałek Województwa Lubelskiego  
**Scoring criterion:** Głębokość analizy zależności między zestawami danych, trafność wniosków

---

## 1. Data Inventory

### 1.1 Air Quality — GIOŚ

| Attribute | Detail |
|---|---|
| Provider | Główny Inspektorat Ochrony Środowiska |
| API base | `https://api.gios.gov.pl/pjp-api/rest/` |
| Endpoints | `/station/findAll`, `/sensor/sensors/{stationId}`, `/data/getData/{sensorId}` |
| Pollutants | PM2.5, PM10, NO₂, SO₂, O₃, CO, Pb, C₆H₆ |
| Coverage | ~150 stations nationwide; **8 stations in Lubelskie** (incl. Lublin-Śródmieście, Puławy-Centrum, Puławy-Azoty, Chełm, Zamość, Biała Podlaska, Kraśnik, Włodawa) |
| Update frequency | Hourly values; stations report with 1-hour lag |
| Format | JSON |
| Gaps / limitations | Low spatial resolution — large areas between stations unmonitored; 1-hour lag means crisis may peak before data confirms it; no push mechanism, must poll |

### 1.2 Air Quality — Airly

| Attribute | Detail |
|---|---|
| Provider | Airly sp. z o.o. (commercial IoT sensor network) |
| API base | `https://airapi.airly.eu/v2/` |
| Endpoints | `/measurements/nearest`, `/measurements/point`, `/installations/nearest` |
| Pollutants | PM1, PM2.5, PM10, temperature, humidity, pressure |
| Coverage | ~10,000+ sensors in Poland; **in Lubelskie: dense in Lublin (~40 sensors), moderate in Puławy (~8), sparse in eastern/rural powiatów** |
| Update frequency | ~5-minute resolution |
| Format | JSON |
| Gaps / limitations | Commercial — requires API key; data quality varies (consumer-grade sensors); not legally certified for regulatory thresholds; spatial clustering in cities, sparse in rural/industrial areas |

### 1.3 Weather — IMGW

| Attribute | Detail |
|---|---|
| Provider | Instytut Meteorologii i Gospodarki Wodnej |
| API base | `https://danepubliczne.imgw.pl/api/data/` |
| Endpoints | `/synop` (current SYNOP observations), `/meteo` (station metadata) |
| NWP forecasts | `https://danepubliczne.imgw.pl/datastore/getfiledown/Arch/Telemetria/Meteo/` |
| Parameters | Wind speed (m/s), wind direction (°), temperature (°C), pressure (hPa), precipitation (mm/h), humidity (%) |
| Key parameter for plume | **Mixing layer height** (MLH) — determines vertical dispersion; critical for concentration estimates |
| Lubelskie stations | Lublin-Radawiec (SYNOP), Puławy (climate station), Zamość, Terespol |
| Update frequency | SYNOP observations: 10-min to hourly; NWP model runs: every 6 hours (00, 06, 12, 18 UTC) |
| Format | JSON (SYNOP API), CSV/GRIB (NWP model output) |
| Gaps / limitations | NWP model has 6-hour run latency; mixing layer height not always in public API — may require GRIB decoding; wind at 10m height, not at plume release height |

### 1.4 Sensitive Objects — Schools (RSPO)

| Attribute | Detail |
|---|---|
| Provider | Ministerstwo Edukacji Narodowej — Rejestr Szkół i Placówek Oświatowych |
| Access | Data portal: `https://rspo.gov.pl` — downloadable CSV/API |
| Fields | School name, type (primary/secondary/kindergarten), address, coordinates, pupil count, RSPO number |
| Lubelskie scope | **~1,800 schools and educational facilities** across 213 gmin |
| Update frequency | Annual; significant events (openings/closures) published mid-year |
| Format | CSV, JSON API |
| Gaps / limitations | No real-time occupancy (holidays, remote learning days); coordinates require geocoding for older records; contact numbers not always current |

### 1.5 Sensitive Objects — Care Homes (DPS Registry)

| Attribute | Detail |
|---|---|
| Provider | Ministerstwo Rodziny i Polityki Społecznej |
| Access | `https://www.gov.pl/web/rodzina/domy-pomocy-spolecznej` — searchable registry |
| Fields | DPS name, address, type (elderly / disabled / psychiatric), bed count, licensed capacity |
| Update frequency | Annual licensing cycle |
| Format | HTML table / manual download; no formal REST API |
| Lubelskie scope | **~60 DPS facilities** — concentrated in Lublin, Puławy, Chełm, Zamość |
| Gaps / limitations | No resident mobility/medical classification in public data; current occupancy not published; contact info may be outdated; no machine-readable API — requires scraping or manual entry |

### 1.6 Sensitive Objects — Hospitals (NFZ/MZ)

| Attribute | Detail |
|---|---|
| Provider | Narodowy Fundusz Zdrowia — rejestr świadczeniodawców |
| Access | `https://rejestr.nfz.gov.pl/` — REST API available |
| Fields | Facility name, address, type, specialty departments, contracted bed counts |
| Update frequency | Quarterly contract updates; real-time occupancy not publicly available |
| Format | JSON API |
| Lubelskie scope | **~35 hospitals**; key facilities: SPZOZ Puławy, COZL Lublin (Centrum Onkologii), SPSK1/SPSK4 Lublin, szpital powiatowy Chełm, Zamość, Biała Podlaska |
| Gaps / limitations | Contracted beds ≠ available beds (occupancy fluctuates); ICU/specialty bed counts require separate NFZ data sets; real-time capacity requires integration with hospital HIS systems (not public) |

### 1.7 Transport Resources — GUS/REGON + Contracts

| Attribute | Detail |
|---|---|
| Provider | GUS REGON registry; voivodeship transport contracts |
| Fields | Company name, NIP, REGON, vehicle count by type, seating capacity |
| Update frequency | Annual business registration; contract list maintained by voivodeship crisis cell |
| Format | REGON API (XML/JSON); contract data in internal voivodeship documents |
| Lubelskie scope | MPK Lublin (buses), PKS Wschód, private carriers; voivodeship transport contracts |
| Gaps / limitations | REGON shows company existence, not vehicle availability; actual availability requires phone confirmation; no real-time fleet tracking in public data |

### 1.8 Population Density — GUS Census Grid

| Attribute | Detail |
|---|---|
| Provider | Główny Urząd Statystyczny — census 2021 |
| Access | `https://geo.stat.gov.pl/` — INSPIRE-compliant WMS/WFS |
| Fields | Population count per 1km² grid cell, age breakdown |
| Update frequency | Decennial census; estimates updated annually |
| Format | GeoTIFF / Shapefile / WFS |
| Gaps / limitations | 1km² resolution misses sub-grid variation; census data 5+ years old; no time-of-day variation (daytime vs. nighttime population) |

### 1.9 Municipal Public Data — BIP Pages (Bonus: Scraping)

| Attribute | Detail |
|---|---|
| Provider | 213 gmin + 20 powiatów + 4 miasta na prawach powiatu in Lubelskie — each with its own BIP (Biuletyn Informacji Publicznej) |
| Access | Individual BIP websites (e.g., `bip.lublin.eu`, `bippulawy.pl`, `umchelm.bip.lubelskie.pl`) |
| Data types | Budget reports, infrastructure status, environmental reports, council resolutions, staffing data, public procurement |
| Format | **HTML tables, PDF documents, XLSX files** — no standard format, no API |
| Update frequency | Varies by gmina — some weekly, some quarterly, some rarely |
| Gaps / limitations | No standardized structure across gminas; documents often scanned PDFs; requires per-source scraping adapters; data quality and timeliness vary wildly |
| SENTINEL approach | Scraping module with per-source parsers for priority gminas (Puławy, Lublin, Chełm); extract structured data from HTML/PDF/XLSX; normalize into SENTINEL data model |

### 1.10 Social Media Signals (Bonus: Social Media Agents)

| Attribute | Detail |
|---|---|
| Sources | Facebook (public groups: Lublin112, Puławy24, regional groups), X (Twitter), local portals (lublin.eu, kurierlubelski.pl) |
| Data types | Citizen reports, photos, geolocated posts about incidents, infrastructure damage, environmental concerns |
| Value | Often **15–30 minutes faster than official channels** — citizens post photos of smoke, flooding, road damage before any agency is notified |
| Format | Unstructured text + images + geolocation (when available) |
| SENTINEL approach | Demonstrational module: monitor selected public feeds, classify posts by relevance (AI), extract/infer geolocation, display as pins on map with confidence score |
| Gaps / limitations | Privacy considerations; geolocation inference is imprecise; signal-to-noise ratio is low; demonstrational scope only |

---

## 2. Dependency Graph

### 2.1 Primary Dependency Chains

```
IMGW wind vector (speed, direction, MLH)
    │
    ├─── GIOŚ/Airly PM2.5 source concentration
    │         │
    │         └──► [PLUME MODEL] → Threat zone polygon (t, t+1h, t+3h)
    │                                        │
    │                    ┌───────────────────┤
    │                    │                   │
    │              RSPO schools         MRIPS DPS         NFZ hospitals
    │              (lat/lon, count)     (lat/lon, count)  (lat/lon, beds)
    │                    │                   │                   │
    │                    └───────────────────┴───────────────────┘
    │                                        │
    │                    [SPATIAL JOIN] → At-risk facilities list
    │                                        │
    │                    ┌───────────────────┤
    │                    │                   │
    │            GUS population          Facility capacity
    │            density grid            (mobility class)
    │                    │                   │
    │                    └─── [VULNERABILITY SCORE] per facility
    │                                        │
    │                    Transport availability (bus count, seats)
    │                                        │
    │                    [FEASIBILITY CHECK] → shelter-in-place OR evacuate
    │                                        │
    │                    NFZ hospital beds (receiving capacity)
    │                                        │
    │                    [ACTION QUEUE] → prioritized, time-sequenced decisions
    │
    └──► Wind forecast update (NWP t+6h run) → re-run plume model → update all downstream
```

### 2.2 Dependency Matrix

| Producing dataset | Consuming dataset | Dependency type | Output |
|---|---|---|---|
| IMGW wind vector | GIOŚ/Airly PM source | Directional trajectory | Plume axis and extent |
| IMGW mixing layer height | Plume model | Concentration amplifier | Ground-level concentration estimates |
| GIOŚ/Airly PM2.5 current | Plume model | Source strength | Emission rate estimate |
| Plume model polygon | RSPO school coords | Spatial intersection | Schools in zone + ETA |
| Plume model polygon | MRIPS DPS coords | Spatial intersection | DPS in zone + ETA |
| Plume model polygon | NFZ hospital coords | Spatial intersection | Hospitals in zone |
| Facility headcount | Transport bus capacity | Demand vs. supply | Evacuation feasibility ratio |
| DPS medical classification | ALS ambulance count | Medical demand | Pre-staging decision |
| NFZ available beds | Evacuation routing | Receiving capacity | Whether to route to local vs. distant hospital |
| GUS population density | Plume polygon clip | Exposure population | Total persons at risk |
| IMGW NWP t+6h update | Plume model re-run | Forecast refinement | Zone shift / expansion alert |
| Plume ETA per facility | Facility response time | Decision deadline | Action urgency ranking |

---

## 3. Derived Metrics

SENTINEL does not display raw data. It computes and displays these derived metrics:

### 3.1 Threat Zone Polygon

**Input:** Wind speed (u, v components), mixing layer height, PM2.5 source concentration, atmospheric stability class (Pasquill-Gifford from IMGW temperature gradient and wind speed).

**Method:** Simplified Gaussian plume dispersion:

```
C(x,y,z) = Q / (2π σy σz u) × exp(-y²/2σy²) × [exp(-(z-H)²/2σz²) + exp(-(z+H)²/2σz²)]
```

Where:
- Q = emission rate (estimated from PM2.5 rise rate at nearest station)
- σy, σz = horizontal/vertical dispersion coefficients (Pasquill-Gifford tables)
- u = mean wind speed (m/s)
- H = effective release height (m)

**Output:** GeoJSON polygon where C > 200 µg/m³ (Polish PM10 alert threshold) or C > 75 µg/m³ (WHO PM2.5 24h limit ×5 acute exposure threshold), with 1h and 3h forecast variants.

### 3.2 Vulnerability Score Per Facility

**Formula:**
```
V = (population_count × mobility_weight × (1 / plume_ETA_minutes)) × density_factor
```

- `mobility_weight`: schools = 0.7 (children can walk), DPS = 1.0 (many non-ambulatory), hospitals = 0.9
- `plume_ETA_minutes`: time in minutes until modeled concentration exceeds threshold at facility location
- `density_factor`: GUS population density within 500m radius, normalized 0–1

**Output:** Ranked list of facilities, highest V first = highest priority.

### 3.3 Evacuation Feasibility Ratio

```
EFR = required_seats / available_seats
```

If EFR > 0.8 AND plume ETA < (loading_time + transit_time): shelter-in-place recommended.  
If EFR ≤ 0.5 AND plume ETA > 2 × (loading_time + transit_time): evacuation feasible.

### 3.4 Transport Demand vs. Supply

| Variable | Source | Unit |
|---|---|---|
| Required seats | RSPO/MRIPS headcounts in zone | Persons |
| Available buses | Voivodeship contract registry | Vehicles |
| Available seats | Bus capacity × vehicles | Seats |
| Loading time | Standard estimate: 8 min/50 persons | Minutes |
| Transit time | Distance to safe zone / avg speed | Minutes |

### 3.5 Hospital Surge Capacity

```
surge_capacity = Σ(available_beds[h] for h within 50km) - expected_casualties
```

expected_casualties estimated from exposure population × health impact rate (0.3% for PM2.5 >200 µg/m³ in vulnerable population, based on WHO epidemiological data).

### 3.6 Decision Deadline

```
deadline = plume_ETA_minutes - facility_response_time_minutes
```

- School closure response time: 15 minutes (PA announcement + move to interior)
- DPS shelter-in-place: 20 minutes (resident mobilization)
- Hospital HVAC seal: 5 minutes (single action by engineer)
- Evacuation: 30–90 minutes (loading + transit)

If `deadline < 0`: immediate action required. If `deadline < 15`: urgent. If `deadline > 30`: monitor and reassess.

---

## 4. Data Gaps & Assumptions

| Gap | Impact | Mitigation |
|---|---|---|
| GIOŚ 1-hour data lag | Cannot detect fast-rising plume until too late | Airly sensors provide 5-min data; use rate-of-change triggering on Airly, validate with GIOŚ |
| Mixing layer height not in public API | Underestimates or overestimates ground concentrations | Use Pasquill stability class proxy from IMGW temperature + wind speed; default to worst-case (stable, MLH 500m) |
| DPS resident mobility not in public registry | Cannot estimate ALS vs. bus transport split | Pre-load from manual data collection during non-crisis period; default assumption: 10% require ALS transport |
| Hospital real-time occupancy unknown | Bed count is contracted capacity, not available beds | Use 70% occupancy as default assumption (national average); flag as estimate in UI |
| Transport availability not real-time | Actual bus availability requires phone confirmation | Maintain pre-vetted contract list with average availability rate; flag resources as "unconfirmed" until phone contact |
| Airly rural gaps | Industrial zones often poorly covered by Airly | GIOŚ stations near industrial zones are usually sited specifically for monitoring; fall back to GIOŚ as primary where Airly sparse |
| Emission rate unknown at fire onset | Cannot initialize Gaussian plume model accurately | Estimate from PM2.5 rise rate at nearest two stations via inverse modeling; update as data accumulates |

---

## 5. AI/LLM Role

Not all SENTINEL outputs benefit equally from AI. The split:

### Deterministic computation (no AI needed)
- Gaussian plume polygon: pure physics + math
- Spatial intersection of polygon with facility locations: GIS query
- Transport feasibility ratio: arithmetic
- Decision deadline calculation: arithmetic

### AI synthesis (Claude adds value)
- **Natural language action recommendation:** "Based on PM2.5 at 341 µg/m³ (station PuL001, 4 min ago), wind NNW at 18 km/h, and DPS Puławy at 2.4 km NNE (142 residents, 14 requiring ALS), recommend immediate shelter-in-place activation and pre-staging of 1 ALS unit at ul. Dęblińska." — Combines multiple data points into one human-readable directive.
- **Anomaly detection:** Detecting when a new NWP run changes the forecast significantly vs. normal model variation.
- **Ambiguous event classification:** A citizen report of "smoke and smell near Zakłady Azotowe" needs classification before sensors confirm.
- **Post-incident summary generation:** Automatic after-action report from the event log.
- **Threshold judgment in gray zones:** PM2.5 at 165 µg/m³ (below Polish threshold of 200, above WHO threshold of 75) with a school 1.8 km downwind — shelter-in-place or not? AI can reason about the trajectory, wind forecast, and risk/benefit of false alarm vs. exposure.

### Human decision (AI supports, does not replace)
- Signing the formal decyzja (legal order)
- Escalating to RCB
- Approving public RCB-Alert SMS
- Overriding a recommendation based on local knowledge

---

## 6. Integration Architecture

### 6.1 Data Pull Schedule

| Source | Method | Interval | Trigger override |
|---|---|---|---|
| GIOŚ | REST poll | 10 min | PM2.5 threshold breach → 2 min |
| Airly | REST poll | 5 min | Always 5 min (native resolution) |
| IMGW SYNOP | REST poll | 10 min | Active crisis → 5 min |
| IMGW NWP | Download on model run | 6h (00/06/12/18 UTC) | Compare successive runs; alert on >15% change in wind vector |
| RSPO (schools) | Scheduled refresh | Weekly | Manual trigger |
| MRIPS (DPS) | Scheduled refresh | Monthly | Manual trigger |
| NFZ (hospitals) | Scheduled refresh | Weekly | Manual trigger |
| Transport contracts | Manual entry | On contract change | — |

### 6.2 Event-Triggered Processing

When PM2.5 at any GIOŚ or Airly station rises >50 µg/m³ above baseline within a 15-minute window:
1. Mark station as potential source
2. Fetch nearest IMGW SYNOP for wind vector
3. Initialize Gaussian plume model
4. Run spatial intersection with facility registry
5. Compute vulnerability scores and decision deadlines
6. Generate Claude AI action recommendation
7. Push to SENTINEL dashboard and event log

### 6.3 Caching Strategy

- Facility registry (schools, DPS, hospitals): in-memory cache, refreshed weekly
- Population density grid: loaded once at startup (static GeoTIFF)
- GIOŚ/Airly readings: 30-minute rolling window in memory; persistent to SQLite for audit
- Plume polygon: recomputed on each new wind or PM reading; cached for 5 minutes

### 6.4 Offline / Degraded Mode

If GIOŚ API is unreachable: use last-known values with staleness indicator in UI.  
If IMGW API is unreachable: use last-known wind + stability class; flag plume model as "wind data stale — using last observation from [timestamp]".  
If all external feeds are down: SENTINEL continues to display last-known state with visible staleness warnings per data source. Duty officer is alerted. System does not fail silently.

---

## Summary: The Dependency Argument for Scoring

The ZESTAW D scenario is not primarily a data collection problem — GIOŚ, IMGW, RSPO, and NFZ registries exist and are accessible. It is a **data integration problem**.

The value created by SENTINEL emerges entirely from cross-dataset dependencies:

**Crisis dependencies (Zestaw D core):**
- Wind + PM source → plume (neither alone produces a geographic threat boundary)
- Plume + facility locations → who is at risk (neither alone tells you which schools to close)
- Facility headcount + transport capacity + plume ETA → shelter vs. evacuate (each dataset alone suggests nothing about the right action)
- Hospital capacity + evacuation zone + route viability → where to send people (the receiving constraint changes the sending decision)
- NWP forecast update + active plume → expanded threat to new facilities (invisible without continuous multi-source comparison)

**Steady-state dependencies (governance value):**
- Hospital bed data + population density → healthcare coverage gaps visible on the map
- Air quality trends + school locations → chronic exposure risk areas for the Marszałek's attention
- BIP-scraped municipal data + sensor data → discrepancy detection ("gmina reports air is fine, GIOŚ says otherwise")
- Social media signals + official reports → early warning and verification layer

Each dependency chain represents a decision that a manual process makes incorrectly, too slowly, or not at all. SENTINEL's contribution is the **automatic computation of these dependency chains** — in crisis mode as a sequenced action list for the operator (Tomasz Kowalczyk), in steady-state as an always-ready regional overview for the Marszałek's briefings.

The system is one — the map, the data, the architecture. The difference is which layers are active and how urgently the results are needed.
