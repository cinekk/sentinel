"""ElevenLabs TTS with per-word timestamps (karaoke sync)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from config import settings

log = logging.getLogger(__name__)

VOICE_ID = "onwK4e9ZLuTAKqWW03F9"  # Daniel — clear male narration voice
MODEL_ID = "eleven_multilingual_v2"
OUTPUT_FORMAT = "mp3_44100_128"
API_BASE = "https://api.elevenlabs.io/v1"
TIMEOUT_S = 20


@dataclass
class WordTiming:
    word: str
    start: float
    end: float


@dataclass
class TtsResult:
    audio_base64: str
    words: list[WordTiming]
    duration_seconds: float
    tts_synthesized: bool = True  # False when falling back to fake timings


def _aggregate_words(alignment: dict) -> list[WordTiming]:
    """Convert per-character timestamps to per-word timestamps."""
    chars: list[str] = alignment["characters"]
    starts: list[float] = alignment["character_start_times_seconds"]
    ends: list[float] = alignment["character_end_times_seconds"]

    words: list[WordTiming] = []
    buf: list[str] = []
    word_start: float = 0.0
    word_end: float = 0.0

    for i, ch in enumerate(chars):
        if ch in (" ", "\n"):
            if buf:
                words.append(WordTiming("".join(buf), round(word_start, 3), round(word_end, 3)))
                buf.clear()
            continue

        if not buf:
            word_start = starts[i]
        buf.append(ch)
        word_end = ends[i]

    if buf:
        words.append(WordTiming("".join(buf), round(word_start, 3), round(word_end, 3)))

    return words


def _fake_timings(text: str, wpm: float = 160) -> TtsResult:
    """Generate synthetic word timings when TTS is unavailable.

    Produces a text-only result (no audio) with evenly-spaced word timings
    so the frontend karaoke animation still works visually.
    """
    raw_words = text.split()
    sec_per_word = 60.0 / wpm
    words: list[WordTiming] = []
    t = 0.0
    for w in raw_words:
        end = t + sec_per_word
        words.append(WordTiming(w, round(t, 3), round(end, 3)))
        t = end + 0.05  # tiny gap between words
    duration = words[-1].end if words else 0.0
    return TtsResult(audio_base64="", words=words, duration_seconds=round(duration, 2), tts_synthesized=False)


async def synthesize_with_timestamps(text: str) -> TtsResult:
    """Call ElevenLabs TTS with-timestamps and return audio + word timings.

    Falls back to synthetic timings (no audio) if TTS fails for any reason.
    """
    api_key = settings.elevenlabs_api_key
    if not api_key:
        log.error("ELEVENLABS_API_KEY not set — no audio will be produced (text-only fallback)")
        return _fake_timings(text)

    masked = f"{api_key[:4]}…{api_key[-4:]}" if len(api_key) >= 8 else "***"
    log.info("ElevenLabs TTS request: voice=%s model=%s format=%s key=%s text_len=%d",
             VOICE_ID, MODEL_ID, OUTPUT_FORMAT, masked, len(text))

    url = f"{API_BASE}/text-to-speech/{VOICE_ID}/with-timestamps"
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "text": text,
        "model_id": MODEL_ID,
        "voice_settings": {"stability": 0.7, "similarity_boost": 0.8},
        "output_format": OUTPUT_FORMAT,
    }

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(url, json=payload, headers=headers)
            log.debug("ElevenLabs HTTP %s, content-type=%s, body_len=%d",
                      resp.status_code, resp.headers.get("content-type", "?"), len(resp.content))
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raw_body = ""
        try:
            raw_body = exc.response.text
            detail = exc.response.json().get("detail", {})
            if isinstance(detail, dict):
                detail = detail.get("message", str(detail))
            else:
                detail = str(detail)
        except Exception:
            detail = raw_body or str(exc)
        log.error("ElevenLabs HTTP %s error — falling back to text-only. Detail: %s",
                  exc.response.status_code, detail)
        return _fake_timings(text)
    except httpx.TimeoutException as exc:
        log.error("ElevenLabs timed out after %ss — falling back to text-only. %s", TIMEOUT_S, exc)
        return _fake_timings(text)
    except httpx.ConnectError as exc:
        log.error("ElevenLabs connection failed — falling back to text-only. %s", exc)
        return _fake_timings(text)

    data = resp.json()
    audio_b64: str = data.get("audio_base64", "")
    if not audio_b64:
        log.error("ElevenLabs returned 200 but audio_base64 is empty — response keys: %s", list(data.keys()))
        return _fake_timings(text)

    alignment = data.get("alignment")
    if not alignment:
        log.error("ElevenLabs response missing 'alignment' key — keys: %s", list(data.keys()))
        return _fake_timings(text)

    words = _aggregate_words(alignment)
    duration = words[-1].end if words else 0.0

    log.info("TTS OK: %d words, %.1fs, audio_b64_len=%d", len(words), duration, len(audio_b64))
    return TtsResult(audio_base64=audio_b64, words=words, duration_seconds=round(duration, 2))
