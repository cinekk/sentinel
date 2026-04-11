# SENTINEL

AI situational awareness platform for real-time crisis management.
Built for Civil42 Hackathon 2026 — scenario: industrial fire / smog crisis in Lublin voivodeship.

## Quickstart

```bash
# 1. Clone and enter the repo
git clone git@github.com:cinekk/sentinel.git && cd sentinel

# 2. Create virtual environment and install dependencies
uv venv && uv pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys

# 4. Start the server
uv run uvicorn main:app --reload
```

Server runs at `http://localhost:8000`.

- API docs: `http://localhost:8000/docs`
- Events feed: `http://localhost:8000/api/events`
- Health check: `http://localhost:8000/api/health`

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (Phase 4) | Claude API key for event classification |
| `ELEVENLABS_API_KEY` | Yes (Phase 4) | ElevenLabs STT/TTS |
| `OLLAMA_BASE_URL` | No | Ollama endpoint for offline LLM fallback (default: `http://localhost:11434`) |
| `DATABASE_URL` | No | SQLite path (default: `sqlite+aiosqlite:///./sentinel.db`) |
| `USEMAPS_BASE_URL` | No | useMaps instance URL (Phase 6) |
| `USEMAPS_LOGIN` | No | useMaps credentials (Phase 6) |
| `USEMAPS_PASSWORD` | No | useMaps credentials (Phase 6) |

## Stack

- Python 3.12 + FastAPI + Uvicorn
- SQLite (async via aiosqlite + SQLAlchemy)
- Anthropic Claude (`claude-sonnet-4-6`) with Ollama fallback
- ElevenLabs STT + TTS
