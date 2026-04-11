# SENTINEL — AI Situational Awareness Platform

## Civil42 Hackathon, 11-12.04.2026

## Project

Dual-use platform for collecting and analyzing crisis events in real time.
Multi-source ingestion → AI classification → API → Grafana dashboard + Usemaps map.

## Stack

- Python 3.12 + FastAPI + Uvicorn
- Anthropic Claude API (primary LLM)
- Ollama + Qwen 2.5 14B (offline fallback)
- SQLite (dev) / PostgreSQL (prod)
- ElevenLabs STT + TTS

## Project Structure

sentinel/
main.py # FastAPI app, CORS, startup
models.py # Pydantic schemas
database.py # SQLite setup, get_db
routers/
events.py # GET /api/events, POST /api/events
resources.py # GET /api/resources
ingest.py # POST /api/ingest (raw input → AI processing)
voice.py # POST /api/voice (ElevenLabs STT)
services/
ai.py # classify_event(text) → category, severity, summary
llm.py # LLM client with fallback: Anthropic → Ollama
tts.py # ElevenLabs TTS alerts

## API Contract

### GET /api/events

Returns flat JSON list of events for Grafana and Usemaps.
Fields: time, latitude, longitude, category, severity, status, description.

### POST /api/ingest

Accepts raw input (free text, sensor data, audio transcript).
Passes to AI classification, saves to DB.
Body: { "source": "human|sensor|radio|api", "payload": "...", "lat": 0.0, "lon": 0.0 }

### GET /api/resources

Static resources (ambulances, fire trucks) with location. Mock for now.

## LLM Fallback

llm.py checks if Anthropic API is reachable. If not → switches to Ollama at localhost:11434.
Always log which model was used (include "model" field in event).

## Coding Rules

- Type hints everywhere
- Async/await for all endpoints
- Short functions, single responsibility
- Don't over-engineer — working first, clean second
- Every endpoint returns a meaningful HTTP error if something fails

## Build Order (priority)

1. GET /api/events with mocks — Grafana needs data immediately
2. POST /api/ingest with AI classification
3. GET /api/resources mock
4. Voice endpoint (ElevenLabs)
5. Ollama fallback
6. Usemaps integration

## Environment Variables

ANTHROPIC_API_KEY=...
ELEVENLABS_API_KEY=...
OLLAMA_BASE_URL=http://localhost:11434
DATABASE_URL=sqlite:///./sentinel.db
