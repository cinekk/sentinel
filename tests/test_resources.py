"""Tests for plugins/resources.py and routers/resources.py (calculator logic)."""
import math
import pytest

from plugins.resources import (
    HospitalsPlugin,
    SocialPlugin,
    SchoolsPlugin,
    FireStationsPlugin,
)
from routers.resources import _haversine_km


# ── Plugin structure ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("plugin_cls,expected_type,min_count", [
    (HospitalsPlugin,     "hospital",     50),
    (SocialPlugin,        "social",       250),
    (SchoolsPlugin,       "school",       1400),
    (FireStationsPlugin,  "fire_station", 10),
])
async def test_plugin_returns_feature_collection(plugin_cls, expected_type, min_count):
    plugin = plugin_cls()
    fc = await plugin.fetch()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) >= min_count


@pytest.mark.asyncio
@pytest.mark.parametrize("plugin_cls,expected_type", [
    (HospitalsPlugin,    "hospital"),
    (SocialPlugin,       "social"),
    (SchoolsPlugin,      "school"),
    (FireStationsPlugin, "fire_station"),
])
async def test_plugin_feature_has_required_props(plugin_cls, expected_type):
    plugin = plugin_cls()
    fc = await plugin.fetch()
    feature = fc["features"][0]

    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    coords = feature["geometry"]["coordinates"]
    assert len(coords) == 2

    lon, lat = coords
    assert -180 <= lon <= 180
    assert -90  <= lat <= 90

    props = feature["properties"]
    assert props.get("type") == expected_type
    assert isinstance(props.get("name"), str)
    assert isinstance(props.get("id"), str)


@pytest.mark.asyncio
async def test_all_plugins_have_distinct_layer_ids():
    ids = {
        HospitalsPlugin.layer_id,
        SocialPlugin.layer_id,
        SchoolsPlugin.layer_id,
        FireStationsPlugin.layer_id,
    }
    assert len(ids) == 4


@pytest.mark.asyncio
async def test_hospitals_coords_in_lublin_voivodeship():
    """All hospital coords should be roughly within the voivodeship bounding box."""
    plugin = HospitalsPlugin()
    fc = await plugin.fetch()
    for f in fc["features"]:
        lon, lat = f["geometry"]["coordinates"]
        assert 20.5 <= lon <= 25.0, f"lon {lon} out of range for {f['properties']['name']}"
        assert 50.2 <= lat <= 52.5, f"lat {lat} out of range for {f['properties']['name']}"


# ── Haversine calculator ──────────────────────────────────────────────────────

def test_haversine_zero_distance():
    assert _haversine_km(51.4158, 21.9698, 51.4158, 21.9698) == pytest.approx(0.0, abs=1e-9)


def test_haversine_known_distance():
    # Puławy → Lublin: ~45 km road, ~42 km straight line
    dist = _haversine_km(51.4158, 21.9698, 51.2490, 22.5665)
    assert 38 <= dist <= 48


def test_haversine_symmetry():
    a = _haversine_km(51.4158, 21.9698, 52.0, 23.0)
    b = _haversine_km(52.0, 23.0, 51.4158, 21.9698)
    assert a == pytest.approx(b, rel=1e-9)


def test_haversine_positive():
    assert _haversine_km(51.0, 22.0, 52.0, 23.0) > 0
