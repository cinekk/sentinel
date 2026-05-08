# Stage 4 — Outputs

**Pipeline position:** Sources → Observations → Reactions → **Outputs**

Outputs are everything downstream that delivers processed data to a human or external system: map layers, voice briefings, REST APIs, PDF reports, and alerting channels.

---

## 1. Overview

Outputs are triggered by three distinct mechanisms:

**Pull outputs (HTTP request)** — the client asks; the system responds.
- Map layers (`GET /api/layers/{layer_id}/geojson`)
- Crisis zone GeoJSON (`/api/v1/crisis/zones-geojson`, etc.)
- REST event list (`GET /api/events`)
- Voice briefing (`POST /api/voice/briefing`)
- AI-driven view configuration (`POST /api/assistant/configure-view`)

**Push outputs (event-driven)** — an `AlertDispatchHook` fires when a new high/critical event is written; the output delivers immediately.
- Email alerts (`EmailAlert`)
- Telegram alerts (`TelegramAlert`)

**Push outputs (scheduled)** — APScheduler fires at a fixed time; the output renders and delivers.
- Morning report (06:30) → PDF + email
- Evening report (18:30) → PDF + email

> **Status note:** Pull outputs are fully operational today. Push outputs (both event-driven and scheduled) are TARGET DESIGN — no scheduler is installed and no delivery plugins exist yet.

---

## 2. Current outputs (existing today)

### 2a. Map layers

`GET /api/layers/{layer_id}/geojson`

Routes through the plugin registry in `routers/layers.py`. When a request arrives, `registry.get(layer_id)` returns the registered plugin (or 404 if unknown), and `plugin.fetch()` is called to produce a fresh GeoJSON FeatureCollection. The registry also exposes `GET /api/layers` (no suffix) which returns the full catalog as `list[LayerMeta]`, including `layer_id`, display name, data type, and `last_updated` timestamp.

Every registered plugin is served identically — live API plugins (IMGW, GIOŚ), static file plugins (schools, hospitals), computed plugins (HospitalStatusPlugin), and the simulation plugin all expose the same interface.

### 2b. Crisis zone GeoJSON

Three crisis-specific GeoJSON endpoints, consumed primarily by Grafana:

- `GET /api/v1/crisis/zones-geojson` — warn/evac radius polygons for active crisis events
- `GET /api/v1/crisis/affected-geojson` — affected facility points (hospitals, schools, social)
- `GET /api/v1/crisis/fires-geojson` — active fire event points

These derive from `services/crisis_store.py` (currently an in-memory dict — see de-facto analysis for the planned persistence fix).

### 2c. REST API

`GET /api/events` returns a flat JSON list of `EventRow` objects (time, latitude, longitude, category, severity, status, description). This is the Grafana-compatible write path: the dashboard polls this endpoint for its panels.

`GET /api/health` returns `{ "status": "ok", "plugins": [...] }`. Used by the Caddy health check and uptime monitoring.

### 2d. Voice briefing

`POST /api/voice/briefing` → ElevenLabs TTS → `BriefingResponse` (MP3 base64 + word timings + plain text)

The endpoint assembles a `BriefingContext` from four parallel async calls:
1. Active crisis events from `crisis_store`
2. Facilities in crisis zones (hospitals, schools, social) via `services/spatial.facilities_in_zones()`
3. Air quality readings from the GIOŚ plugin
4. Hospital flood status from `services/flood_assessment.assess_hospitals()` (when a flood scenario is running)

`services/briefing.generate_briefing_text()` renders deterministic Polish-language text from this context — no LLM involved. Only the output of that function is passed to `services/tts.synthesize_with_timestamps()`. This is a hard rule: raw user input, crisis payload text, and LLM output must never reach the TTS call (SSML injection risk).

If ElevenLabs is unreachable, the endpoint falls back to synthetic word timings at 160 WPM with `tts_synthesized: false`.

For full detail on the briefing text structure, section ordering, and TTS integration: see `docs/features/voice-briefing.md`.

