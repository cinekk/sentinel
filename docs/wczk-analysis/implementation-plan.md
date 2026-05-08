# WCZK Implementation Plan

**Based on:** gap-analysis.md  
**Target:** Warmińsko-Mazurskie voivodeship, WCZK application  
**Date:** 2026-05-06

---

## Guiding principles

1. Each phase ends with something the client can open in a browser and show to their leadership.
2. The Lublin demo (hackathon) continues to work — we never break existing features.
3. WCZK is a new *domain* within Sentinel, not a fork. Same backend, same plugin system.
4. The ML prediction (+12h) is phased last — it needs historical data first.

---

## Phase 1 — Warmińsko-Mazurskie Live Map (1 week)

**Goal:** Client opens the app and sees their actual stations with real alert levels, trend arrows, and a basic chart. First useful artifact.

### 1.1 Voivodeship Switch

- Change `plugins/imgw_hydro.py` filter from `"lubelskie"` → `"warmińsko-mazurskie"` (or make it a config value `IMGW_VOIVODESHIP`).
- Add `IMGW_VOIVODESHIP` to `config.py` and `.env.example`.
- The Lublin demo can use a different env file; production defaults to warmińsko-mazurskie.

### 1.2 Gauge Reading Time-Series (DB)

New SQLAlchemy table: `gauge_readings`

```
id          INTEGER PK
station_id  TEXT
station_name TEXT
river       TEXT
level_cm    REAL
alert_level TEXT  (normal/warning/alarm/unknown)
recorded_at DATETIME
```

- Background task (APScheduler or FastAPI lifespan repeating task) polls IMGW every 30 min and writes rows to `gauge_readings`.
- Keep 90 days of history; older rows pruned in the same background task.
- New endpoint: `GET /api/hydro/stations/{station_id}/history?window=24h|7d|30d` → returns `[{ts, level_cm, alert_level}]`.

### 1.3 Trend Detection + "POZIOM WZRASTA" Alarm

- After each DB write, check last 3 readings for the station.
- If all 3 are rising → create a `CrisisEvent` via `services/crisis_store.py` with category `flood`, severity `high`, description `"UWAGA POZIOM WODY WZRASTA — stacja {name}, {river}"`.
- Alarm is created at most once per 3-hour window per station (de-duplication).

### 1.4 Chart Endpoint

- `GET /api/hydro/stations` → list of all W-M stations with current level + trend (rising/falling/stable).
- `GET /api/hydro/stations/{station_id}/history?window=24h` → time-series for chart.
- Trend = compare latest reading to 3 readings ago; +/−/= symbol.

### 1.5 Map Updates

- Add trend arrow icon overlay on gauge markers (up/down/stable).
- Add click-popup chart (Chart.js, no build step) with 24h/7d/30d toggle — driven by the new history endpoint.

**Deliverable:** Live W-M map with stations, color-coded alert levels, trend arrows, clickable time-series charts.

---

## Phase 2 — Scheduled Reports + Basic Alerts (1 week)

**Goal:** 06:30 and 18:30, the duty officer receives a report automatically. No manual trigger needed.

### 2.1 Report Scheduler

- Use APScheduler (already compatible with FastAPI lifespan) or a simple `asyncio` task.
- Schedule `generate_and_dispatch_report("morning")` at 06:30 Warsaw time.
- Schedule `generate_and_dispatch_report("evening")` at 18:30 Warsaw time.

### 2.2 WCZK Report Content (new `services/wczk_report.py`)

Morning report structure (per spec):
1. Active IMGW warnings (from crisis events with category=flood + severity≥high)
2. Events from last 12h (flood events from DB)
3. High-risk districts (powiaty) — derived from stations in warning/alarm state

Evening report structure:
1. Day summary (event count, peak levels reached, resolved vs active)
2. Key interventions (manual entries — see operator panel)
3. Tomorrow's outlook (current trend extrapolation — no ML yet, just "X stations rising")

Output: structured Markdown (rendered HTML for email) + PDF via WeasyPrint.

### 2.3 Email Alert Delivery

