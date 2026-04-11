# Phase 8 — Polish & Demo

> Goal: jury-ready demo; voice assistant; clean pitch flow

**Status:** 🔲 Not started

---

## Tasks

- [ ] Demo seed script `scripts/seed_demo.py` — loads preset Puławy fire scenario + 10 synthetic events

- [ ] **5-minute demo script** (in `plan/DEMO_SCRIPT.md`):
  - [ ] T+0:00 — show map with real GIOŚ air quality layer (baseline)
  - [ ] T+0:30 — trigger `POST /api/simulation/start` (Puławy fire)
  - [ ] T+1:00 — watch plume spread on map, synthetic PM2.5 layer updates
  - [ ] T+1:30 — threat zone reaches School X / DPS Y → alert fires → AI recommendation shown
  - [ ] T+2:00 — voice command: "ile łóżek szpitalnych w promieniu 30km?" → TTS response
  - [ ] T+2:30 — resource calculator result visible on map + spoken aloud
  - [ ] T+3:00 — show layer toggles (disable simulation, show only real GIOŚ) → "any data source, any frontend"

- [ ] Voice assistant endpoint: `POST /api/voice/command` — STT → parse intent → return action + TTS audio
  - [ ] Intents: "pokaż zagrożenia", "ile łóżek w promieniu 30km", "odczytaj status"

- [ ] `GET /api/health` — uptime, active plugins, LLM backend in use, last sync timestamp

- [ ] Error handling audit: every endpoint returns meaningful HTTP errors

- [ ] Dockerfile + `docker-compose.yml` (app + Ollama)

- [ ] `README.md` — how to run, env vars, demo walkthrough

## Side quests coverage

| Quest | How SENTINEL covers it | Points |
|---|---|---|
| **Marshal (10k PLN)** | Owned Leaflet map + layers + simulation + resources + threat zones + voice | Main prize |
| **ElevenLabs** | STT voice ingest + TTS alert broadcast + voice command assistant | Side quest |
| **Comtegra** (offline LLM) | `LLMRouter` Ollama fallback — system fully operational without internet | Side quest |

## Marshal bonus features

| Bonus | Implementation | Points |
|---|---|---|
| Public data scraping | `GIOSPlugin` — real PM2.5/PM10 from `powietrze.gios.gov.pl` | +10 |
| Resource calculator | `GET /api/resources/calculator` + map UI widget | +10 |
| Voice assistant | `POST /api/voice/command` + ElevenLabs TTS | +10 |
| Social media agents | Not planned — skip | — |

**Projected score: ~84/100 base + 30 bonus = ~114/140**
