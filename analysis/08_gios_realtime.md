# GIOŚ Real-Time Air Quality — Plan implementacji

**Version:** 1.0  
**Date:** 2026-04-12  
**Status:** Plan  
**Bonus:** +10 pkt za integrację z publicznymi danymi  
**Szacowany koszt:** ~120 linii kodu, 1-2h

---

## 1. Cel

Zamienić mock `AIR_QUALITY_DATA` w `v1_layers.py` na prawdziwe odczyty ze stacji GIOŚ w województwie lubelskim. Jury widzi "dane z GIOŚ, aktualizowane co godzinę" zamiast hardcoded wartości.

---

## 2. API GIOŚ — zweryfikowane endpointy

**Base URL:** `https://api.gios.gov.pl/pjp-api/v1/rest/`  
**Auth:** brak (publiczne)  
**Format:** JSON-LD (dane w polskojęzycznych kluczach)  
**Rate limit:** brak udokumentowanego, ale API bywa wolne (~2-5s per request)

### 2.1 Lista stacji

```
GET /station/findAll
```

Paginowane (20/stronę, 15 stron). Odpowiedź:

```json
{
  "@context": { ... },
  "Lista stacji pomiarowych": [
    {
      "Identyfikator stacji": 266,
      "Kod stacji": "LbLubObywate",
      "Nazwa stacji": "Lublin, ul. Obywatelska",
      "WGS84 φ N": "51.259370",
      "WGS84 λ E": "22.569116",
      "Województwo": "LUBELSKIE",
      "Powiat": "Lublin",
      "Gmina": "Lublin"
    }
  ]
}
```

⚠️ Koordynaty to **stringi**, nie floaty. Parsować: `float(station["WGS84 φ N"])`.

### 2.2 Indeks jakości powietrza (główne źródło danych)

```
GET /aqindex/getIndex/{stationId}
```

**To jest endpoint, którego używamy** — daje zagregowany indeks per stację, aktualizowany co godzinę.

Odpowiedź (zweryfikowana live, stacja 266, 2026-04-12):

```json
{
  "AqIndex": {
    "Identyfikator stacji pomiarowej": 266,
    "Data wykonania obliczeń indeksu": "2026-04-12 00:25:09",
    "Wartość indeksu": 1,
    "Nazwa kategorii indeksu": "Dobry",
    "Wartość indeksu dla wskaźnika PM2.5": 1,
    "Nazwa kategorii indeksu dla wskażnika PM2.5": "Dobry",
    "Data danych źródłowych ... PM2.5": "2026-04-12 00:00:00",
    "Wartość indeksu dla wskaźnika PM10": 1,
    "Nazwa kategorii indeksu dla wskażnika PM10": "Dobry",
    "Wartość indeksu dla wskaźnika SO2": 0,
    "Nazwa kategorii indeksu dla wskażnika SO2": "Bardzo dobry",
    "Wartość indeksu dla wskaźnika NO2": 1,
    "Nazwa kategorii indeksu dla wskażnika NO2": "Dobry",
    "Wartość indeksu dla wskaźnika O3": 0,
    "Nazwa kategorii indeksu dla wskażnika O3": "Bardzo dobry",
    "Status indeksu ogólnego dla stacji pomiarowej": true,
    "Kod zanieczyszczenia krytycznego": "PYL"
  }
}
```

**Skala indeksu:**

| Wartość | Kategoria | Kolor UI | Kolor hex |
|---------|-----------|----------|-----------|
| 0 | Bardzo dobry | zielony | `#10b981` |
| 1 | Dobry | zielony jasny | `#84cc16` |
| 2 | Umiarkowany | żółty | `#eab308` |
| 3 | Dostateczny | pomarańczowy | `#f97316` |
| 4 | Zły | czerwony | `#ef4444` |
| 5 | Bardzo zły | bordowy | `#991b1b` |

### 2.3 Odczyty surowe (NIE UŻYWAMY)

```
GET /data/getData/{sensorId}
```

⚠️ Działa **tylko dla stacji automatycznych**. Stacje manualne zwracają błąd: "wyniki pomiarów nie są dostępne na bieżąco, są udostępniane po 4-8 tygodniach". Indeks (`/aqindex/getIndex`) jest bardziej niezawodny.

