"""Tests for GIOŚ air quality plugin and API endpoints."""
from __future__ import annotations

import json as json_mod
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

import plugins.gios as gios_mod
from plugins.gios import (
    GIOSPlugin,
    _build_feature,
    _geojson_to_briefing,
    _INDEX_TO_PM25,
    _INDEX_TO_PM10,
    _INDEX_TO_STATUS,
    _clear_cache,
    _mock_geojson,
)

pytestmark = pytest.mark.asyncio

# ── Canned API responses ──────────────────────────────────────────────────────

MOCK_STATIONS_RESPONSE = {
    "Lista stacji pomiarowych": [
        {
            "Identyfikator stacji": 266,
            "Kod stacji": "LbLubObywate",
            "Nazwa stacji": "Lublin, ul. Obywatelska",
            "WGS84 φ N": "51.259370",
            "WGS84 λ E": "22.569116",
            "Województwo": "LUBELSKIE",
            "Powiat": "Lublin",
        },
        {
            "Identyfikator stacji": 236,
            "Kod stacji": "LbBialPodlOr",
            "Nazwa stacji": "Biała Podlaska, ul. Orzechowa",
            "WGS84 φ N": "52.029",
            "WGS84 λ E": "23.149",
            "Województwo": "LUBELSKIE",
            "Powiat": "Biała Podlaska",
        },
        {
            "Identyfikator stacji": 999,
            "Kod stacji": "MzWarszCentru",
            "Nazwa stacji": "Warszawa, Centrum",
            "WGS84 φ N": "52.231",
            "WGS84 λ E": "21.006",
            "Województwo": "MAZOWIECKIE",
            "Powiat": "Warszawa",
        },
    ]
}

MOCK_INDEX_266 = {
    "AqIndex": {
        "Identyfikator stacji pomiarowej": 266,
        "Data wykonania obliczeń indeksu": "2026-04-12 00:25:09",
        "Wartość indeksu": 1,
        "Nazwa kategorii indeksu": "Dobry",
        "Wartość indeksu dla wskaźnika PM2.5": 1,
        "Nazwa kategorii indeksu dla wskażnika PM2.5": "Dobry",
        "Data danych źródłowych ... PM2.5": "2026-04-12 00:00:00",
        "Wartość indeksu dla wskaźnika PM10": 1,
        "Nazwa kategorii indeksu dla wskażnika PM10": "Dobry",
        "Wartość indeksu dla wskaźnika SO2": 0,
        "Nazwa kategorii indeksu dla wskażnika SO2": "Bardzo dobry",
        "Wartość indeksu dla wskaźnika NO2": 1,
        "Nazwa kategorii indeksu dla wskażnika NO2": "Dobry",
        "Wartość indeksu dla wskaźnika O3": 0,
        "Nazwa kategorii indeksu dla wskażnika O3": "Bardzo dobry",
        "Status indeksu ogólnego dla stacji pomiarowej": True,
        "Kod zanieczyszczenia krytycznego": "PYL",
    }
}

MOCK_INDEX_236 = {
    "AqIndex": {
        "Identyfikator stacji pomiarowej": 236,
        "Data wykonania obliczeń indeksu": "2026-04-12 00:20:00",
        "Wartość indeksu": 0,
        "Nazwa kategorii indeksu": "Bardzo dobry",
        "Wartość indeksu dla wskaźnika PM2.5": 0,
        "Nazwa kategorii indeksu dla wskażnika PM2.5": "Bardzo dobry",
        "Data danych źródłowych ... PM2.5": "2026-04-12 00:00:00",
        "Wartość indeksu dla wskaźnika PM10": 0,
        "Nazwa kategorii indeksu dla wskażnika PM10": "Bardzo dobry",
        "Wartość indeksu dla wskaźnika SO2": None,
        "Nazwa kategorii indeksu dla wskażnika SO2": None,
        "Wartość indeksu dla wskaźnika NO2": None,
        "Nazwa kategorii indeksu dla wskażnika NO2": None,
        "Wartość indeksu dla wskaźnika O3": None,
        "Nazwa kategorii indeksu dla wskażnika O3": None,
        "Status indeksu ogólnego dla stacji pomiarowej": True,
        "Kod zanieczyszczenia krytycznego": "",
    }
}

