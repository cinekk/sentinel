# Voice Briefing Pipeline

## Purpose

Generates a spoken situational briefing: assembles live crisis state into
Polish text, synthesizes it via ElevenLabs TTS, and returns MP3 audio with
per-word timestamps for karaoke-style frontend synchronization.

The text generation is **deterministic** — no LLM involved. Numbers, names,
and distances come directly from API data. Do not add LLM calls here.

---

## Endpoints

### `POST /api/voice/briefing`

The main briefing endpoint. No request body.

**Response (`BriefingResponse`):**
```json
{
  "audio_base64": "<mp3 base64>",
  "words": [
    {"word": "Briefing", "start": 0.0,   "end": 0.412},
    {"word": "sytuacyjny,", "start": 0.462, "end": 1.105},
    ...
  ],
  "text": "Briefing sytuacyjny, godzina 14:32.\n\nAktywne zagrożenie: ...",
  "duration_seconds": 38.4,
  "tts_synthesized": true
}
```

`tts_synthesized: false` means TTS failed — audio is empty, word timings are
synthetic (linear at 160 wpm). The frontend karaoke animation still works.

### `POST /api/voice/speak`

Synthesizes arbitrary text. Used by the demo controller for scripted announcements.

**Request:** `{"text": "..."}`  
**Response:** `{"audio_base64": "<mp3 base64>"}`

Returns HTTP 422 if `text` is empty. Does **not** fall back — raises exception
on TTS failure (caller handles it).

### `GET /api/voice/health`

Checks ElevenLabs API key presence and reachability. Calls
`GET /v1/voices/{VOICE_ID}` (no quota cost).

**Response:**
```json
{"ok": true, "api_key_present": true, "api_key_masked": "sk_e…labs", "voice_id": "onwK4e9ZLuTAKqWW03F9", "voice_name": "Daniel"}
```

Returns `ok: false` with `error` field on missing key, HTTP error, timeout,
or connection failure. Never raises — always returns a dict.

---

## Briefing Flow

```
POST /api/voice/briefing
  │
  ├── _build_briefing_text()
  │     │
  │     ├── store.list_active()           — active crisis events (in-memory)
  │     ├── registry.get("simulation_threat").state — sim plugin state
  │     ├── registry.get("flood_scenario").state    — flood plugin state
  │     │
  │     ├── [parallel asyncio tasks]
  │     │     ├── _load_resource_features()  — hospitals/schools/social GeoJSON
  │     │     ├── get_air_quality_data()     — GIOŚ live readings
  │     │     └── assess_hospitals()         — flood risk per hospital (if flood running)
  │     │
  │     ├── facilities_in_zones(active_crises, features)
  │     │     Spatial intersection: which facilities fall in crisis zones
  │     │
  │     └── generate_briefing_text(BriefingContext)
  │           Deterministic Polish text from template (services/briefing.py)
  │           Falls back to "Briefing niedostępny..." on any exception
  │
  └── synthesize_with_timestamps(text)    — services/tts.py
        ElevenLabs /with-timestamps → audio_base64 + per-char alignment
        _aggregate_words() → per-word timings
        Falls back to _fake_timings() on any TTS failure
```

---

## Text Generation (`services/briefing.py`)

`generate_briefing_text(ctx: BriefingContext)` builds a Polish text string
by concatenating sentence blocks, joined by `\n\n`.

**Always present:**
- Timestamp: `"Briefing sytuacyjny, godzina HH:MM."`
- Closing: `"Koniec briefingu."`
- If no active crises and no flood: `"Brak aktywnych zagrożeń. System monitoringu w trybie czuwania."`

**Per active crisis** (iterates `ctx.active_crises`):
- Crisis name and coordinates
- Evacuation radius + warning radius
- Count of affected facilities (hospitals / schools / social) in threat zone
- Count requiring evacuation + nearest evacuee name + distance
- Nearest air quality station: PM2.5 value vs. 25 µg/m³ norm
- Nearest weather station: wind direction + speed

**Flood scenario** (if `ctx.flood_scenario_state.running == True`):
- Narrative time offset in minutes
- Hospitals requiring evacuation (up to 3 names)
- Hospitals at risk (up to 3 names)
- Or: "Szpitale w regionie powodzi pozostają operacyjne."

`BriefingContext` fields:

| Field | Source | Used for |
|---|---|---|
| `active_crises` | `crisis_store.list_active()` | Crisis blocks |
| `affected` | `spatial.facilities_in_zones()` | Facility counts, evacuation |
| `sim_state` | `SimulationPlugin.state` | (available, not currently used in text) |
| `flood_scenario_state` | `FloodScenarioPlugin.state` | Flood block trigger |
| `flood_hospitals` | `flood_assessment.assess_hospitals()` | Hospital status names |
| `air_quality` | `get_air_quality_data()` (GIOŚ) | PM2.5 near crisis |
| `weather` | `WEATHER_DATA` (static in v1_layers.py) | Wind near crisis |

---

## TTS (`services/tts.py`)

**Constants (hardcoded — do not change without testing):**

| Constant | Value |
|---|---|
| `VOICE_ID` | `onwK4e9ZLuTAKqWW03F9` (Daniel — male narration) |
| `MODEL_ID` | `eleven_multilingual_v2` |
| `OUTPUT_FORMAT` | `mp3_44100_128` |
| `TIMEOUT_S` | `20` |

**API call:**  
`POST https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/with-timestamps`

Voice settings: `stability=0.7`, `similarity_boost=0.8`.

The `/with-timestamps` endpoint returns `audio_base64` (MP3) and `alignment`
(per-character start/end times). `_aggregate_words()` converts character-level
alignment to word-level `WordTiming` objects by scanning for space boundaries.

**Fallback (`_fake_timings()`):**  
Returns `TtsResult(audio_base64="", tts_synthesized=False)` with synthetic
timings at 160 wpm with 50ms gaps. Triggered by:
- `ELEVENLABS_API_KEY` not set
- HTTP error from ElevenLabs
- Timeout (20s)
- Connection error
- Empty `audio_base64` in response
- Missing `alignment` in response

---

## Error Handling Summary

| Layer | What fails | Behaviour |
|---|---|---|
| `_build_briefing_text()` | Any exception | Returns hardcoded fallback string |
| `synthesize_with_timestamps()` | API key missing | Returns fake timings immediately |
| `synthesize_with_timestamps()` | HTTP / timeout / connect error | Logs error, returns fake timings |
| `voice_briefing()` | TTS fails | Returns `BriefingResponse` with `tts_synthesized=false` |
| `voice_health()` | Anything | Always returns dict, never raises |

The `/briefing` endpoint **never returns HTTP 5xx** — it always returns a
`BriefingResponse`, possibly with empty audio and `tts_synthesized: false`.
Monitor for `tts_synthesized: false` in production to catch ElevenLabs issues.
