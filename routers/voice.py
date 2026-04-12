"""Voice briefing endpoint — generates TTS audio with synchronized word timings."""
import logging

from fastapi import APIRouter, HTTPException

import services.crisis_store as store
from models import BriefingResponse, BriefingWordTiming
from plugins import registry
from routers.v1_layers import get_air_quality_data, WEATHER_DATA
from services.briefing import BriefingContext, generate_briefing_text
from services.spatial import facilities_in_zones
from services.tts import synthesize_with_timestamps

from pydantic import BaseModel

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    text: str


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
        active = store.list_active()

        affected: list[dict] = []
        if active:
            facilities = await _load_resource_features()
            affected = facilities_in_zones(active, facilities)

        sim_plugin   = registry.get("simulation_threat")
        flood_plugin = registry.get("flood_scenario")

        flood_state     = flood_plugin.state if flood_plugin else None
        flood_hospitals: list[dict] = []
        if flood_state and flood_state.get("running"):
            from services.flood_assessment import assess_hospitals
            statuses = await assess_hospitals()
            flood_hospitals = [
                s.model_dump() for s in statuses
                if s.status in ("evacuate", "at_risk")
            ]

        ctx = BriefingContext(
            active_crises=active,
            affected=affected,
            sim_state=sim_plugin.state if sim_plugin else None,
            flood_scenario_state=flood_state,
            flood_hospitals=flood_hospitals,
            air_quality=await get_air_quality_data(),
            weather=WEATHER_DATA,
        )
        text = generate_briefing_text(ctx)
        log.info("Briefing text (%d chars): %s…", len(text), text[:80])

        result = await synthesize_with_timestamps(text)

        return BriefingResponse(
            audio_base64=result.audio_base64,
            words=[BriefingWordTiming(word=w.word, start=w.start, end=w.end) for w in result.words],
            text=text,
            duration_seconds=result.duration_seconds,
        )
    except Exception:
        log.exception("Briefing generation failed — returning text-only fallback")
        fallback_text = "Briefing niedostępny. System monitoringu aktywny. Koniec briefingu."
        fake = _fake_briefing(fallback_text)
        return fake


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
    )
