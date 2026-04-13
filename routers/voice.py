"""Voice briefing endpoint — generates TTS audio with synchronized word timings."""
import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException

import services.crisis_store as store
from config import settings
from models import BriefingResponse, BriefingWordTiming
from plugins import registry
from routers.v1_layers import get_air_quality_data, WEATHER_DATA
from services.briefing import BriefingContext, generate_briefing_text
from services.spatial import facilities_in_zones
from services.tts import API_BASE, VOICE_ID, synthesize_with_timestamps

from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str


@router.get("/health")
async def voice_health() -> dict:
    """Check ElevenLabs API key presence and reachability."""
    api_key = settings.elevenlabs_api_key
    if not api_key:
        log.error("Voice health check: ELEVENLABS_API_KEY is not set")
        return {"ok": False, "error": "ELEVENLABS_API_KEY not set", "api_key_present": False}

    masked = f"{api_key[:4]}…{api_key[-4:]}" if len(api_key) >= 8 else "***"
    log.info("Voice health check: key=%s", masked)

    # Hit the voices list endpoint — lightweight, no quota cost
    url = f"{API_BASE}/voices/{VOICE_ID}"
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, headers={"xi-api-key": api_key})
        if resp.status_code == 200:
            voice_name = resp.json().get("name", "?")
            log.info("Voice health check OK: voice=%s (%s)", VOICE_ID, voice_name)
            return {"ok": True, "api_key_present": True, "api_key_masked": masked,
                    "voice_id": VOICE_ID, "voice_name": voice_name}
        else:
            body = resp.text[:300]
            log.error("Voice health check failed: HTTP %s — %s", resp.status_code, body)
            return {"ok": False, "api_key_present": True, "api_key_masked": masked,
                    "http_status": resp.status_code, "error": body}
    except httpx.TimeoutException:
        log.error("Voice health check: ElevenLabs timed out")
        return {"ok": False, "api_key_present": True, "api_key_masked": masked, "error": "timeout"}
    except httpx.ConnectError as exc:
        log.error("Voice health check: connection error — %s", exc)
        return {"ok": False, "api_key_present": True, "api_key_masked": masked, "error": f"connect error: {exc}"}


@router.post("/speak")
async def speak(body: SpeakRequest) -> dict:
    """Synthesize plain text to MP3 and return as base64. Used by the demo controller."""
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="text is empty")
    result = await synthesize_with_timestamps(body.text)
    return {"audio_base64": result.audio_base64}


async def _load_resource_features() -> list[dict]:
    features: list[dict] = []
    for layer_id in ("hospitals", "schools", "social"):
        plugin = registry.get(layer_id)
        if plugin:
            data = await plugin.fetch()
            features.extend(data.get("features", []))
    return features


@router.post("/briefing", response_model=BriefingResponse)
async def voice_briefing() -> BriefingResponse:
    try:
        text = await _build_briefing_text()
    except Exception:
        log.exception("Briefing text generation failed")
        text = "Briefing niedostępny. System monitoringu aktywny. Koniec briefingu."

    log.info("Briefing text (%d chars): %s…", len(text), text[:80])

    try:
        result = await synthesize_with_timestamps(text)
    except Exception:
        log.exception("TTS failed — returning text-only")
        return _fake_briefing(text)

    if not result.tts_synthesized:
        log.warning("Briefing returning WITHOUT audio (TTS fallback active) — check /api/voice/health")

    return BriefingResponse(
        audio_base64=result.audio_base64,
        words=[BriefingWordTiming(word=w.word, start=w.start, end=w.end) for w in result.words],
        text=text,
        duration_seconds=result.duration_seconds,
        tts_synthesized=result.tts_synthesized,
    )


async def _build_briefing_text() -> str:
    active = store.list_active()
    sim_plugin   = registry.get("simulation_threat")
    flood_plugin = registry.get("flood_scenario")
    flood_state  = flood_plugin.state if flood_plugin else None

    tasks: dict[str, asyncio.Task] = {}
    if active:
        tasks["facilities"] = asyncio.create_task(_load_resource_features())
    tasks["air"] = asyncio.create_task(get_air_quality_data())
    if flood_state and flood_state.get("running"):
        from services.flood_assessment import assess_hospitals
        tasks["flood"] = asyncio.create_task(assess_hospitals())

    results = {k: await v for k, v in tasks.items()}

    affected: list[dict] = []
    if active and "facilities" in results:
        affected = facilities_in_zones(active, results["facilities"])

    flood_hospitals: list[dict] = []
    if "flood" in results:
        flood_hospitals = [
            s.model_dump() for s in results["flood"]
            if s.status in ("evacuate", "at_risk")
        ]

    ctx = BriefingContext(
        active_crises=active,
        affected=affected,
        sim_state=sim_plugin.state if sim_plugin else None,
        flood_scenario_state=flood_state,
        flood_hospitals=flood_hospitals,
        air_quality=results.get("air", []),
        weather=WEATHER_DATA,
    )
    return generate_briefing_text(ctx)


def _fake_briefing(text: str) -> BriefingResponse:
    """Generate a text-only briefing response with synthetic timings."""
    words_raw = text.split()
    wpm = 160.0
    sec_per_word = 60.0 / wpm
    words = []
    t = 0.0
    for w in words_raw:
        end = t + sec_per_word
        words.append(BriefingWordTiming(word=w, start=round(t, 3), end=round(end, 3)))
        t = end + 0.05
    duration = words[-1].end if words else 0.0
    return BriefingResponse(
        audio_base64="",
        words=words,
        text=text,
        duration_seconds=round(duration, 2),
        tts_synthesized=False,
    )
