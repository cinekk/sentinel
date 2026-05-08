# WCZK Flood Monitoring — Gap Analysis

**Client:** Krzysztof Kuriata, Dyrektor Wydziału Bezpieczeństwa i Zarządzania Kryzysowego  
**Voivodeship:** Warmińsko-Mazurskie  
**Document:** MONITORING POWODZIOWY.pdf  
**Analysis date:** 2026-05-06

---

## Context

The client wants an application called **WCZK** (Wojewódzkie Centrum Zarządzania Kryzysowego) that automates flood/hydrological threat monitoring and supports generating morning/evening situation reports and alerts for the duty officer. Their reference example is a map at http://87.106.33.162/map.

Sentinel was built as a general dual-use crisis platform. This analysis maps their requirements to what we have, what is missing, and how hard each gap is to close.

---

## Architecture Fit

The client's stated architecture:
```
Źródła danych → Moduł integracji → Moduł AI → Dashboard + Raporty + Alerty
```

Sentinel's architecture is an exact match at every layer:
```
Plugins (data) → FastAPI (processing) → OpenRouter/LLM (AI) → Map + REST API
```

The structural fit is strong. The gaps are in scope (wrong voivodeship), persistence (no time-series), and output channels (no PDF, no alerts, no scheduled reports).

---

## Requirements vs Current State

### 1. Data Sources

| Requirement | Status | Notes |
|---|---|---|
| IMGW HYDRO stations — live data every 30 min | ✅ **EXISTS** | `plugins/imgw_hydro.py`, 5-min cache, fetches all-Poland then filters |
| IMGW METEO stations | ❌ MISSING | Only hydro gauges today |
| Warmińsko-Mazurskie scope | ❌ WRONG SCOPE | Plugin currently filters to `lubelskie` |
| Hydro warnings & IMGW communications | ⚠️ PARTIAL | Alert level (normal/warning/alarm) comes from IMGW river-statuses JSON, but no narrative text from IMGW hydro bulletins |
| Alert RCB feed | ❌ MISSING | No integration |
| Media monitoring (keywords: podtopienie, zalanie, warmińsko-mazurskie) | ❌ MISSING | No media/news scanning at all |
| Other weather services / precipitation | ❌ MISSING | No precipitation or forecast data |
| Sea level forecasts (for Nowakowo, Elbląg, Żukowo) | ❌ MISSING | These Baltic-adjacent stations require tidal/sea level data for the ML model |

### 2. Processing & Analysis

| Requirement | Status | Notes |
|---|---|---|
| Event escalation analysis | ✅ **EXISTS** | `services/flood_assessment.py` classifies risk per facility |
| Alert level classification (normal/warning/alarm) | ✅ **EXISTS** | Full IMGW statusCode → AlertLevel mapping in `plugins/imgw_hydro.py` |
| Trend detection (rise/fall per reading) | ❌ MISSING | Only snapshot, no history |
| 3 consecutive rising readings → "UWAGA POZIOM WODY WZRASTA" alarm | ❌ MISSING | Requires time-series persistence |
| Water level history storage | ❌ MISSING | Gauges are cached in memory only, not persisted to DB |
| +12h water level prediction (ML) | ❌ MISSING | No predictive model; this is the largest single gap |
| +12h prediction specifically for Nowakowo/Elbląg/Żukowo with sea level | ❌ MISSING | Needs sea level API + station-specific model |
| Probability of reaching warning/alarm levels | ❌ MISSING | |
| County-level risk aggregation (powiaty podwyższonego ryzyka) | ❌ MISSING | No administrative boundary data |
| Geolocation of media mentions | ❌ MISSING | |

### 3. Output: Dashboard & Map

| Requirement | Status | Notes |
|---|---|---|
| Map with OpenStreetMap base | ✅ **EXISTS** | Leaflet + OSM, all IMGW gauges shown as colored pins |
| Gauge stations on map | ✅ **EXISTS** | Color-coded by alert level |
| Time-window charts (24h / 7 days / 30 days) | ❌ MISSING | No chart component; no historical data to drive it |
| Historical data access | ❌ MISSING | |
| Trend arrows on station markers | ❌ MISSING | No trend data |
| WCZK operator panel (non-programmer friendly) | ❌ MISSING | Current UI is a technical map, not an operator panel |

### 4. Output: Reports

| Requirement | Status | Notes |
|---|---|---|
| Morning situational briefing (06:30) | ⚠️ PARTIAL | `services/briefing.py` generates audio-first text briefing on-demand; not scheduled, not PDF, Lublin-focused |
| Evening briefing (18:30) | ⚠️ PARTIAL | Same as above |
| Report structure: IMGW warnings / last 12h events / high-risk districts | ⚠️ PARTIAL | Events exist in DB; warnings partial; district aggregation missing |
| PDF report generation | ❌ MISSING | |
| Scheduled report dispatch (06:30, 18:30) | ❌ MISSING | No scheduler in app |

### 5. Output: Alerts

| Requirement | Status | Notes |
|---|---|---|
| Threshold-based alerts to WCZK duty officer | ❌ MISSING | No alert delivery system |
| Email delivery | ❌ MISSING | |
| SMS delivery | ❌ MISSING | |
| Telegram / Signal delivery | ❌ MISSING | |
| Draft communications for PCZK/JST | ❌ MISSING | Could leverage existing LLM pipeline |

### 6. Infrastructure

| Requirement | Status | Notes |
|---|---|---|
| Runs in voivodeship office infrastructure | ✅ **COMPATIBLE** | Docker Compose, self-hosted, no cloud lock-in |
| Tool supports decisions, does not make them | ✅ **BY DESIGN** | Sentinel's design principle matches |

---

## Summary Scores

```
Data ingestion:      ████░░░░░░  3/8 requirements met
Processing/AI:       ██░░░░░░░░  2/10 requirements met
Map/Dashboard:       ██░░░░░░░░  2/6 requirements met
Reports:             ██░░░░░░░░  1/5 requirements met (partial)
Alerts:              ░░░░░░░░░░  0/5 requirements met
Infrastructure:      ██████████  2/2 requirements met
```

**Overall coverage: ~40% of IMGW-core features; ~15% overall when counting media, ML, and alerts**

---

## Critical Path Items

These are blockers for any useful demo to the client:

1. **Voivodeship scope change** — without this, no data is relevant to Warmińsko-Mazurskie
2. **Historical gauge persistence** — without this, trend detection and charts are impossible
3. **Trend alarm (3 rising readings)** — the explicit named feature the client described
4. **Scheduled reports** — the 06:30/18:30 cadence is core to daily operations

---

## What We Can Reuse Unchanged

- The entire plugin architecture — new data sources slot in without touching existing code
- `plugins/imgw_hydro.py` — needs only a voivodeship filter change and time-series hook added
- `services/briefing.py` — the text generation pattern (deterministic, no LLM) should be extended, not replaced
- `services/tts.py` + `routers/voice.py` — audio briefing can coexist with PDF reports
- `services/openrouter.py` — reusable for media classification and PCZK draft generation
- `database.py` — SQLite is fine for this client's scale
- FastAPI app structure — router per feature, plugin per data source
- Deployment stack (Docker + Caddy) — matches "runs in office infrastructure"
