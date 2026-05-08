# Lubelskie GIS API — Kontrakt dla backendu

**Wersja:** 0.3.0  
**Base URL:** `http://<host>:8000`  
**Kontekst:** Grafana dashboard "Centrum Zarządzania Kryzysowego" odpytuje te endpointy co 5s przez Infinity datasource. Zmiana kształtu response'a = zepsuty dashboard.

**Źródło:** Kontrakt od kolegi z hackathonu Civil42 (11-12.04.2026). Jego skrypt demo zarządza pożarami przez CRUD. Nasze symulatora pożarów ma współistnieć z tym CRUD-em w ujednoliconym wyjściu `/api/v1/crisis/*`.

---

## Architektura

```
┌──────────────────┐       ┌──────────────────┐       ┌─────────────┐
│  Operator (curl) │──────>│  Backend API     │<──────│  Grafana    │
│  POST/PATCH/DEL  │       │  :8000           │       │  Infinity   │
│  /api/v1/fires   │       │                  │       │  plugin     │
└──────────────────┘       └──────────────────┘       └─────────────┘
                                  │
                                  ▼
                           ┌──────────────┐
                           │  Data store  │
                           │  (fires +    │
                           │   facilities)│
                           └──────────────┘
```

Dashboard jest **read-only** — czyta dane z endpointów GET. Operator zarządza pożarami przez POST/PATCH/DELETE. Dashboard odświeża się automatycznie.

---

## 1. Zarządzanie pożarami (CRUD)

### `POST /api/v1/fires` — Zgłoś nowy pożar

**Request body:**
```json
{
  "lat": 51.22,
  "lon": 22.56,
  "name": "Pożar zakładu chemicznego Lublin-Południe",
  "evac_radius_km": 5.0,
  "warn_radius_km": 12.0
}
```

| Pole | Typ | Wymagane | Default | Opis |
|------|-----|----------|---------|------|
| `lat` | float | ✅ | — | Szerokość geograficzna (WGS84) |
| `lon` | float | ✅ | — | Długość geograficzna (WGS84) |
| `name` | string | ❌ | `"Pożar"` | Opis zdarzenia |
| `evac_radius_km` | float | ❌ | `5.0` | Promień strefy ewakuacji w km |
| `warn_radius_km` | float | ❌ | `12.0` | Promień strefy ostrzeżenia w km |

**Response `200`:**
```json
{
  "id": "3606afc2",
  "status": "active",
  "affected_facilities": 334,
  "lat": 51.22,
  "lon": 22.56,
  "name": "Pożar zakładu chemicznego Lublin-Południe",
  "evac_radius_km": 5.0,
  "warn_radius_km": 12.0,
  "created_at": 1775919930.305
}
```

`affected_facilities` — liczba obiektów wrażliwych w strefie ostrzeżenia tego pożaru.

---

### `GET /api/v1/fires` — Lista wszystkich pożarów

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU** — panel "Aktywne pożary"

**Response `200`:** Array obiektów fire.
```json
[
  {
    "id": "3606afc2",
    "lat": 51.22,
    "lon": 22.56,
    "name": "Pożar zakładu chemicznego Lublin-Południe",
    "evac_radius_km": 5.0,
    "warn_radius_km": 12.0,
    "status": "active",
    "created_at": 1775919930.305
  }
]
```

**Wymagane pola w response (Grafana czyta):**

| Pole | Typ | Opis |
|------|-----|------|
| `id` | string | Unikalny identyfikator pożaru |
| `name` | string | Opis zdarzenia |
| `status` | string | `"active"` lub `"extinguished"` — dokładnie te wartości! |
| `evac_radius_km` | number | Promień strefy ewakuacji |
| `warn_radius_km` | number | Promień strefy ostrzeżenia |

Pusta tablica `[]` gdy brak pożarów — to OK, Grafana pokaże "No data".

---

### `GET /api/v1/fires/{fire_id}` — Szczegóły pożaru

**Response `200`:** Obiekt fire (jak wyżej, pojedynczy).  
**Response `404`:** `{"detail": "Fire {fire_id} not found"}`

---

### `PATCH /api/v1/fires/{fire_id}` — Aktualizuj pożar

**Request body (wszystkie pola opcjonalne):**
```json
{
  "evac_radius_km": 8.0,
  "warn_radius_km": 15.0,
  "name": "Nowa nazwa",
  "status": "extinguished"
}
```

**Response `200`:** Zaktualizowany obiekt fire + `affected_facilities`.  
**Response `404`:** `{"detail": "Fire {fire_id} not found"}`

---

### `DELETE /api/v1/fires/{fire_id}` — Usuń pożar

**Response `200`:** `{"deleted": "3606afc2"}`  
**Response `404`:** `{"detail": "Fire {fire_id} not found"}`

---

## 2. Endpointy kryzysowe (READ-ONLY, Grafana)

Dynamiczne — odpowiadają na podstawie aktualnie aktywnych pożarów. Gdy brak aktywnych pożarów, zwracają puste kolekcje.

### `GET /api/v1/stats` — Statystyki dla stat paneli

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU** — 3 stat panele

