from fastapi import APIRouter, Depends
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from database import EventRow, get_db
from services.call_generator import generator

router = APIRouter(prefix="/api/emergency", tags=["emergency"])


@router.post("/start")
async def start() -> dict:
    generator.start()
    return {"status": "started", **generator.state}


@router.post("/pause")
async def pause() -> dict:
    generator.pause()
    return {"status": "paused", **generator.state}


@router.post("/resume")
async def resume() -> dict:
    generator.resume()
    return {"status": "resumed", **generator.state}


@router.post("/reset")
async def reset() -> dict:
    generator.reset()
    return {"status": "reset"}


@router.delete("/events")
async def delete_sim_events(db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(
        delete(EventRow).where(EventRow.source == "simulation")
    )
    await db.commit()
    return {"deleted": result.rowcount}