- New config vars: `ALERT_EMAIL_TO`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`.
- `services/alerts.py` — `send_email(subject, body_html, attachments=[])`.
- Sends scheduled reports as email with PDF attachment.
- Threshold alert: when trend alarm fires (Phase 1.3), also send immediate email to duty officer.

### 2.4 Telegram Alert Delivery (optional / depends on client preference)

- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in config.
- One-line threshold alerts: `"⚠️ UWAGA POZIOM WODY WZRASTA — Elbląg (Elbląg), stan: 245 cm ↑"`.
- Scheduled report summary (not full PDF — just key numbers).

**Deliverable:** Duty officer receives morning and evening email with current flood situation. Immediate Telegram/email when a station shows 3 rising readings.

---

## Phase 3 — WCZK Operator Panel (1 week)

**Goal:** Non-programmer duty officer can configure thresholds, review the current picture, confirm reports, and add manual notes — without touching code or a terminal.

### 3.1 Operator Panel Route `/wczk`

Simple FastAPI-served HTML page (no build step, same pattern as current frontend).

Sections:
- **Status strip** — current count of stations by state (operational/warning/alarm)
- **Active alerts** — list of triggered alarms with acknowledge button
- **Station table** — all W-M stations, sortable by level/trend/alert
- **Report preview** — last generated morning/evening report
- **Settings** — alert recipients, threshold overrides per station (optional offset in cm)
- **Manual note** — text field to add a note that appears in next evening report's "interventions" section

### 3.2 Alert Acknowledgement API

- `POST /api/wczk/alerts/{event_id}/acknowledge` — marks a crisis event as `investigating`, records the duty officer's name (or just timestamp).
- Acknowledged alerts no longer appear in the active alert strip.

### 3.3 Configurable Recipients

- Store alert recipients in DB (table `alert_recipients`): name, email, telegram_id, enabled.
- Editable from the operator panel.
- Replaces hardcoded env vars for multi-recipient scenarios.

**Deliverable:** A URL the director can bookmark. No code knowledge needed to use it.

---

## Phase 4 — Media Monitoring + Alert RCB (1-2 weeks)

**Goal:** The system automatically scans for flood-related news and official RCB alerts.

### 4.1 Media Monitoring Plugin (`plugins/media_monitor.py`)

- Polls Google News RSS (or similar) every 30 min for: `("podtopienie" OR "zalanie") AND "warmińsko-mazurskie"`.
- Deduplicates against previously seen articles (hash of URL + title in DB).
- Passes each new article to `services/openrouter.py` for classification: relevant/irrelevant, location extraction, severity estimate.
- Relevant articles are ingested as `CrisisEvent` with `source="api"`, `category="flood"`.
- Appears in morning report under "Zdarzenia z ostatnich 12h".

**Note:** Filtering "what the bot already reported" — handled by the URL hash deduplication table.

### 4.2 Alert RCB Integration

- IMGW publishes official hydro warnings via RCB-compatible RSS / API.
- New plugin: polls RCB hydro alerts for Warmińsko-Mazurskie.
- Alerts are shown on map as a distinct layer and appear at top of morning report.

### 4.3 Draft Communications for PCZK/JST

- When a situation reaches alarm level, the LLM generates a draft alert text for the duty officer.
- Template: `"Na podstawie danych IMGW, stacja {name} osiągnęła stan alarmowy ({level} cm). Zalecamy podjęcie następujących działań: ..."`.
- Draft is shown in operator panel under "Propozycja komunikatu" — duty officer edits and confirms before anything is sent.

**Deliverable:** Morning report now includes media mentions alongside official IMGW data. Duty officer gets a draft communication ready to sign.

---

## Phase 5 — Predictive Model +12h (2-4 weeks, requires Phase 1 data)

**Goal:** Each monitored station shows a projected level in 12 hours with confidence interval.

### 5.1 Data prerequisites (from Phase 1)

- Need at least 14 days of 30-min readings in `gauge_readings` to train any useful model.
- Phase 5 cannot start before Phase 1 has been running for 2 weeks.

### 5.2 Station Nowakowo / Elbląg / Żukowo — Sea Level Integration

These three stations are on or near the Vistula Lagoon (Zalew Wiślany) and are influenced by Baltic sea level pressure. A standard rainfall-runoff model is insufficient.

- Sea level data source: IMGW provides sea level for Baltic stations; also available from BAŁTYK model at ICM (Interdyscyplinarne Centrum Modelowania UW).
- Add `plugins/sea_level.py` polling hourly sea-level forecasts for Bałtyk region.
- These forecasts feed the station-specific models for these three stations.

### 5.3 Prediction Model

**MVP approach (no specialist ML team required):**
- Linear regression on last 24h of readings + precipitation forecast (open-meteo.com API is free for non-commercial use; may need to verify terms with the voivodeship).
- Separate intercept for the sea-level-influenced stations.
- Output: point estimate + ±1σ confidence band for +3h, +6h, +12h.
- Displayed as dashed extension on the station chart.

**Better approach (if data scientist available):**
- LSTM or simple Prophet model per station, trained on historical readings.
- Retrained weekly on the full DB history.

### 5.4 Probability of Threshold Breach

- Given the +12h projection + confidence interval, compute P(level > warning_threshold) and P(level > alarm_threshold).
- Shown in the operator panel station table as a percentage badge.
- If P(alarm) > 30% → proactive alert to duty officer before the threshold is actually crossed.

**Deliverable:** Chart shows projected level for next 12h with confidence band. Operator panel shows probability of reaching warning/alarm.

---

## Technical Decisions

### Database

SQLite is fine. The gauge reading volume for W-M (roughly 60-80 stations × 48 readings/day × 90 days ≈ 250k rows) fits comfortably in SQLite. No Postgres migration needed for Phase 1-3.

### Scheduler

Use `apscheduler` (async-compatible) added to the FastAPI lifespan. Single-process assumption holds for the voivodeship deployment. No Celery/Redis needed.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
```

