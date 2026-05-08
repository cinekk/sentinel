# AI Assistant — View Configuration

## Purpose

Translates a natural-language query into a dashboard view configuration:
which layers to show/hide, which attributes to display in popups, and
which attribute to highlight as a critical metric on the map.

The LLM cannot hallucinate invalid layer IDs — the response is constrained
by a JSON Schema enum built dynamically from the layer catalog.

---

## Endpoints

### `POST /api/assistant/configure-view`

**Request:**
```json
{
  "query": "Pokaż tylko szpitale i straż pożarną",
  "crisis_context": "Pożar zakładu chemicznego w Puławach"  // optional
}
```

**Response:**
```json
{
  "layers_visible": ["hospitals", "fire_stations", "lublin_boundary"],
  "layers_hidden": ["schools", "social", "air_quality", "events", "simulation_threat", "transport_units"],
  "popup_attributes": {
    "hospitals": ["beds_available_estimate", "has_sor", "icu_oiom_beds"]
  },
  "critical_attribute": {
    "layer_id": "hospitals",
    "attribute": "beds_available_estimate",
    "thresholds": [
      {"value": 10, "color": "#ef4444"},
      {"value": 50, "color": "#f97316"},
      {"color": "#10b981"}
    ],
    "label": "Dostępne łóżka"
  },
  "explanation": "Wybieram szpitale i straż jako kluczowe zasoby w zdarzeniu chemicznym.",
  "model": "qwen/qwen3-30b-a3b-instruct-2507"
}
```

Every layer ID must appear in exactly one of `layers_visible` or `layers_hidden`.
`critical_attribute` is `null` when the LLM does not identify a key metric.
`model` is `"fallback"` when the LLM call fails (see Fallback section).

### `GET /api/assistant/layer-schemas`

Returns the full layer catalog — all `LayerSchema` objects with their
`AttributeMeta` entries. Used by the frontend to know what popup attributes
are available per layer.

### `GET /api/assistant/layer-schemas/{layer_id}`

Returns a single layer schema. 404 if `layer_id` is unknown.

---

## Request Flow

```
POST /api/assistant/configure-view
  │
  ├── validate: query must be non-empty (400 if blank)
  │
  ├── services/layer_meta.py → get_all_schemas()
  │     Returns list of LayerSchema for all 9 registered layers
  │
  ├── services/assistant.py → _build_view_config_schema(layer_ids)
  │     Builds JSON Schema with layers_visible/layers_hidden constrained
  │     to enum of known layer IDs. strict=True, additionalProperties=False.
  │
  ├── services/openrouter.py → chat_completion(messages, json_schema=...)
  │     POST https://openrouter.ai/api/v1/chat/completions
  │     temperature=0.2, max_tokens=4096
  │     response_format.type = "json_schema"
  │     │
  │     ├── on success → _parse_json_defensive(content)
  │     │     Strips <think>…</think>, /no_think prefix, markdown fences
  │     │     Extracts outermost {...} and calls json.loads()
  │     │
  │     └── on any exception → _fallback_config(query)  [keyword matching]
  │
  └── services/assistant.py → _validate_and_normalize(raw, schemas)
        Strips any layer IDs not in catalog
        Ensures every layer ID is in exactly one list
        Constructs critical_attribute with hardcoded color thresholds
        Returns final response dict
```

---

## Layer Catalog

Nine layers are currently registered in `services/layer_meta.py`:

| layer_id | Label | Key attributes |
|---|---|---|
| `hospitals` | Szpitale | beds_available_estimate, has_sor, icu_oiom_beds, helipad |
| `schools` | Szkoły | capacity |
| `social` | Placówki Społeczne (DPS) | capacity, beds |
| `fire_stations` | Jednostki PSP/OSP | unit (PSP/OSP) |
| `lublin_boundary` | Granica województwa | name |
| `air_quality` | Jakość powietrza (GIOŚ) | overall_index, pm25_index, pm10_index |
| `events` | Zdarzenia kryzysowe | _(no attributes defined)_ |
| `simulation_threat` | Strefa zagrożenia (symulacja) | pm25, pm10, semi_major_km, elapsed_min |
| `transport_units` | Transport Sanitarny | unit_type, status_label |

---

## Three-Way Sync Requirement

The layer ID enum is derived at runtime from `layer_meta.py`, so adding a
layer there automatically makes it available to the LLM. However, three
things must stay in sync manually:

1. **`_build_view_config_schema()`** — enum is built from `get_all_schemas()`, no action needed
2. **`services/layer_meta.py`** — source of truth; add `LayerSchema` here to register a layer
3. **`_LAYER_KEYWORDS`** in `services/assistant.py` — fallback keyword dict must include the new layer ID

If `_LAYER_KEYWORDS` is missing a layer, the fallback will never show that
layer — it silently falls through to `visible = sorted(all_ids)` (show all).

---

## Fallback Mechanism

When `chat_completion()` raises any exception (network error, API key missing,
empty response, JSON parse failure), `_fallback_config(query)` runs instead.

The fallback uses `_LAYER_KEYWORDS` — a dict of `layer_id → [polish/english keywords]` —
to decide which layers to show. It understands three query intents:
- **hide mode** (`ukryj`, `schowaj`, `hide`) — matched layers → hidden
- **show-only mode** (`tylko`, `only`) — matched layers → visible, rest → hidden
- **scenario shortcuts** — fire/hazmat, smog, flood queries map to preset layer groups

Fallback responses always return `"model": "fallback"`. Monitor for this in
production — a spike indicates OpenRouter connectivity issues.

---

## Prompt

`SYSTEM_PROMPT` in `services/assistant.py` is in Polish. It instructs the model to:
- Select which layers to show and which to hide
- Place every layer in exactly one list
- Respond briefly in Polish in the `explanation` field

**Do not change `SYSTEM_PROMPT` without explicit instruction.** Changes cascade
to all downstream behavior — layer selection logic, popup attribute choices,
and critical attribute identification all depend on how the model interprets
the system instructions.

If `crisis_context` is provided, it is appended to the user message (not the
system prompt) to keep user-controlled input out of the trusted system role.

---

## OpenRouter Client

`services/openrouter.py` handles all LLM communication. Key behaviours:

- **Model**: configured via `OPENROUTER_MODEL` env var (defaults in `config.py`)
- **Timeout**: 60s per request
- **Qwen3 quirk**: some model variants return `content: null` with the JSON
  in the `reasoning` field — the client checks both fields before failing
- **Defensive parsing**: `_parse_json_defensive()` handles `<think>` wrappers,
  `/no_think` prefixes, and markdown-fenced JSON that some models emit

The client injects `_model` into the parsed response dict so the final
response can report which model was actually used.
