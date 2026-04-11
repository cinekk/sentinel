from fastapi import APIRouter, HTTPException

from models import LayerMeta
from plugins import registry

router = APIRouter(prefix="/api/layers", tags=["layers"])


@router.get("", response_model=list[LayerMeta])
async def list_layers() -> list[LayerMeta]:
    return [
        LayerMeta(
            layer_id=p.layer_id,
            name=p.layer_name,
            data_type=p.data_type,
            last_updated=p.last_updated,
        )
        for p in registry.all()
    ]


@router.get("/{layer_id}/geojson")
async def get_layer_geojson(layer_id: str) -> dict:
    plugin = registry.get(layer_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail=f"Layer '{layer_id}' not found")
    return await plugin.fetch()