`GET /api/voice/health` checks ElevenLabs API key presence and voice endpoint reachability without consuming synthesis quota.

### 2e. AI-driven layer configurator

`POST /api/assistant/configure-view` translates a natural-language query into a dashboard `ViewConfig`: which layers to show/hide, which popup attributes to display, and which attribute to highlight as a critical metric.

**Request:**
```json
{
  "query": "Pokaż tylko szpitale i straż pożarną",
  "crisis_context": "Pożar zakładu chemicznego w Puławach"
}
```

**Response fields:** `layers_visible`, `layers_hidden`, `popup_attributes`, `critical_attribute` (with color thresholds), `explanation`, `model`.

Every layer ID must appear in exactly one of `layers_visible` or `layers_hidden`. `critical_attribute` is `null` when the model does not identify a key metric. `model` is `"fallback"` when the LLM call fails.

**Request flow:**
1. `services/layer_meta.get_all_schemas()` — fetches all registered `LayerSchema` objects
2. `services/assistant._build_view_config_schema(layer_ids)` — builds a JSON Schema with `layers_visible`/`layers_hidden` constrained to an enum of known layer IDs (`strict=True`, `additionalProperties=False`)
3. `services/openrouter.chat_completion(messages, json_schema=...)` — POST to OpenRouter, `temperature=0.2`, structured JSON output
4. `services/assistant._validate_and_normalize(raw, schemas)` — trust boundary: strips unknown layer IDs, ensures every layer is in exactly one list, constructs `critical_attribute` with hardcoded color thresholds

**Three-way sync requirement.** Three things must stay in sync when a layer is added:
1. `services/layer_meta.py` — source of truth; add a `LayerSchema` here
2. `services/assistant._build_view_config_schema()` — derives the enum from `get_all_schemas()`, so no manual action needed
3. `_LAYER_KEYWORDS` in `services/assistant.py` — fallback keyword dict; must include the new layer ID or the fallback will never show it

**Fallback mechanism.** When `chat_completion()` raises any exception (network error, missing key, JSON parse failure), `_fallback_config(query)` runs instead using `_LAYER_KEYWORDS`. It understands three query intents: hide mode (`ukryj`/`schowaj`/`hide`), show-only mode (`tylko`/`only`), and scenario shortcuts (fire/hazmat, smog, flood → preset layer groups). Responses always carry `"model": "fallback"` — a spike in production indicates OpenRouter connectivity issues.

**Security note.** The configure-view assistant is a UI configurator, not a crisis analyst. It decides display configuration; it does not analyze threats, assert facts about the situation, or generate new information. `crisis_context` is appended to the user message (not the system prompt) so that user-controlled input never reaches the trusted system role.

The other assistant endpoints — `GET /api/assistant/layer-schemas` (full catalog) and `GET /api/assistant/layer-schemas/{layer_id}` (single layer, 404 if unknown) — expose the layer attribute metadata that the frontend uses to build popup configurations.

---

## 3. Target output plugin types

> **TARGET DESIGN** — none of the following exists yet. This section documents the planned abstraction and its concrete implementations.

Three base classes define the full output surface:

```python
class LayerPlugin(BasePlugin):
    """Existing behavior — serves GeoJSON on HTTP request. No changes."""
    async def fetch(self) -> dict: ...

class ReportPlugin(ABC):
    """Renders a report as bytes (PDF) or text (Markdown / email body)."""
    report_id: str

    async def generate(self, context: ReportContext) -> ReportOutput: ...

class AlertPlugin(ABC):
    """Delivers a notification to a channel."""
    channel_id: str  # "email", "telegram", "webhook"

    async def send(self, subject: str, body: str, attachments: list[bytes] = []) -> None: ...
```

### 3a. LayerPlugin

This is the existing `BasePlugin`. No interface changes. All current plugins already satisfy this contract. Documented here for completeness as the first output plugin type.

### 3b. ReportPlugin

**`WCZKMorningReport`** (`report_id: "wczk_morning"`)