MOCK_INDEX_NULL = {
    "AqIndex": {
        "Identyfikator stacji pomiarowej": 999,
        "Wartość indeksu": None,
        "Status indeksu ogólnego dla stacji pomiarowej": False,
    }
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear GIOŚ module caches before every test."""
    _clear_cache()
    yield
    _clear_cache()


def _make_response(json_data: dict, status_code: int = 200, url: str = "https://api.gios.gov.pl/test") -> httpx.Response:
    """Build a proper httpx.Response that supports raise_for_status."""
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code=status_code,
        content=json_mod.dumps(json_data).encode(),
        headers={"content-type": "application/json"},
        request=request,
    )


def _mock_client_get(station_resp=MOCK_STATIONS_RESPONSE, index_map=None):
    """Create a side_effect function for httpx.AsyncClient.get that routes by URL."""
    if index_map is None:
        index_map = {266: MOCK_INDEX_266, 236: MOCK_INDEX_236}

    async def _get(url, **kwargs):
        url_str = str(url)
        if "station/findAll" in url_str:
            return _make_response(station_resp, url=url_str)
        for sid, data in index_map.items():
            if f"getIndex/{sid}" in url_str:
                return _make_response(data, url=url_str)
        return _make_response({"error": "not found"}, 404, url=url_str)

    return _get


def _patch_httpx(side_effect):
    """Patch httpx.AsyncClient as an async context manager with given get side_effect."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=side_effect)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("plugins.gios.httpx.AsyncClient", return_value=mock_client), mock_client


# ── Unit tests: plugin metadata ───────────────────────────────────────────────

def test_gios_plugin_metadata():
    plugin = GIOSPlugin()
    assert plugin.layer_id == "air_quality"
    assert plugin.data_type == "air_quality"
    assert plugin.layer_name == "Jakość powietrza (GIOŚ)"


# ── Unit tests: fetch returns GeoJSON ─────────────────────────────────────────

async def test_gios_fetch_returns_feature_collection():
    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        result = await plugin.fetch()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 2


async def test_gios_feature_properties():
    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        result = await plugin.fetch()

    feat = [f for f in result["features"] if f["properties"]["station_id"] == 266][0]
    props = feat["properties"]
    assert props["name"] == "GIOŚ Lublin, ul. Obywatelska"
    assert props["source"] == "gios_live"
    assert props["overall_index"] == 1
    assert props["overall_category"] == "Dobry"
    assert props["pm25_index"] == 1
    assert props["pm10_index"] == 1
    assert props["so2_index"] == 0
    assert props["critical_pollutant"] == "PYL"
    assert props["measurement_time"] == "2026-04-12 00:00:00"


async def test_gios_coordinates_parsed_from_strings():
    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        result = await plugin.fetch()

    feat = [f for f in result["features"] if f["properties"]["station_id"] == 266][0]
    lon, lat = feat["geometry"]["coordinates"]
    assert abs(lat - 51.259370) < 0.001
    assert abs(lon - 22.569116) < 0.001


# ── Unit tests: null index filtering ──────────────────────────────────────────

async def test_gios_skips_station_with_null_index():
    stations_with_null = {
        "Lista stacji pomiarowych": [
            MOCK_STATIONS_RESPONSE["Lista stacji pomiarowych"][0],
            {
                "Identyfikator stacji": 777,
                "Nazwa stacji": "Stacja testowa",
                "WGS84 φ N": "51.0",
                "WGS84 λ E": "22.0",
                "Województwo": "LUBELSKIE",
                "Powiat": "Test",
            },
        ]
    }
    index_map = {266: MOCK_INDEX_266, 777: MOCK_INDEX_NULL}

    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get(stations_with_null, index_map))
    with patcher:
        result = await plugin.fetch()

    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["station_id"] == 266


# ── Unit tests: filters non-Lubelskie stations ───────────────────────────────

async def test_gios_filters_non_lubelskie():
    all_index = {266: MOCK_INDEX_266, 236: MOCK_INDEX_236, 999: MOCK_INDEX_266}

    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get(MOCK_STATIONS_RESPONSE, all_index))
    with patcher:
        result = await plugin.fetch()

    station_ids = {f["properties"]["station_id"] for f in result["features"]}
    assert 999 not in station_ids
    assert 266 in station_ids
    assert 236 in station_ids


# ── Unit tests: caching ───────────────────────────────────────────────────────

async def test_gios_station_cache():
    """Second fetch reuses cached station list."""
    call_count = {"stations": 0}

    async def counting_get(url, **kwargs):
        url_str = str(url)
        if "station/findAll" in url_str:
            call_count["stations"] += 1
            return _make_response(MOCK_STATIONS_RESPONSE, url=url_str)
        for sid, data in {266: MOCK_INDEX_266, 236: MOCK_INDEX_236}.items():
            if f"getIndex/{sid}" in url_str:
                return _make_response(data, url=url_str)
        return _make_response({}, 404, url=url_str)

    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(counting_get)
    with patcher:
        await plugin.fetch()
        # Expire index cache to force a second fetch round, but station cache stays
        gios_mod._index_cache = None
        gios_mod._index_cache_time = None
        await plugin.fetch()

    assert call_count["stations"] == 1


async def test_gios_index_cache():
    """Second fetch within TTL returns cached GeoJSON."""
    plugin = GIOSPlugin()
    patcher, mock_client = _patch_httpx(_mock_client_get())
    with patcher:
        r1 = await plugin.fetch()
        r2 = await plugin.fetch()

    assert r1 is r2


# ── Unit tests: fallback ──────────────────────────────────────────────────────