### PDF Generation

Use `WeasyPrint` — pure Python, no LaTeX dependency, produces clean HTML→PDF. The report is generated from a Jinja2 template (reusing the existing Python stack, no new tools).

### Notification delivery

- Email: `aiosmtplib` (async SMTP, no thread blocking).
- Telegram: direct HTTPS to Bot API (no heavy SDK).
- No SMS in Phase 2 (adds cost and carrier complexity; can add later if client requires).

### Frontend for charts

- Chart.js loaded from CDN in the existing no-build-step frontend.
- Same approach as current Leaflet — no npm/bundler.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| IMGW API rate limits at 10-min polling | Medium | Medium | Request special access via Wojewoda as mentioned in spec; fall back to 30-min until granted |
| Sea level data API availability | Medium | High (for Phase 5) | ICM data is free/open; evaluate IMGW Baltic service as backup |
| Google News RSS blocked or noisy | Medium | Low | Phase 4 is enhancement, not core; alternative: scrape local W-M news portals |
| Client requires SMS before Phase 2 complete | Low | Medium | Integrate Twilio/SMSAPI early in Phase 2 if raised |
| ML model accuracy insufficient for operational use | Medium | Medium | Phase 5 framed as "projection aid" not "prediction"; confidence intervals make uncertainty explicit |
| Data loss if SQLite WAL corrupts | Low | High | Nightly backup of sentinel.db via cron on the voivodeship server |

---

## Effort Summary

| Phase | Scope | Estimated effort |
|---|---|---|
| Phase 1 | Voivodeship switch + time-series + trend alarm + charts | 4-5 days |
| Phase 2 | Scheduled reports + PDF + email + Telegram | 4-5 days |
| Phase 3 | WCZK operator panel | 3-4 days |
| Phase 4 | Media monitoring + RCB + draft comms | 5-7 days |
| Phase 5 | +12h prediction + probability | 10-14 days (after data matures) |

Total to Phase 4 (full spec minus ML): ~3.5 weeks of focused development.  
Phase 5 (ML) requires 2-week data maturation period + ~2 weeks development.

---

## Suggested Next Steps

1. **Call/email the client** to confirm: (a) which features are must-have for a first delivery, (b) their deployment environment details (internet access? internal SMTP? Telegram approved?), (c) timeline expectations.
2. **Create a `wczk` branch** from `main` — Phase 1 changes (voivodeship filter, DB table, trend alarm) are safe to develop there without touching Lublin demo.
3. **Phase 1 is shippable without any client interaction** — the voivodeship switch + charts is a low-risk code change we can start immediately.
