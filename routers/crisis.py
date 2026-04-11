"""
Crisis event CRUD + Grafana read endpoints.
All routes are under /api/v1/crisis (and /api/v1/stats).
"""
from fastapi import APIRouter, HTTPException, Query

import services.crisis_store as store
from models import CrisisEvent, CrisisEventCreate, CrisisEventPatch
from plugins import registry
from services.spatial import circle_polygon, facilities_in_zones

router = APIRouter(prefix="/api/v1", tags=["crisis"])


# ── CRUD ──────────────────────────────────────────────────────────────────────

@router.post("/crisis", response_model=CrisisEvent, status_code=201)
async def create_crisis(body: CrisisEventCreate) -> CrisisEvent:
    return store.add(body)


@router.get("/crisis", response_model=list[CrisisEvent])
async def list_crisis(
    type: str | None = Query(None),
    status: str | None = Query(None),
) -> list[CrisisEvent]:
    return store.list_all(type_filter=type, status_filter=status)


@router.get("/crisis/affected")
async def affected_facilities() -> list[dict]:
    """Facilities in evac/warn zones of active events, sorted by distance."""
    active = store.list_active()
    if not active:
        return []
    facilities = await _load_resource_features()
    return facilities_in_zones(active, facilities)


@router.get("/crisis/affected-geojson")
async def affected_facilities_geojson() -> dict:
    """Affected facilities as GeoJSON FeatureCollection for Grafana map panel."""
    affected = await affected_facilities()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
            "properties": {
                "name": f["name"],
                "type": f["type"],
                "display_type": f["display_type"],
                "action": f["action"],
                "zone": f["zone"],
                "distance_km": f["distance_km"],
                "crisis_id": f["crisis_id"],
                "crisis_name": f["crisis_name"],
            },
        }
        for f in affected
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/crisis/zones-geojson")
async def zones_geojson() -> dict:
    """Evac + warn zone polygons for each active crisis event."""
    active = store.list_active()
    features = []
    for event in active:
        for zone_type, radius in (("evac", event.evac_radius_km), ("warn", event.warn_radius_km)):
            ring = circle_polygon(event.lat, event.lon, radius)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [ring]},
                "properties": {
                    "crisis_id": event.id,
                    "name": event.name,
                    "zone": zone_type,
                    "radius_km": radius,
                    "event_type": event.type,
                },
            })
    return {"type": "FeatureCollection", "features": features}


@router.get("/crisis/fires-geojson")
async def fires_geojson() -> dict:
    """All active crisis events as GeoJSON points."""
    active = store.list_active()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [e.lon, e.lat]},
            "properties": {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "evac_radius_km": e.evac_radius_km,
                "warn_radius_km": e.warn_radius_km,
                "status": e.status,
                "source": e.source,
            },
        }
        for e in active
    ]
    return {"type": "FeatureCollection", "features": features}


@router.get("/crisis/{crisis_id}", response_model=CrisisEvent)
async def get_crisis(crisis_id: str) -> CrisisEvent:
    event = store.get(crisis_id)
    if not event:
        raise HTTPException(status_code=404, detail="Crisis event not found")
    return event


@router.patch("/crisis/{crisis_id}", response_model=CrisisEvent)
async def patch_crisis(crisis_id: str, body: CrisisEventPatch) -> CrisisEvent:
    event = store.patch(crisis_id, body)
    if not event:
        raise HTTPException(status_code=404, detail="Crisis event not found")
    return event


@router.delete("/crisis/{crisis_id}", status_code=204)
async def delete_crisis(crisis_id: str) -> None:
    if not store.delete(crisis_id):
        raise HTTPException(status_code=404, detail="Crisis event not found")


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def stats() -> list[dict]:
    """
    3-element array for Grafana stat panels:
      [0] = EWAKUACJA count
      [1] = OSTRZEŻENIE / GOTOWOŚĆ count
      [2] = active fires count
    """
    active = store.list_active()
    fires_count = sum(1 for e in active if e.type == "fire")

    affected = []
    if active:
        facilities = await _load_resource_features()
        affected = facilities_in_zones(active, facilities)

    evac_count = sum(1 for f in affected if f["action"] == "EWAKUACJA")
    warn_count = sum(1 for f in affected if f["action"] in ("GOTOWOŚĆ", "OSTRZEŻENIE", "ZAMKNIĘCIE"))

    return [
        {"label": "Ewakuacja", "value": evac_count},
        {"label": "Ostrzeżenie", "value": warn_count},
        {"label": "Aktywne pożary", "value": fires_count},
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _load_resource_features() -> list[dict]:
    """Load features from hospital, school, and social plugins."""
    features: list[dict] = []
    for layer_id in ("hospitals", "schools", "social"):
        plugin = registry.get(layer_id)
        if plugin:
            data = await plugin.fetch()
            features.extend(data.get("features", []))
    return features