---

## 3. Stacje w województwie lubelskim

Zidentyfikowane 14 stacji. Poniżej te z potwierdzonymi danymi automatycznymi:

| ID | Nazwa | Miasto | Lat | Lon | Auto? | Uwagi |
|---|---|---|---|---|---|---|
| **266** | **ul. Obywatelska** | **Lublin** | 51.259 | 22.569 | **✅** | Główna stacja automatyczna |
| 12096 | ul. Okopowa | Lublin | 51.246 | 22.555 | ? | Druga stacja w Lublinie |
| 236 | ul. Orzechowa | Biała Podlaska | 52.029 | 23.149 | ✅ | Północ województwa |
| 250 | ul. Koszarowa | Kraśnik | 50.928 | 22.228 | ✅ | Południe |
| 285 | ul. Hrubieszowska | Zamość | 50.717 | 23.290 | ✅ | Wschód |
| 11362 | ul. Połaniecka | Chełm | 51.122 | 23.473 | ✅ | Wschód |
| 12098 | ul. Sanatoryjna | Krasnobród | 50.549 | 23.197 | ✅ | Roztocze |
| 20277 | ul. J. Petera | Tomaszów Lub. | 50.444 | 23.422 | ✅ | Południe-wschód |
| 248 | IMGW | Jarczew | 51.814 | 21.972 | ? | Stacja IMGW/tło |
| 275 | ul. Sitkowskiego | Radzyń Podl. | 51.780 | 22.626 | ? | Północ |
| 282 | — | Wilczopole | 51.164 | 22.599 | ? | Okolice Lublina |
| 10874 | RPN | Florianka | 50.552 | 22.983 | ? | Roztoczański PN |
| 258 | ul. Śliwińskiego | Lublin | 51.273 | 22.552 | ❌ manual | Pomiary ręczne |
| 11360 | Al. Małachowskiego | Nałęczów | 51.285 | 22.210 | ❌ manual | Pomiary ręczne |

### ⚠️ Brak automatycznej stacji w Puławach

To jest istotne dla scenariusza demonstracyjnego (pożar Zakładów Azotowych Puławy). Najbliższa automatyczna stacja to Kraśnik (~55 km) lub Lublin (~50 km). Stacja manualna Nałęczów jest bliżej (~11 km), ale nie daje danych real-time.

**Mitygacja w UI:** Przy stacjach wyświetlać odległość od aktywnego zagrożenia. Np. "GIOŚ Lublin, ul. Obywatelska — 50 km od źródła zagrożenia". Użytkownik widzi kontekst.

---

## 4. Architektura implementacji

### 4.1 Nowy plugin: `plugins/gios.py`

```python
class GIOSPlugin(BasePlugin):
    layer_id = "air_quality"
    layer_name = "Jakość powietrza (GIOŚ)"
    data_type = "air_quality"
```

**Strategia cachowania:**

```
Lista stacji  → cache 24h (stacje się nie zmieniają)
Indeks/stację → cache 15 min (dane godzinowe, nie ma sensu częściej)
```

**Strategia odpytywania:**

Nie odpytuj 14 stacji sekwencyjnie (~5s × 14 = 70s). Zamiast tego:

1. Na starcie: pobierz listę stacji, filtruj po `Województwo == "LUBELSKIE"`
2. `asyncio.gather()` — równoległe requesty do `/aqindex/getIndex/{id}` dla wszystkich stacji
3. Timeout per request: 5s (nie blokuj na wolnej stacji)
4. Wynik: GeoJSON FeatureCollection z tymi stacjami, które odpowiedziały

**Fallback:** Jeśli GIOŚ API jest niedostępne (sieć, timeout, 5xx), zwróć ostatni cache. Jeśli nigdy nie było cache — zwróć obecny mock `AIR_QUALITY_DATA` z flagą `"source": "mock"`.

