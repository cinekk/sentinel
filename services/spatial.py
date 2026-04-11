"""
Spatial intersection checks for threat zone alerts.

Uses pure math (no Shapely) — ellipse point-in-test is sufficient for hackathon.
Two-tier alerts: approaching (1.5x zone) and inside (actual zone).
"""
import math
from typing import Literal


AlertLevel = Literal["approaching", "inside"]

SPREAD_RATE_KM_PER_TICK = 0.05


def _point_in_ellipse(
    px: float, py: float,
    cx: float, cy: float,
    semi_major: float, semi_minor: float,
    angle_rad: float,
) -> bool:
    """Test if point (px, py) is inside an axis-aligned rotated ellipse."""
    cos_a = math.cos(-angle_rad)
    sin_a = math.sin(-angle_rad)
    dx = px - cx
    dy = py - cy
    rx = cos_a * dx - sin_a * dy
    ry = sin_a * dx + cos_a * dy
    return (rx / semi_major) ** 2 + (ry / semi_minor) ** 2 <= 1.0


def _deg_to_rad(deg: float) -> float:
    return deg * math.pi / 180.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two points."""
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def circle_polygon(lat: float, lon: float, radius_km: float, n: int = 64) -> list[list[float]]:
    """Return [lon, lat] polygon ring for a circle of given radius."""
    lat_r = math.radians(lat)
    dy = radius_km / 111.0
    dx = radius_km / (111.0 * math.cos(lat_r))
    coords = []
    for i in range(n + 1):
        angle = 2 * math.pi * i / n
        coords.append([lon + dx * math.sin(angle), lat + dy * math.cos(angle)])
    return coords


_DISPLAY_TYPES: dict[str, str] = {
    "hospital": "Szpital",
    "school": "Szkoła",
    "social": "DPS/Placówka",
}

_CRISIS_ACTION_MATRIX: dict[tuple[str, str], str] = {
    ("hospital", "evac"): "EWAKUACJA",
    ("hospital", "warn"): "GOTOWOŚĆ",
    ("social",   "evac"): "EWAKUACJA",
    ("social",   "warn"): "GOTOWOŚĆ",
    ("school",   "evac"): "ZAMKNIĘCIE",
    ("school",   "warn"): "OSTRZEŻENIE",
}


def _facility_alert_level(flat: float, flon: float, event) -> str | None:
    """Return 'inside', 'approaching', or None for a facility vs a crisis event."""
    if event.zone_shape == "ellipse" and event.semi_major_km:
        semi_major_deg = event.semi_major_km / 111.0
        semi_minor_deg = event.semi_minor_km / 111.0
        bearing_rad = _deg_to_rad(90.0 - (event.bearing_deg or 0.0))
        if _point_in_ellipse(flon, flat, event.lon, event.lat, semi_major_deg, semi_minor_deg, bearing_rad):
            return "inside"
        if _point_in_ellipse(flon, flat, event.lon, event.lat, semi_major_deg * 1.5, semi_minor_deg * 1.5, bearing_rad):
            return "approaching"
        return None
    else:
        d = haversine(flat, flon, event.lat, event.lon)
        if d <= event.evac_radius_km:
            return "inside"
        if d <= event.warn_radius_km:
            return "approaching"
        return None


def facilities_in_zones(crisis_events: list, facilities: list[dict]) -> list[dict]:
    """
    For each facility, find the active crisis event that puts it closest to a zone.

    crisis_events: CrisisEvent objects (circle or ellipse zone_shape)
    facilities: GeoJSON Feature dicts from resource plugins

    Returns list of affected-facility dicts sorted by distance_km.
    Deduplication: each facility appears once (nearest event wins).
    """
    results = []
    for facility in facilities:
        props = facility.get("properties", {})
        geom = facility.get("geometry", {})
        coords = geom.get("coordinates", [0.0, 0.0])
        flon, flat = coords[0], coords[1]
        ftype = props.get("type", "")

        if ftype not in ("hospital", "school", "social"):
            continue

        best_dist = float("inf")
        best_level: str | None = None
        best_event = None

        for event in crisis_events:
            level = _facility_alert_level(flat, flon, event)
            if level is None:
                continue
            d = haversine(flat, flon, event.lat, event.lon)
            if d < best_dist:
                best_dist = d
                best_level = level
                best_event = event

        if best_event is None:
            continue

        zone = "evac" if best_level == "inside" else "warn"
        fname = props.get("name", "")
        results.append({
            "facility_id": props.get("id", ""),
            "name": fname,
            "resource_name": fname,           # HUD compat
            "type": ftype,
            "display_type": _DISPLAY_TYPES.get(ftype, ftype),
            "lat": flat,
            "lon": flon,
            "distance_km": round(best_dist, 2),
            "zone": zone,
            "level": best_level,              # HUD compat
            "action": _CRISIS_ACTION_MATRIX.get((ftype, zone), "ALERT"),
            "crisis_id": best_event.id,
            "crisis_name": best_event.name,
        })

    results.sort(key=lambda x: x["distance_km"])
    return results


def _recommended_action(resource_type: str, level: AlertLevel) -> str:
    actions = {
        ("school",        "inside"):      "Zamknij i ewakuuj natychmiast",
        ("school",        "approaching"): "Przygotuj ewakuację szkoły",
        ("social",        "inside"):      "Ewakuacja priorytetowa — DPS",
        ("social",        "approaching"): "Alert dla personelu DPS, przygotuj ewakuację",
        ("hospital",      "inside"):      "Ewakuacja lub przygotuj przyjęcie rannych",
        ("hospital",      "approaching"): "Przygotuj oddział na zwiększony napływ",
        ("fire_station",  "inside"):      "Wycofaj jednostki — jednostka w strefie zagrożenia",
        ("fire_station",  "approaching"): "Stan gotowości — wkrótce w strefie",
    }
    return actions.get((resource_type, level), f"Alert {level} — zastosuj procedury")
