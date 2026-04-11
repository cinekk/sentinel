"""Unit tests for the plugin layer and registry."""
import pytest

from plugins import PluginRegistry
from plugins.mock_boundary import MockBoundaryPlugin, MockEventsPlugin, POWIATY


# ── Registry ──────────────────────────────────────────────────────────────────

def test_registry_register_and_get():
    reg = PluginRegistry()
    plugin = MockBoundaryPlugin()
    reg.register(plugin)
    assert reg.get("lublin_boundary") is plugin


def test_registry_get_unknown_returns_none():
    reg = PluginRegistry()
    assert reg.get("nonexistent") is None


def test_registry_all():
    reg = PluginRegistry()
    reg.register(MockBoundaryPlugin())
    reg.register(MockEventsPlugin())
    assert len(reg.all()) == 2


def test_registry_overwrite_same_id():
    reg = PluginRegistry()
    p1 = MockBoundaryPlugin()
    p2 = MockBoundaryPlugin()
    reg.register(p1)
    reg.register(p2)
    assert reg.get("lublin_boundary") is p2
    assert len(reg.all()) == 1



# ── MockBoundaryPlugin ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_boundary_plugin_fetch_returns_feature_collection():
    plugin = MockBoundaryPlugin()
    result = await plugin.fetch()
    assert result["type"] == "FeatureCollection"
    assert isinstance(result["features"], list)


async def test_boundary_plugin_last_updated_set_after_fetch():
    plugin = MockBoundaryPlugin()
    assert plugin.last_updated is None
    await plugin.fetch()
    assert plugin.last_updated is not None


async def test_boundary_plugin_feature_count():
    plugin = MockBoundaryPlugin()
    result = await plugin.fetch()
    # 1 voivodeship polygon + N powiat points
    assert len(result["features"]) == 1 + len(POWIATY)


async def test_boundary_plugin_polygon_is_closed():
    plugin = MockBoundaryPlugin()
    result = await plugin.fetch()
    polygon = next(f for f in result["features"] if f["properties"]["type"] == "voivodeship")
    coords = polygon["geometry"]["coordinates"][0]
    # A valid GeoJSON polygon must have first == last coordinate
    assert coords[0] == coords[-1]


# ── MockEventsPlugin ──────────────────────────────────────────────────────────

async def test_events_plugin_fetch_returns_empty_collection():
    plugin = MockEventsPlugin()
    result = await plugin.fetch()
    assert result["type"] == "FeatureCollection"
    assert result["features"] == []


async def test_events_plugin_metadata():
    plugin = MockEventsPlugin()
    assert plugin.layer_id == "events"
    assert plugin.data_type == "events"
