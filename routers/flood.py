"""
Flood scenario API router.

GET  /api/flood/assessment          Full hospital status list
GET  /api/flood/summary             AI-generated situation report
POST /api/hospitals/{id}/override   Manual status override (generator, road cut)
POST /api/gauges/{id}/override      Mock gauge alert level for demo
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.flood_assessment import (
    HospitalFloodStatus,
    assess_hospitals,
    get_hospital_overrides,
    set_hospital_override,
)
from services.openrouter import chat_completion
from services.transfer import TransferRecommendation, get_transfer_recommendations

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["flood"])


# ---------------------------------------------------------------------------
# GET /api/flood/assessment
# ---------------------------------------------------------------------------

@router.get("/flood/assessment", response_model=list[HospitalFloodStatus])
async def get_flood_assessment() -> list[HospitalFloodStatus]:
    return await assess_hospitals()


# ---------------------------------------------------------------------------
# GET /api/flood/transfer-recommendations
# ---------------------------------------------------------------------------

@router.get("/flood/transfer-recommendations", response_model=list[TransferRecommendation])
async def get_transfer_recs() -> list[TransferRecommendation]:
    return await get_transfer_recommendations()


# ---------------------------------------------------------------------------
# GET /api/flood/summary
# ---------------------------------------------------------------------------

@router.get("/flood/summary")
async def get_flood_summary() -> dict:
    statuses = await assess_hospitals()

    evacuate = [s for s in statuses if s.status == "evacuate"]
    at_risk = [s for s in statuses if s.status == "at_risk"]
    can_receive = [s for s in statuses if s.can_receive]

    prompt_data = {
        "evacuate": [
            {"name": s.name, "factors": s.risk_factors, "beds": s.beds}
            for s in evacuate
        ],
        "at_risk": [
            {"name": s.name, "factors": s.risk_factors, "beds": s.beds}
            for s in at_risk
        ],
        "can_receive": [
            {"name": s.name, "city": s.name.split()[-1], "beds": s.beds, "sor": s.sor}
            for s in can_receive[:5]
        ],
        "total_hospitals": len(statuses),
    }

    messages = [
        {
            "role": "system",
            "content": (
                "Jesteś systemem wsparcia decyzji dla Urzędu Marszałkowskiego Województwa Lubelskiego "
                "podczas powodzi. Analizujesz dane o szpitalach i generujesz krótki raport sytuacyjny "
                "po polsku. Odpowiadaj wyłącznie JSON z polami: "
                "evacuate (lista stringów), at_risk (lista stringów), redirect_to (lista stringów), narrative (string 2-3 zdania)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Dane sytuacyjne:\n"
                f"- Szpitale do EWAKUACJI ({len(evacuate)}): "
                + (", ".join(s.name for s in evacuate) if evacuate else "brak")
                + f"\n- Szpitale ZAGROŻONE ({len(at_risk)}): "
                + (", ".join(s.name for s in at_risk) if at_risk else "brak")
                + f"\n- Szpitale PRZYJMUJĄCE ({len(can_receive)}): "
                + (", ".join(f"{s.name} ({s.beds} łóżek)" for s in can_receive[:5]) if can_receive else "brak")
                + f"\n\nWygeneruj raport JSON."
            ),
        },
    ]

    try:
        result = await chat_completion(messages, max_tokens=512, temperature=0.2)
    except Exception as exc:
        logger.warning("LLM summary failed: %s", exc)
        result = {
            "evacuate": [f"{s.name} — {', '.join(s.risk_factors[:1])}" for s in evacuate],
            "at_risk": [f"{s.name} — {', '.join(s.risk_factors[:1])}" for s in at_risk],
            "redirect_to": [f"{s.name} ({s.beds} łóżek)" for s in can_receive[:3]],
            "narrative": (
                f"Sytuacja powodziowa: {len(evacuate)} placówek wymaga ewakuacji, "
                f"{len(at_risk)} jest zagrożonych. "
                f"Dostępne łóżka w {len(can_receive)} szpitalach poza strefą zagrożenia."
            ),
        }

    result.setdefault("evacuate", [])
    result.setdefault("at_risk", [])
    result.setdefault("redirect_to", [])
    result.setdefault("narrative", "")
    result.pop("_model", None)
    return result


# ---------------------------------------------------------------------------
# POST /api/hospitals/{id}/override
# ---------------------------------------------------------------------------

class HospitalOverride(BaseModel):
    generator_state: str | None = None   # "ok" | "degraded" | "offline"
    personnel_pct: int | None = None     # 0–100
    road_cut: bool | None = None


@router.post("/hospitals/{hospital_id}/override")
async def override_hospital(hospital_id: str, body: HospitalOverride) -> dict:
    patch: dict = {}
    if body.generator_state is not None:
        if body.generator_state not in ("ok", "degraded", "offline"):
            raise HTTPException(status_code=422, detail="generator_state must be ok/degraded/offline")
        patch["generator_state"] = body.generator_state
    if body.personnel_pct is not None:
        patch["personnel_pct"] = max(0, min(100, body.personnel_pct))
    if body.road_cut is not None:
        patch["road_cut"] = body.road_cut

    if not patch:
        raise HTTPException(status_code=422, detail="No override fields provided")

    set_hospital_override(hospital_id, patch)
    return {"ok": True, "hospital_id": hospital_id, "applied": patch}


@router.get("/hospitals/overrides")
async def list_hospital_overrides() -> dict:
    return get_hospital_overrides()


# ---------------------------------------------------------------------------
# POST /api/gauges/{id}/override
# ---------------------------------------------------------------------------

class GaugeOverride(BaseModel):
    alert_level: str   # "normal" | "warning" | "alarm"


@router.post("/gauges/{gauge_id}/override")
async def override_gauge(gauge_id: str, body: GaugeOverride) -> dict:
    from plugins.imgw_hydro import set_gauge_override

    if body.alert_level not in ("normal", "warning", "alarm"):
        raise HTTPException(status_code=422, detail="alert_level must be normal/warning/alarm")

    set_gauge_override(gauge_id, body.alert_level)  # type: ignore[arg-type]

    # Invalidate assessment cache so next call recomputes
    from services.flood_assessment import _cache as _fc
    import services.flood_assessment as fa
    fa._cache = None
    fa._cache_time = None

    return {"ok": True, "gauge_id": gauge_id, "alert_level": body.alert_level}
