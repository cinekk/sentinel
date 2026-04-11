# Źródła Danych SENTINEL — Pełna Analiza Integracji

**Version:** 1.0  
**Date:** 2026-04-11  
**Status:** Hackathon — wszystkie źródła mockowane; dokument opisuje docelowy stan integracji  
**Kontekst:** Civil42 Hackathon, Województwo Lubelskie

---

## Spis treści

1. [Podsumowanie wykonawcze](#1-podsumowanie-wykonawcze)
2. [Źródła danych środowiskowych](#2-źródła-danych-środowiskowych)
3. [Źródła danych o obiektach wrażliwych](#3-źródła-danych-o-obiektach-wrażliwych)
4. [Źródła danych o zasobach reagowania](#4-źródła-danych-o-zasobach-reagowania)
5. [Źródła danych o infrastrukturze krytycznej](#5-źródła-danych-o-infrastrukturze-krytycznej)
6. [Źródła danych o zagrożeniach przemysłowych](#6-źródła-danych-o-zagrożeniach-przemysłowych)
7. [Źródła danych populacyjnych i administracyjnych](#7-źródła-danych-populacyjnych-i-administracyjnych)
8. [Źródła danych o infrastrukturze komunikacyjnej](#8-źródła-danych-o-infrastrukturze-komunikacyjnej)
9. [Źródła danych społecznościowych i sygnałów](#9-źródła-danych-społecznościowych-i-sygnałów)
10. [Źródła danych o magazynach i zaopatrzeniu](#10-źródła-danych-o-magazynach-i-zaopatrzeniu)
11. [Macierz priorytetów integracji](#11-macierz-priorytetów-integracji)

---

## 1. Podsumowanie wykonawcze

### Klasyfikacja metod pozyskania danych

Każde źródło danych jest sklasyfikowane według jednej z trzech metod pozyskania:

| Symbol | Metoda | Opis |
|--------|--------|------|
| 🟢 **API** | Publiczne API | Oficjalny, publicznie dostępny interfejs REST/SOAP. Integracja stabilna i wspierana. |
| 🟡 **SCRAPE** | Scraping publicznych danych | Dane publiczne, ale bez API — wymagają scrapowania HTML, parsowania PDF/XLSX z BIP lub portali. |
| 🔴 **INTERNAL** | Integracja z systemami wewnętrznymi | Dane dostępne tylko w zamkniętych systemach państwowych/samorządowych. Wymagają umów, dostępów, integracji. |

### Podsumowanie ilościowe

| Kategoria | Źródeł 🟢 API | Źródeł 🟡 SCRAPE | Źródeł 🔴 INTERNAL | Razem |
|-----------|---------------|-------------------|---------------------|-------|
| Środowiskowe | 3 | 0 | 0 | 3 |
| Obiekty wrażliwe | 2 | 1 | 2 | 5 |
| Zasoby reagowania | 1 | 1 | 3 | 5 |
| Infrastruktura krytyczna | 1 | 1 | 2 | 4 |
| Zagrożenia przemysłowe | 0 | 1 | 1 | 2 |
| Populacyjne/administracyjne | 3 | 1 | 0 | 4 |
| Komunikacyjna | 0 | 0 | 2 | 2 |
| Sygnały społecznościowe | 0 | 2 | 0 | 2 |
| Magazyny i zaopatrzenie | 0 | 0 | 2 | 2 |
| **RAZEM** | **10** | **7** | **12** | **29** |

---

## 2. Źródła danych środowiskowych

### 2.1 GIOŚ — Jakość powietrza

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — publiczne REST API |
| **Dostawca** | Główny Inspektorat Ochrony Środowiska |
| **URL API** | `https://api.gios.gov.pl/pjp-api/v1/` (nowe API od 2025; stare `/rest/` wygaszone 30.06.2025) |
| **Dokumentacja** | Swagger: `https://api.gios.gov.pl/pjp-api/swagger-ui/` |
| **Autoryzacja** | Brak klucza — otwarty dostęp; rate limiting per endpoint (od 2 req/min do ~1500 req/min) |
| **Format** | JSON-LD |
| **Częstotliwość** | Wartości godzinowe; stacje raportują z ~1h opóźnieniem |
| **Pokrycie Lubelskie** | ~8 stacji: Lublin-Śródmieście, Puławy-Centrum, Puławy-Azoty, Chełm, Zamość, Biała Podlaska, Kraśnik, Włodawa |

**Wymagana struktura danych:**

```json
{
  "station_id": "string — identyfikator stacji GIOŚ",
  "station_name": "string — np. Puławy-Centrum",
  "latitude": "float — WGS84",
  "longitude": "float — WGS84",
  "voivodeship": "string — lubelskie",
  "city": "string",
  "address": "string",
  "measurements": [
    {
      "pollutant": "enum — PM2.5 | PM10 | NO2 | SO2 | O3 | CO | Pb | C6H6",
      "value": "float — µg/m³",
      "measurement_date": "datetime — UTC",
      "index_level": "enum — bardzo dobry | dobry | umiarkowany | dostateczny | zły | bardzo zły",
      "who_threshold_exceeded": "bool",
      "polish_threshold_exceeded": "bool"
    }
  ],
  "data_freshness_minutes": "int — czas od ostatniego odczytu",
  "station_status": "enum — active | maintenance | offline"
}
```

**Luki i ograniczenia:**
- Niska rozdzielczość przestrzenna — duże obszary między stacjami bez pokrycia
- 1h opóźnienie oznacza, że kryzys może osiągnąć szczyt zanim dane potwierdzą
- Brak mechanizmu push — wymaga pollingu
- Brak bezpośrednich danych o szybkości narastania (rate-of-change) — trzeba obliczać

---

### 2.2 Airly — Hiperloklane czujniki jakości powietrza

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — komercyjne REST API |
| **Dostawca** | Airly sp. z o.o. |
| **URL API** | `https://airapi.airly.eu/v2/` |
| **Dokumentacja** | `https://developer.airly.org` |
| **Autoryzacja** | Klucz API (nagłówek `apikey`); darmowy tier ~100 req/dzień |
| **Format** | JSON (OpenAPI 2.0) |
| **Częstotliwość** | ~5 minut |
| **Pokrycie Lubelskie** | Lublin: ~40 czujników (gęste); Puławy: ~8; wschodnie/wiejskie powiaty: rzadkie |

**Wymagana struktura danych:**

```json
{
  "installation_id": "int",
  "latitude": "float",
  "longitude": "float",
  "address": "string",
  "elevation": "float — m n.p.m.",
  "is_airly_sensor": "bool",
  "measurements": {
    "current": {
      "pm1": "float — µg/m³",
      "pm25": "float — µg/m³",
      "pm10": "float — µg/m³",
      "temperature": "float — °C",
      "humidity": "float — %",
      "pressure": "float — hPa",
      "measurement_time": "datetime"
    },
    "history_24h": ["array — j.w. co godzinę"],
    "forecast_24h": ["array — prognozy Airly"]
  },
  "caqi_index": "float — 0-100+",
  "caqi_level": "string"
}
```

**Luki i ograniczenia:**
- Czujniki klasy konsumenckiej — nie certyfikowane do regulacyjnych progów
- Klasteryzacja w miastach, brak pokrycia przy strefach przemysłowych i wiejskich
- Limit darmowego tieru (100 req/dzień) może być niewystarczający przy kryzysie
- Dane do uzupełnienia GIOŚ, nie do zastąpienia

---

### 2.3 IMGW — Dane meteorologiczne

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — publiczne HTTP API |
| **Dostawca** | Instytut Meteorologii i Gospodarki Wodnej |
| **URL API** | `https://danepubliczne.imgw.pl/api/data/` |
| **Endpointy** | `/synop`, `/meteo`, `/hydro`, `/warningsmeteo`, `/warningshydro` |
| **Autoryzacja** | Brak klucza; akceptacja regulaminu |
| **Format** | JSON (domyślny), XML, CSV, HTML (via `/format/...`) |
| **Częstotliwość** | SYNOP: 10 min–1h; NWP: co 6h (00/06/12/18 UTC) |
| **Stacje Lubelskie** | Lublin-Radawiec (SYNOP), Puławy, Zamość, Terespol |

**Wymagana struktura danych:**

```json
{
  "station_id": "string — kod SYNOP",
  "station_name": "string",
  "latitude": "float",
  "longitude": "float",
  "measurement_time": "datetime — UTC",
  "wind": {
    "speed_ms": "float — m/s",
    "speed_kmh": "float — km/h",
    "direction_deg": "float — stopnie (0=N, 90=E, 180=S, 270=W)",
    "gust_ms": "float — poryw",
    "direction_cardinal": "string — np. NNW"
  },
  "temperature_c": "float",
  "humidity_pct": "float",
  "pressure_hpa": "float",
  "precipitation_mm": "float",
  "cloud_cover_okta": "int — 0-8",
  "visibility_m": "float",
  "mixing_layer_height_m": "float — kluczowy dla modelu plume (jeśli dostępny)",
  "pasquill_stability_class": "enum — A|B|C|D|E|F (obliczane z temp + wiatr)",
  "warnings": [
    {
      "type": "string — np. wiatr, burza, mróz, upał, smog",
      "level": "int — 1-3",
      "valid_from": "datetime",
      "valid_to": "datetime",
      "description": "string"
    }
  ],
  "nwp_forecast": {
    "model_run_time": "datetime — czas uruchomienia modelu",
    "forecast_hours": [
      {
        "forecast_time": "datetime",
        "wind_speed_ms": "float",
        "wind_direction_deg": "float",
        "temperature_c": "float",
        "precipitation_mm": "float"
      }
    ]
  }
}
```

**Luki i ograniczenia:**
- Mixing layer height (MLH) nie zawsze dostępny w publicznym API — może wymagać dekodowania GRIB
- NWP ma 6-godzinną kadencję — między uruchomieniami brak aktualizacji prognozy
- Wiatr mierzony na 10m n.p.t., nie na wysokości emisji dymu
- Brak automatycznego alertu o istotnej zmianie prognozy wiatrowej

---

## 3. Źródła danych o obiektach wrażliwych

### 3.1 RSPO — Rejestr Szkół i Placówek Oświatowych

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — oficjalne API (od 15.01.2026), wymaga wniosku o dostęp |
| **Dostawca** | Centrum Informatyki Edukacji (CIE) / Ministerstwo Edukacji Narodowej |
| **URL API** | `https://api.rspo.gov.pl/` (nowe API od 15.01.2026) |
| **Wniosek o dostęp** | Email: `rspo@cie.gov.pl` |
| **Autoryzacja** | Klucz po zatwierdzeniu wniosku |
| **Format** | JSON-LD, JSON, XML, YAML, CSV, HTML |
| **Częstotliwość** | Roczna; zmiany (otwarcia/zamknięcia) publikowane śródrocznie |
| **Pokrycie Lubelskie** | ~1800 szkół i placówek oświatowych w 213 gminach |

**Wymagana struktura danych:**

```json
{
  "rspo_number": "string — unikalny identyfikator RSPO",
  "name": "string — pełna nazwa szkoły",
  "patron": "string — imię patrona (jeśli dotyczy)",
  "type": "enum — przedszkole | szkoła_podstawowa | liceum | technikum | szkoła_branżowa | specjalna | zespół_szkół",
  "education_level": "enum — przedszkolne | podstawowe | ponadpodstawowe",
  "address": {
    "street": "string",
    "building_number": "string",
    "city": "string",
    "postal_code": "string",
    "gmina": "string",
    "powiat": "string",
    "teryt_code": "string"
  },
  "latitude": "float — WGS84",
  "longitude": "float — WGS84",
  "operator": "string — organ prowadzący (samorząd/prywatny/kościelny)",
  "students_count": "int — liczba uczniów",
  "staff_count": "int — liczba pracowników",
  "contact": {
    "phone": "string",
    "email": "string",
    "director_name": "string"
  },

  "building": {
    "year_built": "int",
    "construction_type": "enum — murowany | prefabrykat_wielka_płyta | drewniany | modułowy",
    "floors": "int",
    "usable_area_sqm": "float",
    "is_tysiaclatka": "bool — szkoła z programu 'Tysiąc szkół na Tysiąclecie' 1959-1966",
    "tysiaclatka_series": "string — seria projektu typowego (jeśli znana)",
    "last_technical_review": "date",
    "thermal_modernization": "bool — czy przeszła termomodernizację"
  },

  "crisis_readiness": {
    "has_basement": "bool — piwnica możliwa do wykorzystania jako schronienie",
    "basement_area_sqm": "float",
    "has_sports_hall": "bool",
    "sports_hall_area_sqm": "float — potencjalna powierzchnia schronienia",
    "sports_hall_capacity_persons": "int",
    "has_kitchen": "bool — kuchnia do żywienia zbiorowego",
    "kitchen_daily_meals_capacity": "int",
    "has_showers": "bool — prysznice (ważne dla schronienia)",
    "shelter_capacity_persons": "int — łączna pojemność jako punkt schronienia",
    "designated_as_shelter": "bool — czy wskazana w planie gminy/powiatu jako punkt schronienia",
    "evacuation_plan_date": "date — data ostatniej aktualizacji planu ewakuacji",
    "last_drill_date": "date — ostatnie ćwiczenia ewakuacyjne",
    "evacuation_assembly_point": "string — punkt zbiórki",
    "alternative_exits_count": "int"
  },

  "building_resilience": {
    "hvac_type": "enum — mechaniczna | grawitacyjna | klimatyzacja",
    "hvac_can_seal": "bool — możliwość zamknięcia wentylacji przy smogu/dymu",
    "has_air_filtration": "bool",
    "backup_power": "bool",
    "backup_power_capacity_hours": "float",
    "water_tank": "bool",
    "water_tank_liters": "float",
    "flood_zone": "bool — czy w strefie zalewowej",
    "flood_zone_level": "string — np. Q100, Q500"
  },

  "accessibility": {
    "wheelchair_accessible": "bool",
    "elevator": "bool",
    "barriers_for_evacuation": "string — opis barier"
  },

  "operating_hours": {
    "school_hours": "string — np. 7:00-16:00",
    "after_hours_activities": "bool",
    "weekend_use": "bool"
  }
}
```

**Uwaga o "tysiąclatkach":**
Szkoły z programu "Tysiąc szkół na Tysiąclecie Państwa Polskiego" (1959-1966) mają specyficzne cechy konstrukcyjne:
- Budowane wg typowych projektów architektonicznych (serie: 900, 1000, 1100 uczniów)
- Konstrukcja murowana, żelbetowe stropy, często z piwnicami
- Wiele z nich przeszło modernizacje, ale zachowały solidną konstrukcję nośną
- Duże sale gimnastyczne — potencjalne punkty schronienia
- Rozpoznawalne po architekturze — ułatwia identyfikację w terenie
- W Lubelskiem: szacunkowo 30-50 szkół tego typu

**Luki i ograniczenia:**
- RSPO nie zawiera danych o budynku (konstrukcja, piwnice, HVAC) — te dane muszą pochodzić z EGiB lub inspekcji
- Brak informacji o gotowości kryzysowej — wymaga ręcznego zbierania od dyrektorów
- Współrzędne starszych rekordów mogą wymagać geokodowania
- Numery kontaktowe nie zawsze aktualne
- Brak informacji o rzeczywistym obłożeniu (ferie, nauka zdalna)

---

### 3.2 MRIPS / RJPS — Domy Pomocy Społecznej

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** — portal wyszukiwarkowy, brak stabilnego API |
| **Dostawca** | Ministerstwo Rodziny i Polityki Społecznej / RJPS |
| **URL** | `https://rjps.mrips.gov.pl/` (wyszukiwarka) |
| **Alternatywne źródła** | BIP wojewody lubelskiego — wykazy DPS w PDF/XLSX |
| **Autoryzacja** | Publiczny dostęp do wyszukiwarki |
| **Format** | HTML (formularz + wyniki); załączniki PDF/XLS na BIP |
| **Częstotliwość** | Roczny cykl licencyjny |
| **Pokrycie Lubelskie** | ~60 placówek DPS w województwie |

**Wymagana struktura danych:**

```json
{
  "dps_id": "string — identyfikator wewnętrzny lub z rejestru",
  "name": "string — pełna nazwa placówki",
  "operator": "string — organ prowadzący (powiat/NGO/kościelny/prywatny)",
  "type": "enum — osoby_starsze | niepełnosprawne_fizycznie | niepełnosprawne_intelektualnie | przewlekle_psychicznie_chore | dzieci_i_młodzież | uzależnione",
  "address": {
    "street": "string",
    "city": "string",
    "postal_code": "string",
    "gmina": "string",
    "powiat": "string",
    "teryt_code": "string"
  },
  "latitude": "float",
  "longitude": "float",

  "capacity": {
    "total_beds": "int — licencjonowana pojemność",
    "occupied_beds": "int — aktualne obłożenie",
    "free_beds": "int — wolne miejsca"
  },

  "residents_mobility": {
    "ambulatory": "int — chodzący samodzielnie",
    "wheelchair": "int — na wózkach inwalidzkich",
    "bedridden": "int — unieruchomieni/leżący",
    "requiring_als_transport": "int — wymagający transportu medycznego (ALS)",
    "requiring_oxygen": "int — na stałym tlenie",
    "psychiatric_supervision": "int — wymagający nadzoru psychiatrycznego"
  },

  "medical_capabilities": {
    "nurse_24_7": "bool — pielęgniarka całodobowo",
    "doctor_visits_per_week": "int",
    "nebulization_available": "bool",
    "oxygen_supply": "bool",
    "critical_medications_stock_days": "int — zapas leków krytycznych w dniach",
    "primary_care_agreement": "string — umowa z POZ",
    "nearest_sor_km": "float — odległość do najbliższego SOR"
  },

  "building": {
    "floors": "int",
    "has_elevator": "bool — winda łóżkowa",
    "elevator_stretcher_capable": "bool",
    "construction_year": "int",
    "construction_type": "string",
    "usable_area_sqm": "float"
  },

  "crisis_readiness": {
    "evacuation_plan_date": "date",
    "last_drill_date": "date",
    "estimated_evacuation_time_minutes": "int — szacowany czas pełnej ewakuacji",
    "required_buses": "int — wymagana liczba autobusów do ewakuacji",
    "required_ambulances": "int — wymagana liczba karetek",
    "designated_evacuation_destination": "string — umowne miejsce docelowe ewakuacji",
    "shelter_in_place_feasibility": "enum — dobra | ograniczona | niska"
  },

  "infrastructure": {
    "backup_power": "bool",
    "backup_power_hours": "float",
    "water_tank": "bool",
    "heating_type": "enum — gazowe | elektryczne | węglowe | miejskie",
    "hvac_can_seal": "bool — możliwość uszczelnienia wentylacji",
    "has_air_filtration": "bool",
    "vehicle_access_width_m": "float — szerokość bramy wjazdowej"
  },

  "vulnerability": {
    "flood_zone": "bool",
    "industrial_hazard_zone": "bool — w strefie zagrożenia zakładu Seveso",
    "distance_to_nearest_industrial_hazard_km": "float"
  },

  "contact": {
    "phone_24h": "string",
    "director_phone": "string",
    "email": "string"
  }
}
```

**Luki i ograniczenia:**
- Brak formalnego REST API — integracja wymaga scrapowania formularza RJPS lub parsowania dokumentów BIP
- Klasyfikacja mobilności mieszkańców nie jest publikowana — wymaga ręcznego zbierania od dyrektorów DPS
- Aktualne obłożenie nie jest publikowane publicznie
- Dane kontaktowe mogą być nieaktualne
- Dane RODO-wrażliwe (o mieszkańcach) — w GIS tylko agregaty, nie dane osobowe

---

### 3.3 NFZ / MZ — Szpitale i podmioty lecznicze

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** (częściowo) + 🟡 **SCRAPE** (dane szczegółowe) |
| **Dostawca** | Narodowy Fundusz Zdrowia / Ministerstwo Zdrowia / CeZ (ezdrowie) |
| **URL API** | `https://api.nfz.gov.pl/` (wiele serwisów: ITL, apteki, etc.) |
| **Dane otwarte** | `https://dane.gov.pl` — zbiory CSV o podmiotach leczniczych |
| **RPRM** | `https://rprm.ezdrowie.gov.pl/` — Rejestr Podmiotów Realizujących Działalność Leczniczą (eksport CSV) |
| **Autoryzacja** | Publiczny dostęp (per serwis — sprawdzić Swagger) |
| **Format** | JSON (API), CSV (dane.gov.pl / RPRM) |
| **Częstotliwość** | Kwartalne aktualizacje kontraktów; czasy oczekiwania co tydzień |
| **Pokrycie Lubelskie** | ~35 szpitali; kluczowe: SPZOZ Puławy, COZL Lublin, SPSK1/SPSK4 Lublin, szpitale powiatowe |

**Wymagana struktura danych:**

```json
{
  "facility_id": "string — KRP / REGON / identyfikator wewnętrzny",
  "name": "string — pełna nazwa",
  "short_name": "string",
  "type": "enum — szpital_ogólny | szpital_specjalistyczny | szpital_kliniczny | szpital_uniwersytecki",
  "operator": "string — np. SPZOZ, podmiot prywatny, uczelnia",
  "nfz_contract": "bool — czy ma kontrakt z NFZ",
  "address": {
    "street": "string",
    "city": "string",
    "postal_code": "string",
    "gmina": "string",
    "powiat": "string",
    "teryt_code": "string"
  },
  "latitude": "float",
  "longitude": "float",

  "emergency": {
    "has_sor": "bool — Szpitalny Oddział Ratunkowy",
    "has_pediatric_sor": "bool — SOR dla dzieci",
    "has_izba_przyjec": "bool — izba przyjęć (jeśli brak SOR)",
    "sor_throughput_per_day": "int — średnia liczba przyjęć/dobę",
    "triage_system": "string — np. MTS (Manchester)",
    "decontamination_entry": "bool — linia dekontaminacji",
    "decontamination_type": "string — np. mokra, sucha",
    "isolation_rooms": "int",
    "negative_pressure_rooms": "int"
  },

  "beds": {
    "total_contracted": "int — łóżka z kontraktu NFZ",
    "total_physical": "int — łóżka fizycznie dostępne",
    "occupied_estimate_pct": "float — szacowane obłożenie (domyślnie 70%)",
    "available_estimate": "int — obliczane: total × (1 - occupied_pct)",
    "by_department": [
      {
        "department": "string — np. interna, chirurgia, kardiologia, neurologia",
        "beds": "int",
        "icu_beds": "int — łóżka OIT/OIOM w oddziale"
      }
    ]
  },

  "critical_care": {
    "icu_oiom_beds": "int — łóżka OIOM łącznie",
    "ventilator_capable_beds": "int",
    "ecmo_available": "bool",
    "ecmo_units": "int",
    "dialysis_stations": "int",
    "burn_unit": "bool",
    "burn_unit_beds": "int",
    "neonatal_icu": "bool",
    "neonatal_icu_beds": "int"
  },

  "specializations": [
    "string — kardiologia, toksykologia, chirurgia urazowa, onkologia, etc."
  ],

  "surgery": {
    "operating_rooms": "int",
    "polytrauma_capable": "bool — zdolność do leczenia urazów wielonarządowych",
    "angiography_24_7": "bool",
    "ct_24_7": "bool",
    "mri_available": "bool"
  },

  "cbrn_readiness": {
    "cbrn_protocol": "bool — procedury przyjęcia skażonych pacjentów",
    "hvac_recirculation": "bool — możliwość przełączenia na recyrkulację",
    "hvac_seal_time_minutes": "int — czas uszczelnienia HVAC",
    "ppe_stock_sets": "int — zestawy ochrony osobistej",
    "antidote_stocks": {
      "atropine": "bool",
      "pralidoxime": "bool",
      "hydroxocobalamin": "bool",
      "other": ["string"]
    }
  },

  "helicopter": {
    "helipad": "bool — lądowisko dla śmigłowców",
    "helipad_type": "enum — na_dachu | naziemne | tymczasowe",
    "helipad_night_capable": "bool",
    "lpr_base_distance_km": "float — odległość do bazy LPR"
  },

  "laboratory": {
    "toxicology_testing": "bool",
    "methemoglobin_testing": "bool",
    "heavy_metals_testing": "bool",
    "blood_gas_analysis_24_7": "bool",
    "turnaround_time_minutes": "int — orientacyjny czas wyniku"
  },

  "blood_bank": {
    "has_blood_bank": "bool",
    "blood_units_available": "int — orientacyjna liczba jednostek",
    "nearest_rckik_km": "float — odległość do Regionalnego Centrum Krwiodawstwa"
  },

  "pharmacy": {
    "hospital_pharmacy": "bool",
    "critical_drug_stock_days": "int — zapas leków krytycznych",
    "oxygen_supply_hours": "float — zapas tlenu w godzinach"
  },

  "infrastructure": {
    "backup_power": "bool",
    "backup_power_capacity_kva": "float",
    "backup_power_startup_seconds": "int",
    "backup_power_fuel_hours": "float",
    "ups_coverage": "string — np. SOR + OIT, pełne",
    "water_independence": "bool — studnia lub zbiorniki",
    "water_reserve_hours": "float"
  },

  "mutual_aid": {
    "partner_hospitals": ["string — nazwy szpitali z umowami o współpracy"],
    "max_patient_transfer_per_day": "int",
    "preferred_transport": "string — np. karetka, LPR"
  },

  "contact": {
    "phone_24h_sor": "string",
    "phone_dyrektor": "string",
    "crisis_coordinator": "string — imię i telefon koordynatora kryzysowego",
    "email": "string"
  }
}
```

**Luki i ograniczenia:**
- Kontraktowane łóżka ≠ dostępne łóżka (obłożenie zmienne) — real-time wymaga integracji z HIS szpitala
- Łóżka OIT/specjalistyczne wymagają osobnych zbiorów danych NFZ
- Gotowość CBRN, stan zapasów antidotów — dane wewnętrzne, nie publiczne
- RPRM daje lokalizacje i specjalizacje, ale nie kapacytet operacyjny
- API NFZ obsługuje głównie terminy leczenia (ITL), nie łóżka

---

### 3.4 PSP / OSP — Jednostki straży pożarnej

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — brak publicznego rejestru stacji; dane z KG PSP, OSM, BDOT10k |
| **Dostawca** | Komenda Główna PSP / komendy powiatowe |
| **Dostępne publicznie** | OSM (amenity=fire_station — niekompletne), BDOT10k (budynki straży) |
| **Dane pełne** | Wnioski o informację publiczną, bezpośrednia współpraca z KW PSP Lublin |
| **Pokrycie Lubelskie** | PSP: ~20 komend miejskich/powiatowych; OSP: ~1000+ jednostek (różna gotowość) |

**Wymagana struktura danych:**

```json
{
  "unit_id": "string",
  "name": "string — np. KM PSP Lublin, KP PSP Puławy, OSP Kazimierz Dolny",
  "type": "enum — PSP_KM | PSP_KP | OSP_ksrg | OSP_poza_ksrg",
  "ksrg_member": "bool — czy w Krajowym Systemie Ratowniczo-Gaśniczym",
  "address": "string",
  "latitude": "float",
  "longitude": "float",
  "powiat": "string",

  "personnel": {
    "total_fte": "int — etaty ogółem",
    "on_duty_shift": "int — obsada dyżurna na zmianie",
    "specialists": {
      "cbrn": "int — ratownicy chemiczni",
      "water_rescue": "int",
      "height_rescue": "int",
      "technical_rescue": "int",
      "medical_qualified": "int — kwalifikowana pierwsza pomoc"
    }
  },

  "fleet": [
    {
      "vehicle_type": "enum — GCBA | GBA | GCBA_RT | SCRt | SLRt | SD | SRD | łódź | samochód_operacyjny",
      "operational_number": "string",
      "water_capacity_liters": "int",
      "foam_capacity_liters": "int",
      "special_equipment": ["string — np. wyposażenie CBRN, pompa, drabina, zestaw hydrauliczny"],
      "status": "enum — operacyjny | w_naprawie | rezerwa"
    }
  ],

  "equipment_stocks": {
    "foam_agent_liters": "int",
    "absorbent_kg": "int",
    "cbrn_detection_devices": "int — detektory wielogazowe",
    "decontamination_sets": "int",
    "breathing_apparatus_sets": "int"
  },

  "coverage": {
    "primary_response_zone_km": "float — strefa podstawowa (15 min)",
    "secondary_response_zone_km": "float — strefa rozszerzona",
    "avg_response_time_minutes": "float — historyczny średni czas dojazdu",
    "isochrone_geojson": "GeoJSON — poligon izochrony dojazdu"
  },

  "specializations": [
    "enum — HAZMAT | water_rescue | USAR | rope_rescue | confined_space | airport_rescue"
  ],

  "mutual_aid": {
    "partner_units": ["string"],
    "neighboring_kp_kms": ["string — sąsiednie komendy"]
  },

  "contact": {
    "dispatch_phone": "string — stanowisko kierowania",
    "commander_phone": "string",
    "radio_callsign": "string"
  }
}
```

**Luki i ograniczenia:**
- Brak publicznego, geokodowanego rejestru wszystkich jednostek PSP/OSP z wyposażeniem
- Dane operacyjne (dyspozycyjność, stany pojazdów) — systemy wewnętrzne PSP (SWD-ST)
- OSM zawiera część stacji, ale dane niekompletne i bez wyposażenia
- Gotowość OSP bardzo zrómienna — od profesjonalnych jednostek KSRG po nieczynne
- Stany magazynowe i specjalizacje — wymagają bezpośredniej współpracy z KW PSP

---

### 3.5 Policja — Jednostki i zasoby

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — brak publicznego geokodowanego rejestru |
| **Dostawca** | Komenda Wojewódzka Policji w Lublinie |
| **Dostępne publicznie** | BIP policji (statystyki), OSM (amenity=police), dane.gov.pl (fragmentarycznie) |
| **Dane pełne** | Współpraca z KWP Lublin |

**Wymagana struktura danych:**

```json
{
  "unit_id": "string",
  "name": "string — np. KMP Lublin, KPP Puławy",
  "type": "enum — KWP | KMP | KPP | PP | posterunek",
  "address": "string",
  "latitude": "float",
  "longitude": "float",
  "jurisdiction_teryt": ["string — kody TERYT gmin w jurysdykcji"],
  "jurisdiction_geojson": "GeoJSON — granica jurysdykcji",

  "personnel": {
    "total_fte": "int",
    "patrol_available_shift": "int — patrole dostępne na zmianie"
  },

  "fleet": {
    "patrol_cars": "int",
    "offroad_vehicles": "int",
    "transport_vans": "int",
    "motorcycles": "int",
    "drones": "int"
  },

  "capabilities": [
    "enum — traffic_control | road_blockade | convoy_escort | crowd_control | crisis_support"
  ],

  "contact": {
    "duty_officer_phone": "string",
    "commander_phone": "string"
  }
}
```

---

## 4. Źródła danych o zasobach reagowania

### 4.1 Transport — Autobusy i pojazdy zbiorowe

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** (dane o przewoźnikach z REGON/BIP) + 🔴 **INTERNAL** (rzeczywista dostępność) |
| **Dostawca** | MPK Lublin, PKS Wschód, przewoźnicy prywatni, kontrakty wojewódzkie |
| **Dostępne publicznie** | GUS REGON (istnienie firm), BIP Urzędu Marszałkowskiego (kontrakty) |
| **API REGON** | `https://api.stat.gov.pl` — SOAP/XML, wymaga rejestracji |
| **Dane operacyjne** | Wewnętrzne dokumenty kryzysiowe województwa |

**Wymagana struktura danych:**

```json
{
  "operator_id": "string — REGON lub identyfikator wewnętrzny",
  "operator_name": "string — np. MPK Lublin Sp. z o.o.",
  "operator_type": "enum — municipal | pks | private | school_transport",
  "nip": "string",
  "regon": "string",

  "fleet": [
    {
      "vehicle_type": "enum — autobus_standardowy | autobus_przegubowy | mikrobus | bus_niskopodłogowy",
      "count": "int",
      "capacity_seated": "int",
      "capacity_standing": "int",
      "capacity_total": "int",
      "wheelchair_accessible": "bool",
      "air_conditioned": "bool"
    }
  ],

  "crisis_availability": {
    "vehicles_pledged_for_crisis": "int — pojazdy z umowy kryzysowej",
    "seats_available_for_crisis": "int",
    "mobilization_time_minutes": "int — czas od wezwania do gotowości",
    "operating_hours": "string — np. 5:00-23:00",
    "after_hours_mobilization": "bool — czy możliwa mobilizacja nocna",
    "crisis_contract": "bool — czy jest umowa z województwem na sytuacje kryzysowe",
    "contract_valid_until": "date"
  },

  "base_location": {
    "address": "string — adres bazy/zajezdni",
    "latitude": "float",
    "longitude": "float"
  },

  "contact": {
    "dispatch_phone": "string",
    "crisis_phone_24h": "string",
    "manager_phone": "string"
  }
}
```

---

### 4.2 Transport medyczny — Karetki i LPR

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — system dyspozytorski PRM / SWD PRM |
| **Dostawca** | Dysponenci PRM na terenie województwa, LPR |
| **Dostępne publicznie** | Lokalizacje baz LPR (publiczne), RPRM (rejestry podmiotów) |
| **Dane operacyjne** | System Wspomagania Dowodzenia PRM |

**Wymagana struktura danych:**

```json
{
  "unit_id": "string",
  "unit_type": "enum — S_ambulance | P_ambulance | N_ambulance | HEMS_helicopter",
  "operator": "string — np. WSS im. Biegańskiego, LPR Baza Lublin",
  "base_location": {
    "address": "string",
    "latitude": "float",
    "longitude": "float"
  },

  "capability": {
    "type_description": "string — S=specjalistyczny (lekarz), P=podstawowy (ratownicy), N=neonatologiczny",
    "stretcher_capable": "bool",
    "als_capable": "bool — Advanced Life Support",
    "neonatal_transport": "bool",
    "bariatric_capable": "bool"
  },

  "coverage_zone": {
    "primary_area_teryt": ["string"],
    "response_time_target_minutes": "int — mediana czasu dojazdu (standard: 15 min miasto, 20 min poza)",
    "isochrone_geojson": "GeoJSON"
  },

  "status": "enum — available | on_call | at_hospital | maintenance",

  "contact": {
    "dispatch_phone": "string — numer dyspozytorni",
    "direct_phone": "string"
  }
}
```

---

## 5. Źródła danych o infrastrukturze krytycznej

### 5.1 Mosty i kluczowa infrastruktura drogowa

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** (GDDKiA/Geoportal WFS częściowo) + 🔴 **INTERNAL** (dane szczegółowe) |
| **Dostawca** | GDDKiA, zarządcy dróg powiatowych/gminnych |
| **Dostępne publicznie** | BDOT10k (geometria mostów), Geoportal WFS, GDDKiA — częściowo |
| **Dane pełne** | Zarządcy dróg, inspekcje mostowe |

**Wymagana struktura danych:**

```json
{
  "bridge_id": "string — identyfikator obiektu",
  "name": "string — nazwa mostu (jeśli posiada)",
  "road_number": "string — nr drogi",
  "road_class": "enum — A_autostrada | S_ekspresowa | krajowa | wojewódzka | powiatowa | gminna",
  "road_manager": "string — zarządca (GDDKiA / powiat / gmina)",
  "km_marker": "float — pikietaż",
  "latitude": "float",
  "longitude": "float",
  "crosses": "string — np. Wisła, Wieprz, linia kolejowa",

  "technical": {
    "length_m": "float",
    "spans": "int — liczba przęseł",
    "clearance_m": "float — prześwit",
    "width_m": "float — szerokość jezdni",
    "construction_year": "int",
    "last_inspection_date": "date"
  },

  "load": {
    "load_class": "string — klasa obciążenia",
    "max_vehicle_weight_t": "float — DMC",
    "heavy_convoy_restriction": "bool",
    "restriction_details": "string"
  },

  "flood_vulnerability": {
    "flood_zone": "bool",
    "critical_water_level_cm": "int — poziom wody powodujący zamknięcie",
    "closure_history": ["date — daty poprzednich zamknięć"],
    "water_level_sensor": "bool — czy jest czujnik poziomu wody"
  },

  "alternatives": {
    "detour_route_km": "float — długość trasy objazdowej",
    "detour_description": "string",
    "alternative_bridge_id": "string — najbliższy alternatywny most"
  },

  "evacuation_role": {
    "on_evacuation_route": "bool — czy leży na wyznaczonej trasie ewakuacyjnej",
    "route_name": "string",
    "bottleneck_risk": "enum — niski | średni | wysoki"
  }
}
```

---

### 5.2 Infrastruktura wodociągowa i energetyczna

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — operatorzy infrastruktury (PGE, wodociągi miejskie) |
| **Dostawca** | MPWiK (wodociągi), PGE Dystrybucja, PSG (gaz), operatorzy lokalni |
| **Dostępne publicznie** | BDOT10k (geometria obiektów), częściowo BIP operatorów |

**Wymagana struktura danych:**

```json
{
  "water_treatment_plants": [
    {
      "id": "string",
      "name": "string",
      "operator": "string",
      "latitude": "float",
      "longitude": "float",
      "source": "enum — rzeka | zbiornik | studnie_głębinowe",
      "source_name": "string — np. Bystrzyca, Wisła",
      "capacity_m3_per_hour": "float",
      "serves_population": "int",
      "redundancy": "enum — single | dual | triple",
      "backup_power": "bool",
      "backup_power_hours": "float",
      "flood_zone": "bool",
      "critical_chemical_stock_days": "int"
    }
  ],

  "power_substations": [
    {
      "id": "string",
      "name": "string",
      "operator": "string — PGE Dystrybucja / Tauron",
      "voltage_level": "string — np. 110/15 kV",
      "latitude": "float",
      "longitude": "float",
      "redundancy": "bool — czy zasilanie z dwóch kierunków",
      "serves_critical_objects": ["string — lista szpitali/DPS zasilanych"],
      "flood_zone": "bool",
      "failure_history_last_5y": "int — liczba awarii"
    }
  ],

  "gas_nodes": [
    {
      "id": "string",
      "name": "string",
      "type": "enum — stacja_redukcyjna | węzeł_gazowy",
      "operator": "string — PSG / GAZ-SYSTEM",
      "latitude": "float",
      "longitude": "float",
      "isolation_valve_location": "string — lokalizacja zaworów odcinających"
    }
  ]
}
```

---

## 6. Źródła danych o zagrożeniach przemysłowych

### 6.1 Zakłady Seveso / PRTR

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** (rejestry publiczne GIOŚ, BIP) + 🔴 **INTERNAL** (szczegóły operacyjne) |
| **Dostawca** | GIOŚ (rejestr Seveso), WIOŚ Lublin, zakłady (plany operacyjno-ratownicze) |
| **Dostępne publicznie** | Rejestr zakładów Seveso na stronie GIOŚ, PRTR PL, plany zewnętrzne na BIP KW PSP |
| **Dane pełne** | Plany operacyjno-ratownicze (POR) — dokumenty niejawne u komendantów PSP |
| **Kluczowe zakłady Lubelskie** | Zakłady Azotowe Puławy (Grupa Azoty), LW Bogdanka, Zakłady Chemiczne Organika-Sarzyna (sąsiednie woj., wpływ na Lubelskie) |

**Wymagana struktura danych:**

```json
{
  "facility_id": "string — nr w rejestrze GIOŚ",
  "name": "string — np. Grupa Azoty Zakłady Azotowe Puławy S.A.",
  "operator": "string",
  "regon": "string",
  "seveso_tier": "enum — upper_tier | lower_tier",
  "address": "string",
  "latitude": "float",
  "longitude": "float",

  "substances": [
    {
      "name": "string — np. amoniak, kwas azotowy, metanol",
      "cas_number": "string",
      "hazard_class": "string — GHS classification",
      "max_quantity_tonnes": "float",
      "storage_type": "enum — zbiornik | magazyn | rurociąg",
      "combustion_products": ["string — produkty spalania: np. CO, NOx, HCN, SO2"],
      "toxic_cloud_possible": "bool",
      "water_reactive": "bool",
      "explosion_risk": "bool"
    }
  ],

  "scenarios": [
    {
      "scenario_id": "string",
      "type": "enum — fire | explosion | toxic_release | spill_to_water",
      "description": "string",
      "affected_zone_radius_m": "float",
      "affected_zone_geojson": "GeoJSON — strefa zagrożenia z POR",
      "warning_zone_radius_m": "float",
      "population_at_risk": "int — ludność w strefie",
      "sensitive_objects_at_risk": ["string — szkoły/DPS/szpitale w strefie"]
    }
  ],

  "onsite_resources": {
    "industrial_fire_brigade": "bool — własna straż przemysłowa",
    "fire_water_capacity_m3": "float — zapas wody gaśniczej",
    "foam_systems": "bool",
    "gas_detection_network": "bool — sieć detektorów",
    "siren_system": "bool — system alarmowy",
    "siren_coverage_radius_m": "float"
  },

  "emergency_contacts": {
    "duty_phone_24h": "string",
    "crisis_manager": "string",
    "por_reference": "string — numer i data POR"
  },

  "environmental_receptors": {
    "nearest_school_km": "float",
    "nearest_dps_km": "float",
    "nearest_hospital_km": "float",
    "nearest_water_intake_km": "float — odległość do ujęcia wody",
    "nearest_residential_area_km": "float"
  }
}
```

---

## 7. Źródła danych populacyjnych i administracyjnych

### 7.1 GUS — Gęstość zaludnienia (siatka census)

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — WMS/WFS + BDL API |
| **Dostawca** | Główny Urząd Statystyczny |
| **URL API** | Geo: `https://geo.stat.gov.pl`; BDL: `https://bdl.stat.gov.pl/api/v1/` |
| **Autoryzacja** | BDL: anonimowy tier + wyższe limity z kluczem `X-ClientId` po rejestracji |
| **Format** | WFS: GeoPackage/SHP; BDL: JSON/XML; siatka: GeoTIFF |
| **Częstotliwość** | Spis powszechny co 10 lat (ostatni NSP 2021); szacunki BDL roczne |

**Wymagana struktura danych:**

```json
{
  "grid_cell_id": "string — identyfikator komórki siatki",
  "geometry": "GeoJSON — kwadrat 1km²",
  "centroid_lat": "float",
  "centroid_lon": "float",
  "gmina_teryt": "string",
  "powiat_teryt": "string",

  "population": {
    "total": "int",
    "male": "int",
    "female": "int",
    "age_0_6": "int — dzieci przedszkolne",
    "age_7_14": "int — dzieci szkolne",
    "age_15_18": "int — młodzież",
    "age_19_64": "int — osoby w wieku produkcyjnym",
    "age_65_plus": "int — osoby starsze",
    "age_80_plus": "int — osoby najstarsze (wysoka wrażliwość)"
  },

  "density_per_km2": "float",
  "households": "int",
  "dwellings": "int",
  "census_year": "int — 2021"
}
```

---

### 7.2 TERYT — Rejestr terytorialny

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — SOAP + pliki do pobrania |
| **Dostawca** | GUS |
| **URL** | Pliki: `https://eteryt.stat.gov.pl`; API SOAP: `https://api.stat.gov.pl/Home/TerytApi` |
| **Autoryzacja** | Pliki: otwarty dostęp; SOAP: rejestracja `teryt_ws1@stat.gov.pl` |
| **Format** | XML/CSV (pliki), SOAP (API) |

**Wymagana struktura danych:**

```json
{
  "terc": {
    "woj": "string — kod województwa (06 = lubelskie)",
    "pow": "string — kod powiatu",
    "gmi": "string — kod gminy",
    "rodz": "string — rodzaj gminy (1=miejska, 2=wiejska, 3=miejsko-wiejska)",
    "nazwa": "string",
    "stan_na": "date"
  },
  "simc": {
    "sym": "string — identyfikator miejscowości",
    "nazwa": "string",
    "rm": "string — rodzaj miejscowości"
  },
  "ulic": {
    "sym_ul": "string — identyfikator ulicy",
    "nazwa_1": "string — główna nazwa",
    "nazwa_2": "string — przymiotnik",
    "cecha": "string — ul., al., pl., os."
  },
  "boundaries_geojson": "GeoJSON — granice administracyjne woj/pow/gmi"
}
```

---

### 7.3 Geoportal / BDOT10k — Dane topograficzne i przestrzenne

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟢 **API** — WMS/WFS/WMTS publiczne |
| **Dostawca** | GUGiK (Główny Urząd Geodezji i Kartografii) |
| **URL** | Portal: `https://www.geoportal.gov.pl`; WFS BDOT: `https://mapy.geoportal.gov.pl/wss/service/PZGIK/BDOT/WFS/PobieranieBDOT10k` |
| **Autoryzacja** | Publiczny dostęp (większość warstw) |
| **Format** | WMS (PNG/JPEG), WFS (GML), WMTS (kafelki) |

**Dostępne warstwy kluczowe dla SENTINEL:**
- Granice administracyjne (województwo, powiaty, gminy)
- Budynki (w tym klasyfikacja: szkoły, szpitale, straż, policja)
- Sieć drogowa i kolejowa
- Hydrografia (rzeki, zbiorniki, wały przeciwpowodziowe)
- Sieci uzbrojenia terenu (orientacyjnie)
- Pokrycie terenu, roślinność
- Ortofotomapa (podkład)
- NMT/NMPT (numeryczny model terenu)

---

### 7.4 BIP — Biuletyny Informacji Publicznej gmin

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** — każda gmina ma własny BIP, brak standardu |
| **Dostawca** | 213 gmin + 20 powiatów + 4 miasta na prawach powiatu w Lubelskiem |
| **URL** | Indywidualnie: np. `bip.lublin.eu`, `bippulawy.pl`, `umchelm.bip.lubelskie.pl` |
| **Autoryzacja** | Publiczny dostęp |
| **Format** | HTML, PDF, DOC/DOCX, XLS/XLSX — brak standardu |
| **Częstotliwość** | Od tygodniowej do kwartalnej, zależnie od gminy |

**Typowe dane dostępne na BIP (do scrapowania):**
- Budżety i sprawozdania finansowe
- Raporty o stanie gminy
- Protokoły z sesji rad
- Dane o infrastrukturze (drogi, mosty, wodociągi)
- Raporty środowiskowe
- Zamówienia publiczne (wskazują na inwestycje i modernizacje)
- Wykazy placówek (szkoły, przedszkola, DPS, instytucje kultury)
- Plany zagospodarowania przestrzennego
- Dane o ludności (rejestry wyborców jako proxy)

**Luki i ograniczenia:**
- Całkowity brak standaryzacji — każda gmina publikuje inaczej
- Dokumenty często jako skany PDF (nie przeszukiwalne maszynowo)
- Wymaga budowy osobnych parserów per źródło (minimum: Puławy, Lublin, Chełm, Zamość dla priorytetowych gmin)
- Dane nierównej jakości i aktualności

---

## 8. Źródła danych o infrastrukturze komunikacyjnej

### 8.1 Syreny alarmowe i system ostrzegania

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — dane z Wydziałów Bezpieczeństwa i Zarządzania Kryzysowego |
| **Dostawca** | Starostwa powiatowe, urzędy gmin |

**Wymagana struktura danych:**

```json
{
  "siren_id": "string",
  "location": {
    "address": "string",
    "latitude": "float",
    "longitude": "float",
    "mounting": "enum — budynek | maszt | słup"
  },
  "type": "enum — elektroniczna | mechaniczna",
  "power_source": "enum — sieciowe | akumulatorowe | hybrydowe",
  "audibility_radius_m": "float — zasięg słyszalności",
  "coverage_geojson": "GeoJSON — poligon pokrycia",
  "remote_activation": "bool — zdalne uruchamianie",
  "last_test_date": "date",
  "operational_status": "enum — sprawna | niesprawna | wyłączona",
  "gmina": "string",
  "powiat": "string"
}
```

---

### 8.2 Infrastruktura telekomunikacyjna (BTS)

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — UKE (Urząd Komunikacji Elektronicznej), operatorzy |
| **Dostawca** | Orange, Play, T-Mobile, Plus; UKE |
| **Dostępne publicznie** | UKE publikuje częściowe dane o pozwoleniach radiowych |
| **Format** | Rejestry pozwoleń — CSV na stronie UKE |

**Wymagana struktura danych:**

```json
{
  "bts_id": "string",
  "operator": "string — Orange | T-Mobile | Play | Plus",
  "latitude": "float",
  "longitude": "float",
  "tower_height_m": "float",
  "technology": ["enum — 2G | 3G | 4G | 5G"],
  "backup_power": "bool",
  "backup_power_hours": "float",
  "backhaul_type": "enum — fiber | microwave",
  "flood_zone": "bool",
  "serves_critical_area": "bool — czy pokrywa szpital/DPS/komendę",
  "coverage_radius_estimate_km": "float"
}
```

---

## 9. Źródła danych społecznościowych i sygnałów

### 9.1 Social media — Facebook, X, portale lokalne

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** — monitoring publicznych grup i profili |
| **Źródła** | Facebook: grupy Lublin112, Puławy24, regionalne; X (Twitter); portale: lublin.eu, kurierlubelski.pl |
| **Ograniczenia prawne** | Dane publiczne, ale RODO i ToS platform ograniczają automatyczne przetwarzanie |
| **Wartość** | Często 15-30 minut szybciej niż oficjalne kanały |

**Wymagana struktura danych:**

```json
{
  "signal_id": "string — UUID",
  "source": "enum — facebook | twitter_x | local_portal | other",
  "source_url": "string",
  "source_group": "string — np. Lublin112",
  "timestamp": "datetime",
  "raw_text": "string",
  "has_image": "bool",
  "has_video": "bool",

  "ai_classification": {
    "category": "enum — fire | flood | air_quality | infrastructure_damage | accident | medical | other",
    "severity": "enum — info | warning | critical",
    "confidence": "float — 0.0-1.0",
    "summary_pl": "string — streszczenie po polsku"
  },

  "geolocation": {
    "method": "enum — gps_from_post | address_extraction | landmark_inference | manual",
    "latitude": "float",
    "longitude": "float",
    "accuracy_m": "float — szacowana dokładność",
    "location_text": "string — tekst lokalizacji z postu"
  },

  "verification_status": "enum — unverified | cross_referenced | confirmed | rejected",
  "cross_reference_source": "string — np. potwierdzone przez GIOŚ, PSP"
}
```

---

### 9.2 Raporty obywatelskie (w przyszłości)

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🟡 **SCRAPE** / przyszła integracja z systemami zgłoszeń |
| **Źródła** | Systemy typu "napraw.to", ePUAP, aplikacje gminne do zgłoszeń |

---

## 10. Źródła danych o magazynach i zaopatrzeniu

### 10.1 Magazyny kryzysowe województwa

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — Wydział Bezpieczeństwa UMWL |
| **Dostawca** | Urząd Marszałkowski, OC gmin, straż pożarna |

**Wymagana struktura danych:**

```json
{
  "warehouse_id": "string",
  "name": "string",
  "owner": "string — np. UMWL, powiat puławski, PCK",
  "type": "enum — magazyn_oc | magazyn_przeciwpowodziowy | magazyn_żywności | stacja_paliw_strategiczna",
  "address": "string",
  "latitude": "float",
  "longitude": "float",
  "capacity_m3": "float",

  "inventory": {
    "blankets": "int — koce",
    "cots": "int — łóżka polowe",
    "water_liters": "int — woda pitna",
    "food_rations": "int — racje żywnościowe",
    "generators_portable": "int — agregaty przenośne",
    "sandbags": "int — worki z piaskiem",
    "flood_barriers_m": "int — bariery przeciwpowodziowe (metry bieżące)",
    "first_aid_kits": "int",
    "ppe_sets": "int — zestawy ochrony osobistej",
    "fuel_diesel_liters": "int",
    "fuel_gasoline_liters": "int"
  },

  "access": {
    "operating_hours": "string",
    "emergency_access_procedure": "string",
    "contact_person": "string",
    "contact_phone": "string"
  },

  "last_inventory_date": "date",
  "flood_zone": "bool"
}
```

---

### 10.2 Punkty schronienia i ewakuacji

| Atrybut | Szczegóły |
|---------|-----------|
| **Metoda pozyskania** | 🔴 **INTERNAL** — plany zarządzania kryzysowego gmin/powiatów |
| **Dostawca** | Gminy, powiaty, Wydział Bezpieczeństwa UMWL |

**Wymagana struktura danych:**

```json
{
  "shelter_id": "string",
  "name": "string — np. Hala OSiR Puławy, SP nr 4 (sala gimnastyczna)",
  "type": "enum — schron_obrony_cywilnej | punkt_zbiórki | hala_sportowa | hotel_umowny | szkoła | inny",
  "address": "string",
  "latitude": "float",
  "longitude": "float",

  "capacity": {
    "persons_max": "int",
    "cots_available": "int — łóżka polowe na stanie",
    "area_sqm": "float"
  },

  "facilities": {
    "toilets": "int",
    "showers": "bool",
    "kitchen": "bool",
    "kitchen_meals_per_day": "int",
    "drinking_water": "bool",
    "heating": "bool",
    "air_conditioning": "bool",
    "medical_area": "bool",
    "pet_area": "bool — strefa dla zwierząt domowych",
    "family_separation_capable": "bool — możliwość wydzielenia stref"
  },

  "accessibility": {
    "wheelchair_accessible": "bool",
    "bus_parking": "bool — parking dla autobusów ewakuacyjnych",
    "bus_parking_capacity": "int"
  },

  "contamination_safety": {
    "hvac_sealable": "bool — możliwość uszczelnienia (przy smogu/dymu)",
    "air_filtration": "bool",
    "upwind_from_industrial_zones": "bool — pod wiatr od stref przemysłowych"
  },

  "legal": {
    "owner": "string",
    "crisis_agreement": "bool — umowa na czas kryzysu",
    "agreement_valid_until": "date",
    "insurance": "bool"
  },

  "inventory_on_site": {
    "blankets": "int",
    "first_aid_kits": "int",
    "generators": "int"
  },

  "activation": {
    "activation_time_minutes": "int — czas od decyzji do gotowości",
    "requires_personnel": "int — wymagany personel do obsługi",
    "contact_person": "string",
    "contact_phone": "string"
  }
}
```

---

## 11. Macierz priorytetów integracji

### Priorytet 1 — Krytyczne dla demo hackathonowego (mockowane teraz)

| # | Źródło | Metoda | Priorytet produkcyjny | Trudność integracji |
|---|--------|--------|----------------------|---------------------|
| 1 | GIOŚ — jakość powietrza | 🟢 API | Natychmiastowy | Niska — otwarte API |
| 2 | IMGW — wiatr i pogoda | 🟢 API | Natychmiastowy | Niska — otwarte API |
| 3 | RSPO — szkoły | 🟢 API (wniosek) | Tygodnie (wniosek o dostęp) | Średnia |
| 4 | NFZ — szpitale (lokalizacje) | 🟢 API + dane.gov.pl | Tygodnie | Średnia — wiele serwisów |
| 5 | GUS siatka populacji | 🟢 WFS | Tygodnie | Średnia — duże dane GIS |
| 6 | TERYT — granice administracyjne | 🟢 pliki + API | Natychmiastowy | Niska |

### Priorytet 2 — Ważne dla pełnej funkcjonalności

| # | Źródło | Metoda | Priorytet produkcyjny | Trudność integracji |
|---|--------|--------|----------------------|---------------------|
| 7 | Airly — czujniki lokalne | 🟢 API | Tygodnie (klucz API) | Niska |
| 8 | DPS — domy pomocy | 🟡 SCRAPE | Miesiące | Wysoka — brak API |
| 9 | Zakłady Seveso | 🟡 SCRAPE + 🔴 | Miesiące | Wysoka |
| 10 | BIP gmin (priorytetowe) | 🟡 SCRAPE | Miesiące | Bardzo wysoka — brak standardu |
| 11 | Geoportal/BDOT10k | 🟢 WFS | Tygodnie | Średnia |
| 12 | Transport (autobusy) | 🟡 + 🔴 | Miesiące | Wysoka |

### Priorytet 3 — Pełna platforma (integracje wewnętrzne)

| # | Źródło | Metoda | Priorytet produkcyjny | Trudność integracji |
|---|--------|--------|----------------------|---------------------|
| 13 | PSP — straż pożarna | 🔴 INTERNAL | Kwartały (umowy) | Bardzo wysoka |
| 14 | Policja — jednostki | 🔴 INTERNAL | Kwartały | Bardzo wysoka |
| 15 | Karetki / LPR | 🔴 INTERNAL | Kwartały | Bardzo wysoka — SWD PRM |
| 16 | Szpitale — real-time łóżka | 🔴 INTERNAL | Kwartały+ | Bardzo wysoka — integracja HIS |
| 17 | Infrastruktura wod-kan/energia | 🔴 INTERNAL | Kwartały | Bardzo wysoka |
| 18 | Mosty — dane szczegółowe | 🔴 INTERNAL | Kwartały | Wysoka |
| 19 | Syreny alarmowe | 🔴 INTERNAL | Kwartały | Średnia |
| 20 | BTS / telekomunikacja | 🔴 INTERNAL | Kwartały+ | Wysoka |
| 21 | Magazyny kryzysowe | 🔴 INTERNAL | Kwartały | Średnia |
| 22 | Punkty schronienia | 🔴 INTERNAL | Kwartały | Średnia |
| 23 | Social media monitoring | 🟡 SCRAPE | Miesiące | Wysoka — NLP + geolokalizacja |

---

### Podsumowanie ścieżki od hackatonu do produkcji

```
HACKATHON (teraz)          FAZA 1 (0-3 mies.)         FAZA 2 (3-6 mies.)         FAZA 3 (6-12 mies.)
─────────────────          ───────────────────         ───────────────────         ────────────────────
Wszystko mockowane    →    Publiczne API:              Scraping + wnioski:         Integracje wewnętrzne:
                           · GIOŚ (real)               · DPS (RJPS scraper)        · PSP (SWD-ST)
                           · IMGW (real)               · Seveso (GIOŚ reg.)        · PRM (karetki)
                           · TERYT/granice             · BIP 10 gmin               · HIS szpitali
                           · Airly                     · Social media MVP          · Policja
                           · RSPO (po wniosku)         · Transport (umowy)         · Infrastruktura kryt.
                           · NFZ (lokalizacje)                                     · Syreny, BTS
                           · GUS populacja                                         · Magazyny, schrony
                           · BDOT10k
```

---

*Dokument przygotowany na potrzeby hackathonu Civil42 — 11-12.04.2026*  
*Wszystkie struktury danych opisują docelowy stan integracji; w wersji hackathonowej dane są mockowane.*
