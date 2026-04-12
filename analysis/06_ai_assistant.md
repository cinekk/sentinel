# Asystent AI — Analiza Funkcjonalności

**Version:** 1.0
**Date:** 2026-04-11
**Status:** Faza A zaimplementowana; Faza B do decyzji

---

## 1. Wybór modelu (open-weights)

### Rekomendacja: Qwen3-30B-A3B Instruct 2507 via OpenRouter + Structured Output

| Model | Parametry (aktywne) | Cena (input/output) | JSON output | Latencja |
|-------|---------------------|---------------------|-------------|----------|
| **Qwen3-30B-A3B-2507** | 30B (3.3B active) | ~$0.07/$0.14/M tok | json_schema ✓ | **~3-5s** |
| Qwen3 8B (04-28) | 8.2B | $0.05/$0.40/M tok | content:null z json_object* | ~3-7s |
| Qwen3.5 9B | 9B | $0.05/$0.15/M tok | niestabilny** | ~10-50s |
| Qwen3 235B-A22B-2507 | 235B (22B active) | $0.07/$0.10/M tok | json_schema ✓ | ~2-6s |

*Qwen3 8B: `response_format: json_object` zwraca `content: null`. Wymaga `json_schema`.
**Qwen3.5 9B: thinking mode zużywa 4000+ tokenów, providery ignorują `enable_thinking: false`, JSON niestabilny.

**Dlaczego Qwen3-30B-A3B Instruct 2507:**
- MoE: 30B parametrów, ale **tylko 3.3B aktywnych** — lekki jak 4B model
- **Non-thinking mode** (Instruct-2507) — zero overhead na reasoning, ~110 tokenów output
- `json_schema` z `strict: true` + enum na layer_id → model zwraca TYLKO prawidłowe nazwy warstw
- Licencja Apache 2.0 (open-weights — dodatkowe punkty konkursowe)
- Przetestowany: "pokaż tylko szpitale", "ukryj szkoły" → poprawne odpowiedzi **~4s**

**Fallback:** Keyword-based heurystyka (zaimplementowana w `_fallback_config`) z obsługą "pokaż tylko X" / "ukryj X".

---

## 2. Architektura — Faza A (zaimplementowana)

### Komponenty

```
services/layer_meta.py    — Katalog atrybutów z human-friendly names (7 warstw, 62 atrybuty)
services/openrouter.py    — Klient OpenRouter (OpenAI-compatible, json_schema, defensive parsing)
services/assistant.py     — System prompt + LLM call + walidacja + fallback
routers/assistant.py      — POST /api/assistant/configure-view + GET /api/assistant/layer-schemas
frontend/app.js           — applyViewConfig() + sendAssistantQuery() + chat panel
frontend/index.html       — Chat panel w sidebar
frontend/style.css        — Stylizacja ops-center
```

### Przepływ danych

1. Użytkownik opisuje sytuację w chacie
2. Frontend → `POST /api/assistant/configure-view` z query
3. Backend buduje system prompt z katalogiem warstw/atrybutów
4. OpenRouter (Qwen3-30B-A3B, json_schema structured output) → JSON ViewConfig
5. Frontend `applyViewConfig()` → programowo przełącza warstwy, filtruje popupy, ustawia critical attribute

### Kontrakt ViewConfig

```json
{
  "layers_visible": ["hospitals", "fire_stations", "simulation_threat"],
  "layers_hidden": ["schools", "social", "events", "lublin_boundary"],
  "popup_attributes": {
    "hospitals": ["name", "beds_available_estimate", "has_sor", "icu_oiom_beds"]
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
  "explanation": "Widok kryzysowy pożar — szpitale z dostępnością łóżek, straż, strefa zagrożenia."
}
```

---

## 3. Faza B — Analiza i synteza danych (scope)

### Pytania analityczne Tomasza Kowalczyka

Na podstawie persony (01_persona.md) i case study (03_case_study.md):

#### Możliwe teraz (istniejące endpointy)

