"""
ISOK flood zone point-in-polygon service.

Loads polygon data from FloodZonesPlugin (ISOK WFS) and caches it.
Provides point_in_flood_zone(lat, lon) -> "p1" | "p10" | None

P=1%  — 1-in-100-year flood (high hazard; road cut trigger)
P=10% — 1-in-10-year flood (moderate hazard; warning trigger)

No external dependencies — pure math ray casting.
"""
from __future__ import annotations

import logging
from typing import Literal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Internal polygon cache — populated lazily from FloodZonesPlugin
# ---------------------------------------------------------------------------

_p1_rings: list[list[list[float]]] = []    # list of [lon, lat] rings
_p10_rings: list[list[list[float]]] = []
_loaded = False


def _classify_hazard_type(props: dict) -> Literal["p1", "p10"] | None:
    """
    Attempt to classify an ISOK feature as P=1% or P=10% from its properties.
    INSPIRE NaturalHazardArea features carry return period info in various fields.
    """
    ht: str = (props.get("hazard_type") or "").lower()

    # Direct INSPIRE URI fragments: "p1", "q1pct", "100year" → P=1%
    if any(tok in ht for tok in ("p1pct", "q1", "100year", "_01_", "p0.01")):
        return "p1"
    # "p10pct", "10year" → P=10%
    if any(tok in ht for tok in ("p10pct", "q10", "10year", "_10_", "p0.10")):
        return "p10"

    # Fallback: anything labelled as a flood hazard zone → treat as P=10%
    if "flood" in ht or "powodz" in ht or "zal" in ht or ht != "":
        return "p10"

    return None


def _extract_rings(geometry: dict) -> list[list[list[float]]]:
    """Return all exterior rings from a Polygon or MultiPolygon geometry."""
    gtype = geometry.get("type", "")
    coords = geometry.get("coordinates", [])
    rings: list[list[list[float]]] = []
    if gtype == "Polygon":
        if coords:
            rings.append(coords[0])  # exterior ring
    elif gtype == "MultiPolygon":
        for poly in coords:
            if poly:
                rings.append(poly[0])
    return rings


async def load_flood_zones() -> None:
    """
    Load ISOK flood zone polygons from FloodZonesPlugin into the module cache.
    Call once at startup (registered in lifespan).
    """
    global _p1_rings, _p10_rings, _loaded

    # Import here to avoid circular imports at module load time
    from plugins.flood_zones import FloodZonesPlugin

    plugin = FloodZonesPlugin()
    try:
        fc = await plugin.fetch()
    except Exception as exc:
        logger.warning("FloodZonesPlugin fetch failed — flood zone assessment disabled: %s", exc)
        _loaded = True
        return

    p1: list[list[list[float]]] = []
    p10: list[list[list[float]]] = []

    for feature in fc.get("features", []):
        geom = feature.get("geometry") or {}
        props = feature.get("properties") or {}
        level = _classify_hazard_type(props)
        if level is None:
            continue
        rings = _extract_rings(geom)
        if level == "p1":
            p1.extend(rings)
        else:
            p10.extend(rings)

    _p1_rings = p1
    _p10_rings = p10
    _loaded = True
    logger.info("Flood zones loaded: %d P=1%% rings, %d P=10%% rings", len(p1), len(p10))


def _ray_cast(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Standard ray-casting point-in-polygon test. Ring: list of [lon, lat] pairs."""
    n = len(ring)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def point_in_flood_zone(lat: float, lon: float) -> Literal["p1", "p10"] | None:
    """
    Return flood zone category for a point, or None if outside all zones.

    P=1%  → road cut / evacuation
    P=10% → at-risk warning
    """
    if not _loaded:
        logger.debug("Flood zones not yet loaded; skipping zone check")
        return None

    for ring in _p1_rings:
        if _ray_cast(lon, lat, ring):
            return "p1"
    for ring in _p10_rings:
        if _ray_cast(lon, lat, ring):
            return "p10"
    return None