**Response `200`:** Array o stałej długości 3, w stałej kolejności:
```json
[
  {"metric": "Strefa ewakuacji", "value": 288},
  {"metric": "Strefa ostrzeżenia", "value": 360},
  {"metric": "Aktywne pożary", "value": 1}
]
```

⚠️ **KRYTYCZNE:** Grafana czyta po indeksie (`$.[0]`, `$.[1]`, `$.[2]`), więc kolejność jest stała.
- Index 0 = obiekty w strefie ewakuacji
- Index 1 = łączna liczba obiektów w strefie ostrzeżenia
- Index 2 = liczba aktywnych pożarów

---

### `GET /api/v1/crisis/affected` — Zagrożone obiekty (tabela)

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU** — panel "Rekomendowane działania"

**Response `200`:** Array, posortowany po `distance_km` rosnąco.
```json
[
  {
    "name": "Caritas Archidiecezji Lubelskiej",
    "type": "DPS/Placówka",
    "lat": 51.245,
    "lon": 22.555,
    "distance_km": 3.0,
    "action": "EWAKUACJA",
    "fire_id": "3606afc2",
    "fire_name": "Pożar zakładu chemicznego Lublin-Południe"
  }
]
```

**Logika action:**

| Typ obiektu | W strefie ewakuacji | W strefie ostrzeżenia |
|-------------|--------------------|-----------------------|
| Szpital | `EWAKUACJA` | `GOTOWOŚĆ` |
| DPS/Placówka | `EWAKUACJA` | `GOTOWOŚĆ` |
| Szkoła | `ZAMKNIĘCIE` | `OSTRZEŻENIE` |

---

### `GET /api/v1/crisis/affected-geojson` — Zagrożone obiekty (mapa)

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU** — panel "Mapa sytuacyjna" (warstwa markers)

**Response `200`:** GeoJSON FeatureCollection z Point features.

⚠️ `coordinates` = `[longitude, latitude]` (kolejność GeoJSON — lon first!)

---

### `GET /api/v1/crisis/zones-geojson` — Strefy zagrożenia (polygony)

GeoJSON FeatureCollection z Polygon features. Dla każdego aktywnego pożaru — 2 polygony (evacuation + warning). `zone` = `"evacuation"` | `"warning"`.

---

### `GET /api/v1/crisis/fires-geojson` — Lokalizacje pożarów (punkty)

GeoJSON FeatureCollection z Point features (pozycje pożarów).

---

## 3. Dane statyczne (warstwy bazowe)

### `GET /api/v1/layers/air-quality` — Stacje pomiarowe

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU**

**Response `200`:** GeoJSON FeatureCollection.
Properties: `name` (string), `pm25` (number), `pm10` (number), `status` (`"critical"` | `"warning"` | `"ok"`)

---

### `GET /api/v1/layers/weather` — Dane meteorologiczne

🔴 **GRAFANA ZALEŻY OD TEGO ENDPOINTU**

**Response `200`:** GeoJSON FeatureCollection.
Properties: `name` (string), `temp_c` (number), `wind_dir` (string), `wind_speed_kmh` (number), `humidity_pct` (number)

---

### `GET /api/v1/layers/hospitals` — Szpitale
### `GET /api/v1/layers/schools` — Szkoły
### `GET /api/v1/layers/social-facilities` — Placówki społeczne

GeoJSON FeatureCollection z Point features.

---

## Podsumowanie: co Grafana MUSI dostać

| Panel Grafana | Endpoint | Format | Krytyczne pola |
|--------------|----------|--------|----------------|
| Mapa sytuacyjna | `GET /api/v1/crisis/affected-geojson` | GeoJSON FeatureCollection (Points) | coordinates [lon,lat], name, type, action |
| Aktywne pożary | `GET /api/v1/fires` | JSON Array | id, name, status, evac/warn radius |
| Stat: pożary | `GET /api/v1/stats` → index 2 | `{"value": N}` | value (number) |
| Stat: ewakuacja | `GET /api/v1/stats` → index 0 | `{"value": N}` | value (number) |
| Stat: ostrzeżenie | `GET /api/v1/stats` → index 1 | `{"value": N}` | value (number) |
| Tabela działań | `GET /api/v1/crisis/affected` | JSON Array | action, type, name, distance_km |
| Jakość powietrza | `GET /api/v1/layers/air-quality` | GeoJSON FeatureCollection | name, pm25, pm10, status |
| Pogoda | `GET /api/v1/layers/weather` | GeoJSON FeatureCollection | name, temp_c, wind_dir, wind_speed_kmh, humidity_pct |

---

## CORS

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
```

## Notatki implementacyjne

- **Haversine** — do kalkulacji odległości obiektów od pożarów używamy wzoru haversine (`R = 6371 km`)
- **Deduplikacja** — gdy obiekty są w zasięgu kilku pożarów, zwracamy je raz (najbliższy pożar)
- **Sortowanie** — `/crisis/affected` sortuje po `distance_km` rosnąco
- **GeoJSON coordinates** — zawsze `[lon, lat]`, NIE `[lat, lon]`
- **Status pożaru** — `"extinguished"` = pożar nieaktywny, nie wpływa na obliczenia kryzysowe
