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

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


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
        from services.flood_assessment import get_assessment
        statuses = await get_assessment()
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
