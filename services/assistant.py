"""
AI Assistant service — translates natural-language queries into dashboard
view configurations. Uses json_schema structured output with enum-constrained
layer IDs so the LLM cannot hallucinate invalid layer names.
"""
from __future__ import annotations

import logging

from services.layer_meta import get_all_schemas, LayerSchema
from services.openrouter import chat_completion

logger = logging.getLogger(__name__)


def _build_view_config_schema(layer_ids: list[str]) -> dict:
    """Build a JSON Schema for ViewConfig with layer IDs as enum."""
    layer_enum = {"type": "string", "enum": layer_ids}
    return {
        "name": "view_config",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "layers_visible": {"type": "array", "items": layer_enum},
                "layers_hidden": {"type": "array", "items": layer_enum},
                "popup_attributes": {
                    "type": "object",
                    "additionalProperties": {"type": "array", "items": {"type": "string"}},
                },
                "critical_attribute_layer_id": {"type": ["string", "null"]},
                "critical_attribute_key": {"type": ["string", "null"]},
                "critical_attribute_label": {"type": ["string", "null"]},
                "explanation": {"type": "string"},
            },
            "required": [
                "layers_visible", "layers_hidden", "popup_attributes",
                "critical_attribute_layer_id", "critical_attribute_key",
                "critical_attribute_label", "explanation",
            ],
            "additionalProperties": False,
        },
    }


SYSTEM_PROMPT = """\
Asystent mapy SENTINEL. Wybierz które warstwy pokazać a które ukryć.

Warstwy: {layer_ids}

Każda warstwa MUSI być w layers_visible ALBO layers_hidden. Odpowiedz krótko po polsku w explanation.
"""


async def configure_view(query: str, crisis_context: str | None = None) -> dict:
    schemas = get_all_schemas()
    layer_ids = [s.layer_id for s in schemas]
    system = SYSTEM_PROMPT.format(layer_ids=", ".join(layer_ids))
    view_schema = _build_view_config_schema(layer_ids)

    user_msg = query
    if crisis_context:
        user_msg = f"{query}\n\nAktywny kontekst kryzysowy: {crisis_context}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    try:
        result = await chat_completion(
            messages, temperature=0.2, max_tokens=4096, json_schema=view_schema,
        )
    except Exception:
        logger.exception("OpenRouter call failed, returning fallback config")
        return _fallback_config(query)

    return _validate_and_normalize(result, schemas)


def _validate_and_normalize(raw: dict, schemas: list[LayerSchema]) -> dict:
    all_ids = {s.layer_id for s in schemas}

    visible = [lid for lid in raw.get("layers_visible", []) if lid in all_ids]
    hidden = [lid for lid in raw.get("layers_hidden", []) if lid in all_ids]

    if not visible:
        visible = list(all_ids)
        hidden = []

    for lid in all_ids:
        if lid not in visible and lid not in hidden:
            hidden.append(lid)

    popup_attrs: dict[str, list[str]] = {}
    for lid, attrs in raw.get("popup_attributes", {}).items():
        if lid in all_ids and isinstance(attrs, list):
            popup_attrs[lid] = attrs

    critical = None
    crit_layer = raw.get("critical_attribute_layer_id")
    crit_key = raw.get("critical_attribute_key")
    if crit_layer and crit_key and crit_layer in all_ids:
        critical = {
            "layer_id": crit_layer,
            "attribute": crit_key,
            "thresholds": [
                {"value": 10, "color": "#ef4444"},
                {"value": 50, "color": "#f97316"},
                {"color": "#10b981"},
            ],
            "label": raw.get("critical_attribute_label") or crit_key,
        }

    return {
        "layers_visible": visible,
        "layers_hidden": hidden,
        "popup_attributes": popup_attrs,
        "critical_attribute": critical,
        "explanation": raw.get("explanation", ""),
        "model": raw.get("_model", "unknown"),
    }


_LAYER_KEYWORDS: dict[str, list[str]] = {
    "hospitals": ["szpital", "hospital", "łóżk", "sor", "oit", "oiom", "lecznic", "medycz"],
    "schools": ["szkoł", "school", "uczeń", "uczni", "oświat", "edukac"],
    "social": ["dps", "społeczn", "opiekuńcz", "pomoc", "senior"],
    "fire_stations": ["straż", "fire", "psp", "osp", "strażak", "pożarn"],
    "air_quality": ["powietrze", "smog", "pm2.5", "pm10", "gioś", "jakość powietrza"],
    "simulation_threat": ["symulac", "zagroż", "strefa", "pluma", "dyspersj"],
    "lublin_boundary": ["granica", "powiat", "województw"],
    "events": ["zdarzen", "event", "kryzys", "incydent"],
    "transport_units": ["transport", "karetk", "ambulans", "sanitarn"],
}


def _fallback_config(query: str) -> dict:
    q = query.lower()
    all_ids = set(_LAYER_KEYWORDS.keys())

    hide_mode = any(w in q for w in ("ukryj", "schowaj", "wyłącz", "hide"))
    show_only = any(w in q for w in ("tylko", "only", "pokaż tylko", "same"))

    matched = [lid for lid, kws in _LAYER_KEYWORDS.items()
               if any(kw in q for kw in kws)]

    if matched and hide_mode:
        visible = sorted(all_ids - set(matched))
        hidden = matched
    elif matched and show_only:
        visible = matched + (["lublin_boundary"] if "lublin_boundary" not in matched else [])
        hidden = sorted(all_ids - set(visible))
    elif any(w in q for w in ("pożar", "fire", "hazmat", "chemi")):
        visible = ["hospitals", "fire_stations", "simulation_threat", "lublin_boundary"]
        hidden = sorted(all_ids - set(visible))
    elif any(w in q for w in ("smog", "powietrze", "pm2.5", "pm10")):
        visible = ["hospitals", "schools", "social", "air_quality", "lublin_boundary"]
        hidden = sorted(all_ids - set(visible))
    elif any(w in q for w in ("powód", "flood", "woda", "rzek")):
        visible = ["hospitals", "schools", "social", "fire_stations", "lublin_boundary"]
        hidden = sorted(all_ids - set(visible))
    else:
        visible = sorted(all_ids)
        hidden = []

    critical = None
    if "hospitals" in visible and any(w in q for w in ("pożar", "fire", "hazmat", "łóżk", "kryzys")):
        critical = {
            "layer_id": "hospitals",
            "attribute": "beds_available_estimate",
            "thresholds": [
                {"value": 10, "color": "#ef4444"},
                {"value": 50, "color": "#f97316"},
                {"color": "#10b981"},
            ],
            "label": "Dostępne łóżka",
        }

    return {
        "layers_visible": visible,
        "layers_hidden": hidden,
        "popup_attributes": {},
        "critical_attribute": critical,
        "explanation": "Konfiguracja domyślna (brak połączenia z AI).",
        "model": "fallback",
    }
