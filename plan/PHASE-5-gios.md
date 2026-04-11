# Phase 5 — Real Air Quality Data (GIOŚ)

> Goal: real PM2.5/PM10 displayed alongside simulation — earns +10 bonus points

**Status:** 🔲 Not started

---

## Tasks

- [ ] `plugins/gios.py` — `GIOSPlugin`
  - [ ] Fetch PM2.5/PM10 from GIOŚ REST API (v1, no auth):
    - stations: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll`
    - sensors per station: `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/sensors/{stationId}`
    - readings: `GET https://api.gios.gov.pl/pjp-api/v1/rest/data/getData/{sensorId}`
    - AQ index: `GET https://api.gios.gov.pl/pjp-api/v1/rest/aqindex/getIndex/{stationId}`
  - [ ] Filter to stations in Lublin voivodeship (bbox filter by coords)
  - [ ] Returns GeoJSON FeatureCollection with sensor readings as properties
  - [ ] Cache with 10-min TTL (API is slow)
- [ ] Simulation synthetic PM layer displayed separately alongside real GIOŚ layer
- [ ] Smoke test: real station markers visible on map with PM2.5 values in popups

## Notes

- GIOŚ station IDs near Puławy: use `GET https://api.gios.gov.pl/pjp-api/v1/rest/station/findAll`, filter by coords
- Lublin voivodeship bbox approx: lat 50.4–51.8, lon 21.5–24.1
