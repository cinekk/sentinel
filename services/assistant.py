"""
AI Assistant service — translates natural-language situational descriptions
into dashboard view configurations (which layers to show, which attributes
to display in popups, and which numeric attribute to use for color-coding).
"""
from __future__ import annotations

import json
import logging

from services.layer_meta import get_all_schemas, LayerSchema
from services.openrouter import chat_completion

logger = logging.getLogger(__name__)


def _build_layer_catalog(schemas: list[LayerSchema]) -> str:
    """Build a compact text catalog of layers + attributes for the system prompt."""
    parts: list[str] = []
    for s in schemas:
        if not s.attributes:
            continue
        attr_lines = []
        for a in s.attributes:
            extra = ""
            if a.critical_candidate:
                extra = " [NUMERIC — can be critical_attribute]"
            desc = f" — {a.description}" if a.description else ""
            attr_lines.append(f"    - {a.key} ({a.label}, {a.type}){desc}{extra}")
        attrs_block = "\n".join(attr_lines)
        parts.append(f"  Layer: {s.layer_id} — \"{s.label}\"\n  Opis: {s.description}\n  Atrybuty:\n{attrs_block}")
    return "\n\n".join(parts)


SYSTEM_PROMPT = """\
Jesteś asystentem AI platformy SENTINEL — systemu świadomości sytuacyjnej dla województwa lubelskiego.

Twoim zadaniem jest konfiguracja widoku dashboardu na podstawie opisu sytuacji kryzysowej lub analitycznej od operatora.

## Dostępne warstwy i atrybuty

{layer_catalog}

## Zasady

1. Na podstawie opisu sytuacji wybierz RELEWANTNE warstwy (layers_visible) i ukryj pozostałe (layers_hidden).
2. Dla każdej widocznej warstwy z atrybutami, wybierz 3-8 NAJWAŻNIEJSZYCH atrybutów do popup_attributes. Zawsze uwzględnij "name".
3. Jeśli sytuacja wymaga wizualizacji numerycznej (np. dostępne łóżka, pojemność), ustaw critical_attribute z progami kolorów.
4. Progi (thresholds) to lista obiektów {{"value": <max>, "color": "<hex>"}} posortowana rosnąco. Ostatni próg bez value to kolor domyślny (powyżej najwyższego progu). Kolory: czerwony #ef4444 (krytycznie mało), pomarańczowy #f97316 (mało), zielony #10b981 (ok).
5. Odpowiadaj WYŁĄCZNIE po polsku.
6. explanation — krótkie (1-2 zdania) wyjaśnienie dlaczego taki widok.

## Scenariusze referencyjne

- Pożar/HAZMAT: szpitale (łóżka, SOR, OIT), straż, symulacja, granica. Critical: beds_available_estimate lub icu_oiom_beds.
- Smog/jakość powietrza: symulacja (PM2.5), szkoły, DPS, szpitale. Critical: pm25 lub capacity.
- Powódź: szpitale, szkoły, DPS, straż, granica. Critical: beds_available_estimate.
- Codzienny przegląd: szpitale, szkoły, DPS, straż, granica. Bez critical_attribute.
- Ewakuacja: DPS (pojemność, łóżka), szpitale (łóżka, SOR), straż. Critical: capacity lub beds.

## Format odpowiedzi

Odpowiedz WYŁĄCZNIE prawidłowym JSON:
{{
  "layers_visible": ["layer_id", ...],
  "layers_hidden": ["layer_id", ...],
  "popup_attributes": {{
    "layer_id": ["attr_key", ...]
  }},
  "critical_attribute": {{
    "layer_id": "...",
    "attribute": "...",
    "thresholds": [
      {{"value": 10, "color": "#ef4444"}},
      {{"value": 50, "color": "#f97316"}},
      {{"color": "#10b981"}}
    ],
    "label": "Czytelna nazwa"
  }},
  "explanation": "..."
}}

Jeśli critical_attribute nie jest potrzebny, ustaw null.
"""


async def configure_view(query: str, crisis_context: str | None = None) -> dict:
    """
    Takes a user query describing a situation and returns a ViewConfig dict.
    """
    schemas = get_all_schemas()
    catalog = _build_layer_catalog(schemas)
    system = SYSTEM_PROMPT.format(layer_catalog=catalog)

    user_msg = f"/no_think\n{query}"
    if crisis_context:
        user_msg = f"/no_think\n{query}\n\nAktywny kontekst kryzysowy: {crisis_context}"

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_msg},
    ]

    try:
        result = await chat_completion(messages, temperature=0.2, max_tokens=2048)
    except Exception:
        logger.exception("OpenRouter call failed, returning fallback config")
        return _fallback_config(query)

    return _validate_and_normalize(result, schemas)


def _validate_and_normalize(raw: dict, schemas: list[LayerSchema]) -> dict:
    """Ensure the LLM response has all required fields."""
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
    raw_popups = raw.get("popup_attributes", {})
    for lid, attrs in raw_popups.items():
        if lid in all_ids and isinstance(attrs, list):
            popup_attrs[lid] = attrs

    critical = raw.get("critical_attribute")
    if critical and isinstance(critical, dict):
        if critical.get("layer_id") not in all_ids:
            critical = None
        elif not critical.get("attribute"):
            critical = None
        else:
            if "thresholds" not in critical or not critical["thresholds"]:
                critical["thresholds"] = [
                    {"value": 10, "color": "#ef4444"},
                    {"value": 50, "color": "#f97316"},
                    {"color": "#10b981"},
                ]

    model_used = raw.get("_model", "unknown")

    return {
        "layers_visible": visible,
        "layers_hidden": hidden,
        "popup_attributes": popup_attrs,
        "critical_attribute": critical,
        "explanation": raw.get("explanation", ""),
        "model": model_used,
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
}


def _fallback_config(query: str) -> dict:
    """Return a sensible default when the LLM is unavailable."""
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