| # | Pytanie | Endpoint | Uwagi |
|---|---------|----------|-------|
| 1 | Ile szpitali z SOR w promieniu 30km od Puław? | `/api/resources/calculator` | Filtr type + has_sor |
| 2 | Jakie obiekty są w strefie zagrożenia? | `/api/v1/crisis/affected` | Już działa z symulacją |
| 3 | Ile łóżek OIT w województwie? | `/api/resources?type=hospital` | Sumowanie po stronie klienta |
| 4 | Które jednostki PSP/OSP pokrywają Puławy? | `/api/layers/fire_stations/geojson` | Filtr przestrzenny |
| 5 | Jaki jest aktualny stan symulacji? | `/api/simulation/state` | Tick, config, crisis_id |

#### Wymaga rozszerzenia endpointów

| # | Pytanie | Brakujące | Koszt impl. |
|---|---------|-----------|-------------|
| 6 | Ile łóżek jest dostępnych w promieniu 50km? | Spatial query + sumowanie beds_available | Niski |
| 7 | Które szkoły/DPS mają schronienia (basement)? | Filtr po crisis_readiness atrybutach | Niski (gdy dane wejdą) |
| 8 | Jaka jest przepustowość transportowa do ewakuacji? | EFR (Evacuation Feasibility Ratio) | Średni |
| 9 | Ranking wrażliwości obiektów w strefie | Vulnerability Score (3.2 z data_req) | Średni |
| 10 | Ile osób narażonych w strefie zagrożenia? | GUS grid + plume intersection | Wysoki |

#### Wymaga nowych danych

| # | Pytanie | Brakujące dane |
|---|---------|----------------|
| 11 | Jaki jest trend PM2.5 w ostatnich 24h? | GIOŚ time-series (Phase 5) |
| 12 | Czy prognoza wiatru zmienia strefę zagrożenia? | IMGW NWP comparison (Phase 5) |
| 13 | Ile autobusów jest dostępnych do ewakuacji? | Transport contracts (INTERNAL) |
| 14 | Jak wygląda obłożenie szpitali w czasie rzeczywistym? | HIS real-time beds (INTERNAL) |
| 15 | Czy BIP gminy Puławy wspomina o zagrożeniach? | BIP scraping (Phase 7+) |

### Rekomendacja implementacji Fazy B

**Podejście: Tool-use (function calling)**

Asystent LLM dostaje zestaw narzędzi (endpointów API) i sam decyduje które wywołać:

```
tools:
  - resources_in_radius(lat, lon, radius_km, type?) → lista zasobów
  - crisis_affected() → obiekty w strefie zagrożenia
  - simulation_state() → stan symulacji
  - layer_geojson(layer_id) → surowe dane GeoJSON
```

**Korzyści:** Użytkownik zadaje pytanie NL → LLM planuje sekwencję wywołań → zwraca odpowiedź NL.

**Ryzyka:** Latencja (multi-step), hallucynacje w interpretacji danych, koszt tokenów.

**Rekomendacja:** Zaimplementować tool-use tylko jeśli starczy czasu. Priorytet = Faza A (zarządzanie widokiem) działa dobrze na hackathonie.

---

## 4. Pytania do doprecyzowania

1. **Kontekst kryzysu:** Czy asystent ma automatycznie reagować na aktywną symulację/kryzys, czy tylko na jawne polecenie użytkownika?
2. **Persystencja widoku:** Czy konfiguracja widoku powinna być zapisywalna (np. "widok kryzysowy pożar", "widok codzienny smog")?
3. **Multi-turn:** Czy asystent ma pamiętać kontekst rozmowy (np. "teraz pokaż mi jeszcze szkoły"), czy każde zapytanie jest niezależne?
4. **Język:** Interfejs po polsku — czy asystent też musi odpowiadać po polsku? (Obecnie: tak, wymuszony w system prompt)
5. **Latencja:** Jakie jest akceptowalne opóźnienie odpowiedzi asystenta? (Obecne ~3-5s z Qwen3-30B-A3B na OpenRouter)
6. **Scoring konkursowy:** Ile punktów za open-weights? Czy Ollama fallback też się liczy, czy musi być primary?
