"""Unit tests for services/spatial.py — pure math, no I/O."""
import pytest
from services.spatial import check_intersections


def make_zone(semi_major_km=5.0, semi_minor_km=2.0, bearing_deg=0.0,
              center_lat=51.4158, center_lon=21.9698):
    return {
        "properties": {
            "center_lat": center_lat,
            "center_lon": center_lon,
            "semi_major_km": semi_major_km,
            "semi_minor_km": semi_minor_km,
            "bearing_deg": bearing_deg,
        }
    }


def make_resource(id, name, type, lat, lon):
    return {"id": id, "name": name, "type": type, "latitude": lat, "longitude": lon}


# ── Basic intersection ────────────────────────────────────────────────────────

def test_resource_inside_zone():
    zone = make_zone(semi_major_km=10.0, semi_minor_km=5.0)
    # Same coords as center — definitely inside
    r = make_resource(1, "Szpital", "hospital", 51.4158, 21.9698)
    alerts = check_intersections(zone, [r])
    assert len(alerts) == 1
    assert alerts[0]["level"] == "inside"
    assert alerts[0]["resource_id"] == 1


def test_resource_far_outside_zone():
    zone = make_zone(semi_major_km=1.0, semi_minor_km=0.5)
    # ~50 km away
    r = make_resource(1, "Daleki obiekt", "school", 52.2297, 21.0122)
    alerts = check_intersections(zone, [r])
    assert alerts == []


def test_resource_in_approaching_buffer():
    # Small zone but resource is just outside it, within 1.5x buffer
    zone = make_zone(semi_major_km=1.0, semi_minor_km=0.5)
    # ~0.012 deg ≈ 1.3 km north — outside 1km zone, inside 1.5km buffer
    r = make_resource(1, "Szkoła", "school", 51.4158 + 0.012, 21.9698)
    alerts = check_intersections(zone, [r])
    assert len(alerts) == 1
    assert alerts[0]["level"] == "approaching"


def test_empty_resources_returns_empty():
    zone = make_zone(semi_major_km=10.0, semi_minor_km=5.0)
    assert check_intersections(zone, []) == []


def test_multiple_resources_mixed():
    zone = make_zone(semi_major_km=5.0, semi_minor_km=2.0)
    resources = [
        make_resource(1, "Centrum",   "hospital", 51.4158, 21.9698),  # inside
        make_resource(2, "Daleko",    "school",   52.0,    22.5),     # outside
        make_resource(3, "Blisko DPS","social",   51.4158, 21.9698),  # inside
    ]
    alerts = check_intersections(zone, resources)
    assert len(alerts) == 2
    ids = {a["resource_id"] for a in alerts}
    assert ids == {1, 3}


# ── Alert content ─────────────────────────────────────────────────────────────

def test_alert_has_required_fields():
    zone = make_zone(semi_major_km=10.0, semi_minor_km=5.0)
    r = make_resource(42, "Szpital Puławy", "hospital", 51.4158, 21.9698)
    alerts = check_intersections(zone, [r])
    assert len(alerts) == 1
    a = alerts[0]
    assert a["resource_id"] == 42
    assert a["resource_name"] == "Szpital Puławy"
    assert a["resource_type"] == "hospital"
    assert a["level"] in ("inside", "approaching")
    assert isinstance(a["action"], str)
    assert len(a["action"]) > 0


def test_inside_beats_approaching():
    """Resource at center must be 'inside', not 'approaching'."""
    zone = make_zone(semi_major_km=5.0, semi_minor_km=2.0)
    r = make_resource(1, "Centrum", "school", 51.4158, 21.9698)
    alerts = check_intersections(zone, [r])
    assert alerts[0]["level"] == "inside"


# ── Action strings ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rtype,level,expected_fragment", [
    ("school",        "inside",      "ewakuuj"),
    ("school",        "approaching", "ewakuacj"),
    ("social",        "inside",      "DPS"),
    ("social",        "approaching", "DPS"),
    ("hospital",      "inside",      "Ewakuacja"),
    ("hospital",      "approaching", "oddział"),
    ("fire_station",  "inside",      "Wycofaj"),
    ("fire_station",  "approaching", "gotowości"),
])
def test_action_strings(rtype, level, expected_fragment):
    from services.spatial import _recommended_action
    action = _recommended_action(rtype, level)
    assert expected_fragment in action


def test_unknown_resource_type_returns_generic_action():
    from services.spatial import _recommended_action
    action = _recommended_action("submarine", "inside")
    assert "inside" in action or "Alert" in action
