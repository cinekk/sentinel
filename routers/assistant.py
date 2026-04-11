from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.assistant import configure_view
from services.layer_meta import get_all_schemas, get_schema

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AssistantRequest(BaseModel):
    query: str
    crisis_context: str | None = None


@router.post("/configure-view")
async def api_configure_view(req: AssistantRequest) -> dict:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    return await configure_view(req.query, req.crisis_context)


@router.get("/layer-schemas")
async def api_layer_schemas() -> list[dict]:
    """Return attribute metadata for all layers (used by frontend for human-friendly labels)."""
    return [s.to_dict() for s in get_all_schemas()]


@router.get("/layer-schemas/{layer_id}")
async def api_layer_schema(layer_id: str) -> dict:
    schema = get_schema(layer_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Schema for '{layer_id}' not found")
    return schema.to_dict()
