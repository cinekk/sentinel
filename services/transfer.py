"""
Hospital transfer recommendation service.

For each hospital in 'evacuate' or 'at_risk' status, returns the top-3
nearest hospitals that are operational and can_receive == True.
"""
from __future__ import annotations

from pydantic import BaseModel

from services.spatial import haversine


class TransferTarget(BaseModel):
    hospital_id: str
    name: str
    short_name: str
    lat: float
    lon: float
    distance_km: float
    available_beds: int
    has_sor: bool


class TransferRecommendation(BaseModel):
    from_hospital_id: str
    from_name: str
    from_lat: float
    from_lon: float
    status: str
    targets: list[TransferTarget]


async def get_transfer_recommendations() -> list[TransferRecommendation]:
    from services.flood_assessment import assess_hospitals

    statuses = await assess_hospitals()

    receivers = [s for s in statuses if s.can_receive]
    sources   = [s for s in statuses if s.status in ("evacuate", "at_risk")]

    # Build a lookup for short_name / sor from the hospital DB
    from sqlalchemy import select
    from database import HospitalRow, SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(select(HospitalRow))
        rows = result.scalars().all()

    row_by_id: dict[str, HospitalRow] = {
        (r.facility_id or str(r.id)): r for r in rows
    }

    recommendations: list[TransferRecommendation] = []

    for src in sources:
        candidates = sorted(
            receivers,
            key=lambda r: haversine(src.lat, src.lon, r.lat, r.lon),
        )[:3]

        targets = []
        for c in candidates:
            row = row_by_id.get(c.hospital_id)
            targets.append(TransferTarget(
                hospital_id=c.hospital_id,
                name=c.name,
                short_name=(row.short_name if row and row.short_name else c.name[:20]),
                lat=c.lat,
                lon=c.lon,
                distance_km=round(haversine(src.lat, src.lon, c.lat, c.lon), 1),
                available_beds=c.beds,
                has_sor=c.sor,
            ))

        recommendations.append(TransferRecommendation(
            from_hospital_id=src.hospital_id,
            from_name=src.name,
            from_lat=src.lat,
            from_lon=src.lon,
            status=src.status,
            targets=targets,
        ))

    return recommendations
