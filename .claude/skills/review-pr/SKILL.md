---
name: review-pr
description: Review a PR diff with a fresh context window — no author blindness. Loads CLAUDE.md and the relevant subsystem doc, then checks for async correctness, error handling, prompt injection, and LLM pipeline safety.
---

# /review-pr — Sentinel PR Review (Fresh Context)

Review a PR diff as if you have never seen the code before. The goal is to catch what the author's session missed.

## Invocation

```
/review-pr [PR number or branch name]
```

If no argument is given, review the current branch diff against `main`.

## Steps

### 1. Load context

Read in parallel:
- `CLAUDE.md` — project constraints, Do Not rules, LLM pipeline rules
- The most relevant doc from `docs/` based on what files changed:
  - `docs/ai-assistant.md` — if `services/assistant.py` or `services/openrouter.py` changed
  - `docs/voice-briefing.md` — if `services/briefing.py`, `services/tts.py`, or `routers/voice.py` changed
  - `docs/flood-assessment.md` — if `services/flood_assessment.py` or `routers/flood*.py` changed
  - `docs/evacuation-dispatch.md` — if `services/evacuation*.py` changed
  - `docs/event-ingestion.md` — if `routers/events.py` or `services/crisis_store.py` changed
  - `docs/simulation-demo.md` — if `plugins/simulation.py` or `routers/flood_scenario.py` changed

### 2. Get the diff

```bash
# For a PR number:
gh pr diff <number>

# For current branch vs main:
git diff main...HEAD
```

### 3. Review checklist

Work through each area and report findings:

#### Async correctness
- No sync-blocking calls inside `async def` route handlers (no `time.sleep`, blocking I/O, sync DB calls)
- All `await` points are correct — no fire-and-forget where a result is expected

#### Error handling at API boundaries
- Every endpoint returns a meaningful HTTP error on failure (400/422/500 — not a bare exception)
- External API calls (OpenRouter, ElevenLabs, IMGW, GIOŚ) have try/except with fallback or logged error

#### Prompt injection vectors
- `/api/ingest` equivalent endpoints: user-supplied payload is never interpolated directly into prompts without sanitization
- Assistant query endpoint: user message is isolated from system prompt construction

#### LLM pipeline protection (if assistant.py or openrouter.py touched)
- `SYSTEM_PROMPT` unchanged unless explicitly intended
- Three-way sync intact: `_build_view_config_schema()` + `services/layer_meta.py` + `_LAYER_KEYWORDS`
- `_validate_and_normalize()` not weakened or bypassed

#### TTS input safety (if briefing.py or tts.py touched)
- Only output of `generate_briefing_text()` reaches ElevenLabs
- No raw crisis payload, user input, or LLM output routed to TTS

#### Do Not violations
- No `services/ai.py` or `services/llm.py` created
- No build step added to frontend
- No old GIOŚ API paths (`/pjp-api/rest/`)
- `routers/ingest.py` not used as a pattern

### 4. Report

For each finding: **location** (file:line), **severity** (blocker / warning / note), **description**, **suggested fix**.

If no issues found, say so explicitly — a clean review is a useful signal.

Format:

```
## Review: <PR title or branch>

### Blockers
- `services/tts.py:42` — raw crisis description passed to ElevenLabs. Only briefing text should reach TTS.

### Warnings
- `routers/flood.py:18` — no try/except around IMGW fetch; a network failure will return 500.

### Notes
- `models.py:55` — unused field `foo` added but never referenced.

### Clean
- Async correctness: OK
- LLM pipeline: OK
```
