# Phase 6 — AI Classification & Voice

> Goal: every ingested event gets AI-classified; voice in/out works
> (Moved after data layers: demo needs visible objects before AI narrative)

**Status:** 🔲 Not started

---

## Tasks

- [ ] `services/llm.py` — `LLMRouter`
  - [ ] Try Anthropic Claude (`claude-sonnet-4-6`)
  - [ ] Fallback: Ollama at `OLLAMA_BASE_URL` with Qwen 2.5 14B
  - [ ] Log which model was used; include `model` field on every event

- [ ] `services/ai.py` — `classify_event(text, context) -> ClassificationResult`
  - [ ] Fields: `category`, `severity`, `summary`, `recommended_actions: list[str]`, `affected_radius_km`
  - [ ] For simulation ticks: generate narrative summary of current threat state
  - [ ] For targeted intersection alerts: specific recommendation per object type
    - e.g. "Zamknij szkołę X", "Ewakuuj DPS Y"

- [ ] `services/tts.py` — `ElevenLabs`
  - [ ] `synthesize(text) -> bytes` — TTS alert audio
  - [ ] `transcribe(audio_bytes) -> str` — STT from radio/voice

- [ ] `routers/ingest.py` — `POST /api/ingest` → classify → save → return `IngestResponse`

- [ ] `routers/voice.py` — `POST /api/voice` → STT → ingest pipeline

## Notes

- Ollama model availability on demo machine — confirm `qwen2.5:14b` is pulled beforehand
- ElevenLabs API key required (`ELEVENLABS_API_KEY` env var)