### 4.2 Format GeoJSON (output z pluginu)

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [22.569, 51.259]
      },
      "properties": {
        "name": "GIOŚ Lublin, ul. Obywatelska",
        "station_id": 266,
        "source": "gios_live",
        "overall_index": 1,
        "overall_category": "Dobry",
        "pm25_index": 1,
        "pm25_category": "Dobry",
        "pm10_index": 1,
        "pm10_category": "Dobry",
        "so2_index": 0,
        "so2_category": "Bardzo dobry",
        "no2_index": 1,
        "no2_category": "Dobry",
        "o3_index": 0,
        "o3_category": "Bardzo dobry",
        "critical_pollutant": "PYL",
        "measurement_time": "2026-04-12T00:00:00",
        "calculation_time": "2026-04-12T00:25:09"
      }
    }
  ]
}
```

### 4.3 Zmiany w istniejącym kodzie

**`routers/v1_layers.py`:**
- Endpoint `GET /api/v1/layers/air-quality` → zamiast zwracać mock listę, pobierz z `GIOSPlugin` via registry
- Zachowaj kompatybilność response: dodaj pola `pm25`, `pm10`, `status` (wyliczone z indeksu) żeby briefing service dalej działał bez zmian
- Dodać pole `source: "gios_live" | "mock"` żeby UI mogło to wyróżnić

**Backward-compatible mapping indeks → wartości liczbowe (dla briefingu):**

| Indeks | pm25 przybliżony (µg/m³) | pm10 przybliżony (µg/m³) | status (dotychczasowy) |
|--------|--------------------------|--------------------------|------------------------|
| 0 | 5 | 15 | bardzo dobra |
| 1 | 15 | 35 | dobra |
| 2 | 30 | 55 | umiarkowana |
| 3 | 55 | 80 | dostateczna |
| 4 | 80 | 120 | zła |
| 5 | 120+ | 150+ | bardzo zła |

Uwaga: to są przybliżenia środka przedziału — GIOŚ indeks nie zwraca surowych µg/m³, tylko kategorię. Dla dokładnych odczytów trzeba by `/data/getData/{sensorId}`, ale to wymaga identyfikacji automatycznych sensorów per stację.

**`services/briefing.py`:**
- Bez zmian jeśli `v1_layers` zachowuje pola `pm25`, `status` w response
- Opcjonalnie: dodać `measurement_time` do briefingu — "Dane z GIOŚ, pomiar z godziny dwudziestej trzeciej"

**`main.py`:**
- `registry.register(GIOSPlugin())` w lifespan

**`services/layer_meta.py`:**
- Dodać/zaktualizować schemat warstwy `air_quality` z nowymi atrybutami (overall_index, pm25_index, etc.)

---

## 5. UI / Frontend

### 5.1 Mapa — markery stacji

Stacje GIOŚ renderowane jako kolorowe kółka (kolor = overall_index po tabeli z §3). Popup przy kliknięciu:

```
┌──────────────────────────────────────┐
│ GIOŚ Lublin, ul. Obywatelska        │
│──────────────────────────────────────│
│ Ogólny indeks: 🟢 Dobry             │
│ PM2.5: 🟢 Dobry                     │
│ PM10:  🟢 Dobry                     │
│ SO2:   🟢 Bardzo dobry              │
│ NO2:   🟢 Dobry                     │
│ O3:    🟢 Bardzo dobry              │
│──────────────────────────────────────│
│ Pomiar: 12.04.2026 00:00            │
│ Źródło: GIOŚ (dane publiczne)       │
└──────────────────────────────────────┘
```

Emoji kolorów: 🟢 (0-1), 🟡 (2), 🟠 (3), 🔴 (4-5).

### 5.2 Tabela jakości powietrza (jeśli jest w Grafana)

Jeśli Grafana dashboard (hackathon-gis-v2) też czyta air quality — endpoint zwraca backward-compatible format. Grafana parsuje `pm25`, `pm10`, `status` jak wcześniej, ale teraz to prawdziwe dane.

### 5.3 Warstwa AI Assistant (layer_meta)

Asystent AI (Faza A) powinien wiedzieć o nowych atrybutach. Przy zapytaniu "pokaż jakość powietrza" → widoczna warstwa `air_quality` z `popup_attributes: ["name", "overall_category", "pm25_category", "pm10_category", "measurement_time"]`.

### 5.4 Badge "Live data"

Rozważyć małą etykietkę przy warstwie air_quality w layer panelu:

```
☑ Jakość powietrza (GIOŚ) [LIVE]
```

`[LIVE]` = dane z API. `[MOCK]` = fallback. Jury od razu widzi że to prawdziwe dane.

---

## 6. Scenariusz demonstracyjny

### Bez aktywnego kryzysu (steady-state)

Operator widzi mapę z 10-14 stacjami GIOŚ, wszystkie prawdopodobnie zielone (kwiecień, niska emisja). Popup pokazuje szczegóły per stację. Briefing głosowy mówi: "Jakość powietrza w rejonie: PM2.5 dobry, norma 25."

### Z aktywnym kryzysem (pożar Puławy)

Symulacja generuje syntetyczne odczyty PM2.5 w strefie zagrożenia (SimulationPlugin). GIOŚ stacje pokazują **prawdziwe** tło — np. Lublin ma indeks "Dobry". Kontrast: prawdziwe dane mówią "OK", symulacja mówi "krytyczny w strefie pożaru". To jest potężny efekt wizualny — jury widzi różnicę między normalnym stanem a kryzysem.

### Persona: Tomasz Kowalczyk (dyrektor WCZiK)

Pytania które GIOŚ real data odpowiada:
- "Jaki jest stan powietrza w województwie?" → mapa z kolorowymi markerami
- "Czy są stacje w okolicy Puław?" → tak, ale manual (Nałęczów). Najbliższa auto: Lublin/Kraśnik
- "Jakie jest tło PM2.5 przed incydentem?" → prawdziwy odczyt z GIOŚ. Ważne do oceny nasilenia zanieczyszczenia z pożaru

---

## 7. Gotchas i edge cases

| Problem | Rozwiązanie |
|---------|-------------|
| GIOŚ API niedostępne na demo | Fallback na cache, potem mock. Badge zmienia się na `[CACHED]` / `[MOCK]` |
| Stacja nie ma indeksu (null values) | Pomiń stację w GeoJSON (nie renderuj pustych markerów) |
| Stacja manualna (brak danych real-time) | Filtruj: jeśli `Wartość indeksu == null` && `Status == false` → pomiń |
| Wolne API (~5s per request) | `asyncio.gather()` z timeout 5s. Stacja która nie odpowie = pominięta |
| Koordynaty jako stringi | Parse `float()` z obsługą błędów |
| JSON-LD format | Dane zagnieżdżone pod polskimi kluczami. Parsować defensywnie |
| Godzinny lag w pomiarach | Pokazać `measurement_time` w UI. Użytkownik wie kiedy był pomiar |
| Brak automatycznej stacji w Puławach | Notatka w UI lub dodać stację Airly (osobna integracja, nie w scope) |

---

## 8. Priorytety implementacji

| # | Zadanie | Blokuje | Effort |
|---|---------|---------|--------|
| 1 | `plugins/gios.py` — fetch stacji + indeksów z cache | Wszystko | 80 linii |
| 2 | Rejestracja w `main.py` + update `v1_layers.py` | UI, briefing | 15 linii |
| 3 | `layer_meta.py` — schemat air_quality | AI assistant | 10 linii |
| 4 | Frontend: kolorowe markery + popup format | Demo | 20 linii |
| 5 | Badge `[LIVE]`/`[MOCK]` w layer panelu | Nice-to-have | 5 linii |

**Łącznie: ~130 linii, 1-2h.**

---

## 9. Testowanie

1. **Smoke test:** `GET /api/v1/layers/air-quality` → JSON z prawdziwymi stacjami, `source: "gios_live"`
2. **Cache test:** Wyłącz sieć → endpoint zwraca cached data (nie 500)
3. **Fallback test:** Bez sieci i bez cache → mock data z `source: "mock"`
4. **Map test:** Markery widoczne na mapie, popup wyświetla indeks i czas pomiaru
5. **Briefing test:** Voice briefing poprawnie cytuje najbliższą stację GIOŚ z prawdziwymi danymi
