"""Unit tests for services/spatial.py — pure math, no I/O."""
import time
import pytest
from services.spatial import facilities_in_zones, _recommended_action
from models import CrisisEvent


def make_event(
    semi_major_km=5.0, semi_minor_km=2.0, bearing_deg=0.0,
    lat=51.4158, lon=21.9698,
    zone_shape="ellipse", evac_radius_km=5.0, warn_radius_km=12.0,
):
    return CrisisEvent(
        id="test",
        type="fire",
        lat=lat,
        lon=lon,
        name="Test Fire",
        evac_radius_km=evac_radius_km,
        warn_radius_km=warn_radius_km,
        zone_shape=zone_shape,
        semi_major_km=semi_major_km,
        semi_minor_km=semi_minor_km,
        bearing_deg=bearing_deg,
        status="active",
        source="test",
        created_at=time.time(),
    )


def make_facility(id, name, ftype, lat, lon):
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "properties": {"id": id, "name": name, "type": ftype},
    }


# ── Ellipse intersection ──────────────────────────────────────────────────────

def test_facility_inside_ellipse():
    event = make_event(semi_major_km=10.0, semi_minor_km=5.0)
    # Same coords as center — definitely inside
    f = make_facility(1, "Szpital", "hospital", 51.4158, 21.9698)
    results = facilities_in_zones([event], [f])
    assert len(results) == 1
    assert results[0]["level"] == "inside"


def test_facility_far_outside_ellipse():
    event = make_event(semi_major_km=1.0, semi_minor_km=0.5)
    # ~50 km away
    f = make_facility(1, "Daleki obiekt", "school", 52.2297, 21.0122)
    results = facilities_in_zones([event], [f])
    assert results == []


def test_facility_in_approaching_buffer():
    # Small ellipse; facility is just outside 1×, within 1.5×
    event = make_event(semi_major_km=1.0, semi_minor_km=0.5)
    # ~0.012 deg ≈ 1.3 km north — outside 1km zone, inside 1.5km buffer
    f = make_facility(1, "Szkoła", "school", 51.4158 + 0.012, 21.9698)
    results = facilities_in_zones([event], [f])
    assert len(results) == 1
    assert results[0]["level"] == "approaching"


def test_empty_facilities_returns_empty():
    event = make_event(semi_major_km=10.0, semi_minor_km=5.0)
    assert facilities_in_zones([event], []) == []


def test_multiple_facilities_mixed():
    event = make_event(semi_major_km=5.0, semi_minor_km=2.0)
    facilities = [
        make_facility(1, "Centrum",    "hospital", 51.4158, 21.9698),  # inside
        make_facility(2, "Daleko",     "school",   52.0,    22.5),     # outside
        make_facility(3, "Blisko DPS", "social",   51.4158, 21.9698),  # inside
    ]
    results = facilities_in_zones([event], facilities)
    assert len(results) == 2
    ids = {r["facility_id"] for r in results}
    assert ids == {1, 3}


# ── Circle intersection ───────────────────────────────────────────────────────

def test_circle_inside_evac():
    event = make_event(zone_shape="circle", evac_radius_km=10.0, warn_radius_km=20.0,
                       semi_major_km=None, semi_minor_km=None)
    f = make_facility(1, "Szpital", "hospital", 51.4158, 21.9698)
    results = facilities_in_zones([event], [f])
    assert len(results) == 1
    assert results[0]["level"] == "inside"
    assert results[0]["zone"] == "evac"


def test_circle_warn_zone():
    event = make_event(zone_shape="circle", evac_radius_km=1.0, warn_radius_km=20.0,
                       semi_major_km=None, semi_minor_km=None)
    # At center = inside evac; move ~5 km north to be in warn only
    f = make_facility(1, "Szkoła", "school", 51.4158 + 0.045, 21.9698)  # ~5km
    results = facilities_in_zones([event], [f])
    assert len(results) == 1
    assert results[0]["level"] == "approaching"
    assert results[0]["zone"] == "warn"


# ── Result fields ─────────────────────────────────────────────────────────────

def test_result_has_hud_fields():
    event = make_event(semi_major_km=10.0, semi_minor_km=5.0)
    f = make_facility(42, "Szpital Puławy", "hospital", 51.4158, 21.9698)
    results = facilities_in_zones([event], [f])
    assert len(results) == 1
    r = results[0]
    assert r["level"] in ("inside", "approaching")
    assert r["resource_name"] == "Szpital Puławy"
    assert r["name"] == "Szpital Puławy"
    assert r["zone"] in ("evac", "warn")
    assert isinstance(r["action"], str)


def test_inside_level_maps_to_evac_zone():
    event = make_event(semi_major_km=5.0, semi_minor_km=2.0)
    f = make_facility(1, "Centrum", "school", 51.4158, 21.9698)
    results = facilities_in_zones([event], [f])
    assert results[0]["level"] == "inside"
    assert results[0]["zone"] == "evac"


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
    action = _recommended_action(rtype, level)
    assert expected_fragment in action


def test_unknown_resource_type_returns_generic_action():
    action = _recommended_action("submarine", "inside")
    assert "inside" in action or "Alert" in action
