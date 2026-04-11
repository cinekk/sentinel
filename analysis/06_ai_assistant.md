# Asystent AI — Analiza Funkcjonalności

**Version:** 1.0
**Date:** 2026-04-11
**Status:** Faza A zaimplementowana; Faza B do decyzji

---

## 1. Wybór modelu (open-weights)

### Rekomendacja: Qwen3 235B-A22B Instruct 2507 via OpenRouter

| Model | Parametry | Cena (input/output) | JSON output | Polski | Latencja |
|-------|-----------|---------------------|-------------|--------|----------|
| **Qwen3 235B-A22B-2507** | 235B/22B active | $0.07/$0.10/M tok | 0.31% error | 201 języków | ~2-6s |
| Qwen3 235B-A22B (04-28) | 235B/22B active | $0.45/$1.82/M tok | Problemy z JSON* | 201 języków | ~5-25s |
| DeepSeek V3.2 | 671B/37B active | $0.26/$0.38/M tok | 0.51% error | ~30 języków | ~2-4s |
| Llama 4 Maverick | 400B/17B active | $0.15/$0.60/M tok | brak danych | 200 języków | ~2-3s |

*Wersja 04-28 ma problem z JSON mode: content=None, odpowiedź w polu reasoning. Wersja 2507 naprawia to.

**Dlaczego Qwen3 235B Instruct 2507:**
- Najlepszy multilingual benchmark (87.5% na 29 językach) — krytyczne dla polskich promptów
- Najniższy structured output error rate (0.31%)
- Licencja Apache 2.0 (open-weights — dodatkowe punkty konkursowe)
- Koszt ~$0.07/M input — przy ~2000 tokenów kontekstu to <$0.001 per request
- Wersja 2507 poprawnie obsługuje `response_format: json_object` bez artefaktów thinking
- Przetestowane: 3 scenariusze (pożar, briefing, ewakuacja) — poprawne odpowiedzi 4-25s

**Fallback:** Keyword-based heurystyka (zaimplementowana w `_fallback_config`) gdy OpenRouter niedostępny.

---

## 2. Architektura — Faza A (zaimplementowana)

### Komponenty

```
services/layer_meta.py    — Katalog atrybutów z human-friendly names (7 warstw, 62 atrybuty)
services/openrouter.py    — Klient OpenRouter (OpenAI-compatible, json_mode, defensive parsing)
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
4. OpenRouter (Qwen3) → JSON ViewConfig
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
5. **Latencja:** Jakie jest akceptowalne opóźnienie odpowiedzi asystenta? (Obecne ~2-3s z Qwen3 na OpenRouter)
6. **Scoring konkursowy:** Ile punktów za open-weights? Czy Ollama fallback też się liczy, czy musi być primary?
