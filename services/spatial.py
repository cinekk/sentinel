"""
Spatial intersection checks for threat zone alerts.

Uses pure math (no Shapely) — ellipse point-in-test is sufficient for hackathon.
Two-tier alerts: approaching (1.5x zone) and inside (actual zone).
"""
import math
from typing import Literal


AlertLevel = Literal["approaching", "inside"]


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


def check_intersections(
    threat_zone: dict,
    resources: list[dict],
) -> list[dict]:
    """
    Given a threat_zone GeoJSON Feature and a list of resource dicts,
    return alerts for resources that are approaching or inside the zone.

    threat_zone properties must include:
        center_lat, center_lon, semi_major_km, semi_minor_km, bearing_deg

    Each resource dict must include:
        id, name, type, latitude, longitude

    Returns list of alert dicts:
        resource_id, resource_name, resource_type, level, action
    """
    props = threat_zone.get("properties", {})
    cx = props.get("center_lon", 0.0)
    cy = props.get("center_lat", 0.0)
    semi_major = props.get("semi_major_km", 1.0)
    semi_minor = props.get("semi_minor_km", 0.5)
    bearing_deg = props.get("bearing_deg", 0.0)

    # Convert km to approximate degrees (1 deg lat ≈ 111 km)
    semi_major_deg = semi_major / 111.0
    semi_minor_deg = semi_minor / 111.0

    # Wind bearing: meteorological (0=N, 90=E) → math angle from +x axis
    bearing_rad = _deg_to_rad(90.0 - bearing_deg)

    alerts: list[dict] = []

    for resource in resources:
        px = resource.get("longitude", 0.0)
        py = resource.get("latitude", 0.0)

        inside = _point_in_ellipse(px, py, cx, cy, semi_major_deg, semi_minor_deg, bearing_rad)
        approaching = not inside and _point_in_ellipse(
            px, py, cx, cy,
            semi_major_deg * 1.5, semi_minor_deg * 1.5,
            bearing_rad,
        )

        if inside or approaching:
            level: AlertLevel = "inside" if inside else "approaching"
            alerts.append({
                "resource_id": resource.get("id"),
                "resource_name": resource.get("name", "Unknown"),
                "resource_type": resource.get("type", "unknown"),
                "level": level,
                "action": _recommended_action(resource.get("type", ""), level),
            })

    return alerts


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