Content structure:
- IMGW warnings: stations at warning or alarm level (from `observations` table, latest per station)
- Events in the last 12 hours: EventRow rows grouped by category and severity
- High-risk districts: spatial join of alarm-level gauges against administrative boundary polygons

Renders to PDF via WeasyPrint + Jinja2 template. Also renders to plain text for the email body.

Triggered by: APScheduler at 06:30 Europe/Warsaw, OR `POST /api/wczk/reports/generate?type=morning` for on-demand.

**`WCZKEveningReport`** (`report_id: "wczk_evening"`)

Content structure:
- Full-day event summary (00:00–18:30): counts by category and severity
- Manual operator notes (entered via the WCZK panel during the day)
- Trend extrapolation: linear regression on river level readings → projected levels for the next 12 hours

Triggered by: APScheduler at 18:30 Europe/Warsaw, OR `POST /api/wczk/reports/generate?type=evening`.

### 3c. AlertPlugin

**`EmailAlert`** (`channel_id: "email"`)

Sends HTML email with an optional PDF attachment (the report generated alongside the alert). Uses `aiosmtplib` for async SMTP. Configuration: `ALERT_EMAIL_HOST`, `ALERT_EMAIL_PORT`, `ALERT_EMAIL_USER`, `ALERT_EMAIL_PASSWORD`, `ALERT_EMAIL_RECIPIENTS` (comma-separated) in `config.py`.

**`TelegramAlert`** (`channel_id: "telegram"`)

Direct HTTPS POST to the Telegram Bot API (`sendMessage`). Intended for one-line threshold alerts — river level at alarm, high/critical event created — where low latency matters more than formatting. Configuration: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` in `config.py`.

Both plugins are triggered by `AlertDispatchHook` in Stage 3. The hook fires on every new `EventRow` where `severity in ("high", "critical")`. For alarm-level events it also calls `services/openrouter.py` to draft a communication for PCZK/JST (see section 4).

### 3d. WCZK Operator Panel

Route `/wczk` — FastAPI-served HTML, no build step, same pattern as the current Leaflet frontend. The panel is the primary day-to-day interface for the duty officer.

Planned sections:
- **Status strip** — current alert level color, active event count, time of last report
- **Active alerts** — list of high/critical EventRows with an Acknowledge button per row
- **Station table** — IMGW gauge readings with trend arrows (up/down/stable), color-coded by alert level
- **Report preview** — inline PDF viewer for the last generated morning/evening report
- **Manual notes** — free-text input saved to DB; included in the evening report
- **Settings** — alert recipient list CRUD, notification preferences

API endpoints backing the panel:
- `POST /api/wczk/alerts/{event_id}/acknowledge` — sets event `status` to `"investigating"`
- `GET /api/wczk/reports` — list generated reports with download links
- `POST /api/wczk/reports/generate` — on-demand report trigger
- `GET/POST /api/wczk/recipients` — alert recipient management
- `POST /api/wczk/notes` — save manual operator note

---

## 4. LLM-driven outputs (planned expansion)

> **TARGET DESIGN**

The existing `configure-view` assistant is deliberately narrow in scope — it configures layer visibility only. Two planned expansions use the same `services/openrouter.py` client with new callers:

**Draft communications for PCZK/JST**

When `AlertDispatchHook` fires on an alarm-level event, it calls OpenRouter with a structured prompt that receives the event description, affected facilities, and current gauge levels. The model drafts a short formal communication for the county crisis management center (PCZK) or local government unit (JST). The draft is attached to the email alert as a `.txt` file and displayed in the WCZK panel for operator review before sending. The operator sends it; the system never sends communications autonomously.

**Media article classification**

A planned Stage 1 plugin (`MediaMonitoringPlugin`) will poll regional news RSS feeds. When a new article arrives, `AlertDispatchHook` classifies it via OpenRouter (crisis-relevant / not relevant, inferred category and severity). Articles classified as crisis-relevant create an EventRow with `source="media"`. This uses the existing ingest write path with no changes to that path.

Both expansions follow the same pattern: new caller → existing `services/openrouter.py` client. No new LLM service files.
