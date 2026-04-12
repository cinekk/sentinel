from datetime import datetime, timezone

import httpx

from plugins.base import BasePlugin

_WFS_URL = "https://wody.isok.gov.pl/wss/INSPIRE/INSPIRE_NZ_HY_MZPMRP_WFS"

# Lublin voivodeship bounding box (lon_min, lat_min, lon_max, lat_max)
_LUBLIN_BBOX = "21.3,50.2,24.2,52.2,CRS:84"

# Same bounds as floats for post-fetch centroid filtering
_LON_MIN, _LAT_MIN, _LON_MAX, _LAT_MAX = 21.3, 50.2, 24.2, 52.2


def _centroid_in_lublin(geometry: dict) -> bool:
    """Return True if the first ring's centroid falls inside the Lublin bbox."""
    gtype = geometry.get("type", "")
    coords = geometry.get("coordinates")
    if not coords:
        return False
    # Grab the exterior ring of the first polygon
    if gtype == "Polygon":
        ring = coords[0]
    elif gtype == "MultiPolygon":
        ring = coords[0][0]
    else:
        return False
    if not ring:
        return False
    lons = [pt[0] for pt in ring]
    lats = [pt[1] for pt in ring]
    cx = sum(lons) / len(lons)
    cy = sum(lats) / len(lats)
    return _LON_MIN <= cx <= _LON_MAX and _LAT_MIN <= cy <= _LAT_MAX

_cache: dict | None = None
_cache_time: datetime | None = None
_CACHE_TTL_SECONDS = 3600


class FloodZonesPlugin(BasePlugin):
    layer_id   = "flood_zones"
    layer_name = "Strefy zagrożenia powodziowego (ISOK)"
    data_type  = "flood_zone"

    async def fetch(self) -> dict:
        global _cache, _cache_time

        now = datetime.now(timezone.utc)
        if _cache and _cache_time and (now - _cache_time).seconds < _CACHE_TTL_SECONDS:
            return _cache

        params = {
            "SERVICE":      "WFS",
            "VERSION":      "2.0.0",
            "REQUEST":      "GetFeature",
            "TYPENAMES":    "nz-core:HazardArea",
            "outputFormat": "application/json",
            "BBOX":         _LUBLIN_BBOX,
            "count":        "2000",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(_WFS_URL, params=params)
        r.raise_for_status()

        fc = r.json()

        # Keep only features whose centroid is inside Lublin voivodship.
        # WFS BBOX returns everything that *intersects* the box, which can pull
        # in zones from neighbouring voivodships.
        kept = []
        for feat in fc.get("features", []):
            geom = feat.get("geometry") or {}
            if not _centroid_in_lublin(geom):
                continue
            props = feat.get("properties") or {}
            feat["properties"] = {
                "name":        props.get("inspireId") or props.get("localId") or "Strefa zagrożenia",
                "type":        "flood_zone",
                "hazard_type": props.get("typeOfHazard", {}).get("hazardCategory", {}).get("href", "")
                               .split("/")[-1] if isinstance(props.get("typeOfHazard"), dict) else str(props.get("typeOfHazard", "")),
                "source":      "ISOK / RZGW",
            }
            kept.append(feat)
        fc["features"] = kept

        self._last_updated = now
        _cache = fc
        _cache_time = now
        return fc
