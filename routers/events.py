from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, EventRow
from models import EventOut, EventCreate

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(db: AsyncSession = Depends(get_db)) -> list[EventOut]:
    result = await db.execute(select(EventRow).order_by(EventRow.time.desc()))
    rows = result.scalars().all()
    return [EventOut.model_validate(row, from_attributes=True) for row in rows]


@router.post("", response_model=EventOut, status_code=201)
async def create_event(body: EventCreate, db: AsyncSession = Depends(get_db)) -> EventOut:
    row = EventRow(
        time=body.time or datetime.now(timezone.utc),
        latitude=body.latitude,
        longitude=body.longitude,
        category=body.category,
        severity=body.severity,
        status=body.status,
        description=body.description,
        source=body.source,
        model=body.model,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return EventOut.model_validate(row, from_attributes=True)