async def test_gios_fallback_to_cache_on_api_error():
    plugin = GIOSPlugin()

    # First call succeeds (populates cache)
    patcher1, _ = _patch_httpx(_mock_client_get())
    with patcher1:
        first = await plugin.fetch()
    assert first["features"][0]["properties"]["source"] == "gios_live"

    # Expire index cache, make second call fail
    gios_mod._index_cache_time = None

    async def fail_get(url, **kwargs):
        raise httpx.ConnectError("Network down")

    patcher2, _ = _patch_httpx(fail_get)
    with patcher2:
        second = await plugin.fetch()

    assert len(second["features"]) > 0
    assert second["features"][0]["properties"]["source"] == "gios_cached"


async def test_gios_fallback_to_mock_when_no_cache():
    plugin = GIOSPlugin()

    async def fail_get(url, **kwargs):
        raise httpx.ConnectError("Network down")

    patcher, _ = _patch_httpx(fail_get)
    with patcher:
        result = await plugin.fetch()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 6
    assert result["features"][0]["properties"]["source"] == "mock"


# ── Unit tests: briefing data format ──────────────────────────────────────────

async def test_gios_briefing_data_format():
    plugin = GIOSPlugin()
    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        data = await plugin.get_briefing_data()

    assert len(data) == 2
    for item in data:
        assert "name" in item
        assert "lat" in item
        assert "lon" in item
        assert "pm25" in item
        assert "pm10" in item
        assert "status" in item
        assert isinstance(item["pm25"], (int, float))
        assert isinstance(item["pm10"], (int, float))
        assert isinstance(item["status"], str)


# ── Unit tests: index mapping ─────────────────────────────────────────────────

@pytest.mark.parametrize("index,expected_pm25,expected_pm10,expected_status", [
    (0, 5, 15, "bardzo dobra"),
    (1, 15, 35, "dobra"),
    (2, 30, 55, "umiarkowana"),
    (3, 55, 80, "dostateczna"),
    (4, 80, 120, "zła"),
    (5, 120, 150, "bardzo zła"),
])
def test_gios_index_to_value_mapping(index, expected_pm25, expected_pm10, expected_status):
    assert _INDEX_TO_PM25[index] == expected_pm25
    assert _INDEX_TO_PM10[index] == expected_pm10
    assert _INDEX_TO_STATUS[index] == expected_status


# ── Unit tests: helper functions ──────────────────────────────────────────────

def test_build_feature_geometry():
    station = {"id": 266, "name": "Test", "lat": 51.259, "lon": 22.569}
    idx = {
        "Wartość indeksu": 1,
        "Nazwa kategorii indeksu": "Dobry",
        "Status indeksu ogólnego dla stacji pomiarowej": True,
    }
    feat = _build_feature(station, idx)
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [22.569, 51.259]


def test_geojson_to_briefing_maps_correctly():
    fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [22.569, 51.259]},
            "properties": {
                "name": "GIOŚ Test",
                "overall_index": 2,
                "source": "gios_live",
            },
        }],
    }
    result = _geojson_to_briefing(fc)
    assert len(result) == 1
    assert result[0]["name"] == "GIOŚ Test"
    assert result[0]["lat"] == 51.259
    assert result[0]["lon"] == 22.569
    assert result[0]["pm25"] == 30
    assert result[0]["pm10"] == 55
    assert result[0]["status"] == "umiarkowana"


def test_mock_geojson_returns_valid_structure():
    fc = _mock_geojson()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 6
    for feat in fc["features"]:
        assert feat["type"] == "Feature"
        assert feat["geometry"]["type"] == "Point"
        assert feat["properties"]["source"] == "mock"


# ── API integration tests ─────────────────────────────────────────────────────

async def test_air_quality_appears_in_layers_list(client: AsyncClient):
    from plugins import registry
    registry.register(GIOSPlugin())

    r = await client.get("/api/layers")
    assert r.status_code == 200
    ids = {layer["layer_id"] for layer in r.json()}
    assert "air_quality" in ids


async def test_air_quality_geojson_endpoint(client: AsyncClient):
    from plugins import registry
    registry.register(GIOSPlugin())

    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        r = await client.get("/api/layers/air_quality/geojson")

    assert r.status_code == 200
    body = r.json()
    assert body["type"] == "FeatureCollection"
    assert len(body["features"]) == 2


async def test_air_quality_v1_endpoint(client: AsyncClient):
    from plugins import registry
    registry.register(GIOSPlugin())

    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        r = await client.get("/api/v1/layers/air-quality")

    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    for item in data:
        assert "name" in item
        assert "pm25" in item
        assert "pm10" in item
        assert "status" in item
        assert "lat" in item
        assert "lon" in item


async def test_air_quality_v1_source_field(client: AsyncClient):
    from plugins import registry
    registry.register(GIOSPlugin())

    patcher, _ = _patch_httpx(_mock_client_get())
    with patcher:
        r = await client.get("/api/v1/layers/air-quality")

    data = r.json()
    for item in data:
        assert "source" in item
        assert item["source"] in ("gios_live", "gios_cached", "mock")
