# Phase 7 — useMaps Integration

> Goal: all layers auto-pushed to useMaps; fallback is own Leaflet frontend

**Status:** 🔲 Not started

---

## Tasks

- [ ] `services/usemaps.py` — `UseMapsClient`
  - [ ] `authenticate(login, password) -> token` via `POST /api/auth/login`
  - [ ] `push_features(layer_id, geojson) -> None` — upsert features on a layer
  - [ ] Coordinate transform: WGS84 → EPSG:2180 (using `pyproj`)
  - [ ] Token refresh on 401

- [ ] `services/sync.py` — `SyncService`
  - [ ] On event creation: push updated layer to useMaps
  - [ ] On simulation tick: push `threat_zones` + `events` layers

- [ ] `routers/sync.py` — `POST /api/sync` (force full resync of all layers)

- [ ] Layer mapping: define which plugin layers map to which useMaps layer IDs

- [ ] Add `pyproj` to `requirements.txt`

## Notes / Open questions

- useMaps layer IDs — need to be created in useMaps UI first; **get IDs from teammate**
- useMaps instance URL — **confirm with teammate** (env var `USEMAPS_BASE_URL`)
- **Fallback**: if useMaps credentials/URL unavailable, own Leaflet frontend is the demo surface — no demo blocker
