import math
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from plugins import registry

router = APIRouter(prefix="/api/resources", tags=["resources"])

_RESOURCE_LAYER_IDS = {"hospitals", "social", "schools", "fire_stations"}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return r * 2 * math.asin(math.sqrt(a))


async def _collect_resources() -> list[dict[str, Any]]:
    resources = []
    for layer_id in _RESOURCE_LAYER_IDS:
        plugin = registry.get(layer_id)
        if plugin is None:
            continue
        fc = await plugin.fetch()
        for feature in fc.get("features", []):
            props = feature.get("properties", {})
            coords = feature["geometry"]["coordinates"]
            resources.append({
                "id": props.get("id"),
                "name": props.get("name"),
                "type": props.get("type"),
                "layer": layer_id,
                "latitude": coords[1],
                "longitude": coords[0],
                **{k: v for k, v in props.items() if k not in ("id", "name", "type")},
            })
    return resources


@router.get("")
async def list_resources(type: str | None = Query(default=None)) -> list[dict[str, Any]]:
    resources = await _collect_resources()
    if type:
        resources = [r for r in resources if r.get("type") == type]
    return resources


@router.get("/calculator")
async def resource_calculator(
    lat: float = Query(..., description="Center latitude"),
    lon: float = Query(..., description="Center longitude"),
    radius_km: float = Query(..., gt=0, description="Search radius in km"),
    type: str | None = Query(default=None, description="Filter by resource type"),
) -> dict[str, Any]:
    resources = await _collect_resources()
    if type:
        resources = [r for r in resources if r.get("type") == type]

    in_radius = [
        r for r in resources
        if _haversine_km(lat, lon, r["latitude"], r["longitude"]) <= radius_km
    ]

    by_type: dict[str, int] = {}
    for r in in_radius:
        t = r.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    hospitals_in_radius = [r for r in in_radius if r.get("type") == "hospital"]
    beds_total = sum(r.get("beds") or 0 for r in hospitals_in_radius)
    icu_beds = sum(r.get("icu_oiom_beds") or 0 for r in hospitals_in_radius)
    beds_available = sum(r.get("beds_available_estimate") or 0 for r in hospitals_in_radius)

    return {
        "center": {"lat": lat, "lon": lon},
        "radius_km": radius_km,
        "total": len(in_radius),
        "by_type": by_type,
        "hospital_beds": beds_total,
        "hospital_icu_beds": icu_beds,
        "hospital_beds_available": beds_available,
        "resources": in_radius,
    }
