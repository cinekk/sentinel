"""
Compatibility alias: /api/v1/fires → crisis store with type="fire".
Ensures the buddy's demo script works without changes.
"""
from fastapi import APIRouter, HTTPException

import services.crisis_store as store
from models import CrisisEvent, CrisisEventCreate, CrisisEventPatch

router = APIRouter(prefix="/api/v1/fires", tags=["fires-compat"])


@router.post("", response_model=CrisisEvent, status_code=201)
async def create_fire(body: CrisisEventCreate) -> CrisisEvent:
    body.type = "fire"
    return store.add(body)


@router.get("", response_model=list[CrisisEvent])
async def list_fires(status: str | None = None) -> list[CrisisEvent]:
    return store.list_all(type_filter="fire", status_filter=status)


@router.get("/{fire_id}", response_model=CrisisEvent)
async def get_fire(fire_id: str) -> CrisisEvent:
    event = store.get(fire_id)
    if not event or event.type != "fire":
        raise HTTPException(status_code=404, detail="Fire not found")
    return event


@router.patch("/{fire_id}", response_model=CrisisEvent)
async def patch_fire(fire_id: str, body: CrisisEventPatch) -> CrisisEvent:
    event = store.get(fire_id)
    if not event or event.type != "fire":
        raise HTTPException(status_code=404, detail="Fire not found")
    updated = store.patch(fire_id, body)
    return updated  # type: ignore[return-value]


@router.delete("/{fire_id}", status_code=204)
async def delete_fire(fire_id: str) -> None:
    event = store.get(fire_id)
    if not event or event.type != "fire":
        raise HTTPException(status_code=404, detail="Fire not found")
    store.delete(fire_id)
