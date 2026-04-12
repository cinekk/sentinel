"""
Tests for the AI assistant: structured output schema, fallback, normalization,
and integration with mocked OpenRouter responses.

Run with: pytest tests/test_assistant.py -v
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient

from services.assistant import (
    _build_view_config_schema,
    _fallback_config,
    _validate_and_normalize,
    configure_view,
)
from services.layer_meta import get_all_schemas
from services.openrouter import _parse_json_defensive

pytestmark = pytest.mark.asyncio

ALL_LAYER_IDS = {s.layer_id for s in get_all_schemas()}


# ── JSON Schema structure ─────────────────────────────────────────────────────

class TestViewConfigSchema:
    def test_schema_has_enum_constraint(self):
        ids = ["hospitals", "schools", "fire_stations"]
        schema = _build_view_config_schema(ids)
        items = schema["schema"]["properties"]["layers_visible"]["items"]
        assert items["enum"] == ids

    def test_schema_enum_matches_real_layers(self):
        ids = [s.layer_id for s in get_all_schemas()]
        schema = _build_view_config_schema(ids)
        enum = schema["schema"]["properties"]["layers_visible"]["items"]["enum"]
        assert set(enum) == ALL_LAYER_IDS

    def test_schema_is_strict(self):
        schema = _build_view_config_schema(["a", "b"])
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False

    def test_schema_requires_all_fields(self):
        schema = _build_view_config_schema(["a"])
        required = set(schema["schema"]["required"])
        assert "layers_visible" in required
        assert "layers_hidden" in required
        assert "explanation" in required
        assert "popup_attributes" in required
        assert "critical_attribute_layer_id" in required
        assert "critical_attribute_key" in required

    def test_schema_visible_and_hidden_use_same_enum(self):
        ids = ["hospitals", "schools"]
        schema = _build_view_config_schema(ids)
        vis_enum = schema["schema"]["properties"]["layers_visible"]["items"]["enum"]
        hid_enum = schema["schema"]["properties"]["layers_hidden"]["items"]["enum"]
        assert vis_enum == hid_enum == ids


# ── Fallback ──────────────────────────────────────────────────────────────────

class TestFallback:
    def test_show_only_hospitals(self):
        cfg = _fallback_config("pokaż tylko szpitale")
        assert "hospitals" in cfg["layers_visible"]
        assert "schools" not in cfg["layers_visible"]
        assert "schools" in cfg["layers_hidden"]
        assert cfg["model"] == "fallback"

    def test_hide_schools(self):
        cfg = _fallback_config("ukryj szkoły")
        assert "schools" in cfg["layers_hidden"]
        assert "schools" not in cfg["layers_visible"]
        assert "hospitals" in cfg["layers_visible"]

    def test_fire_scenario(self):
        cfg = _fallback_config("pożar w Puławach")
        assert "hospitals" in cfg["layers_visible"]
        assert "fire_stations" in cfg["layers_visible"]
        assert "schools" in cfg["layers_hidden"]
        assert cfg["critical_attribute"] is not None
        assert cfg["critical_attribute"]["layer_id"] == "hospitals"

    def test_smog_scenario(self):
        cfg = _fallback_config("jaka jest jakość powietrza?")
        assert "air_quality" in cfg["layers_visible"]
        assert "hospitals" in cfg["layers_visible"]

    def test_flood_scenario(self):
        cfg = _fallback_config("powódź na Wiśle")
        assert "hospitals" in cfg["layers_visible"]
        assert "fire_stations" in cfg["layers_visible"]

    def test_generic_query_shows_all(self):
        cfg = _fallback_config("co słychać?")
        assert set(cfg["layers_visible"]) == ALL_LAYER_IDS
        assert cfg["layers_hidden"] == []

    def test_all_layers_accounted_for(self):
        """Every layer is either visible or hidden — never missing."""
        for query in ["pokaż tylko szpitale", "ukryj szkoły", "pożar", "co słychać?"]:
            cfg = _fallback_config(query)
            accounted = set(cfg["layers_visible"]) | set(cfg["layers_hidden"])
            assert accounted == ALL_LAYER_IDS, f"Missing layers for query: {query}"


# ── Validate & normalize ─────────────────────────────────────────────────────

class TestValidateNormalize:
    SCHEMAS = get_all_schemas()

    def test_valid_response_passes_through(self):
        raw = {
            "layers_visible": ["hospitals"],
            "layers_hidden": ["schools", "social"],
            "popup_attributes": {"hospitals": ["name", "beds_total_physical"]},
            "critical_attribute_layer_id": "hospitals",
            "critical_attribute_key": "beds_available_estimate",
            "critical_attribute_label": "Dostępne łóżka",
            "explanation": "Test",
            "_model": "qwen/qwen3-8b",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert result["layers_visible"] == ["hospitals"]
        assert "hospitals" not in result["layers_hidden"]
        assert result["critical_attribute"]["layer_id"] == "hospitals"
        assert result["model"] == "qwen/qwen3-8b"

    def test_missing_layers_go_to_hidden(self):
        raw = {
            "layers_visible": ["hospitals"],
            "layers_hidden": [],
            "popup_attributes": {},
            "explanation": "Only hospitals",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert "hospitals" in result["layers_visible"]
        for lid in ALL_LAYER_IDS - {"hospitals"}:
            assert lid in result["layers_hidden"], f"{lid} should be hidden"

    def test_invalid_layer_id_filtered_out(self):
        raw = {
            "layers_visible": ["hospitals", "nonexistent_layer"],
            "layers_hidden": ["schools"],
            "popup_attributes": {},
            "explanation": "Test",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert "nonexistent_layer" not in result["layers_visible"]
        assert "hospitals" in result["layers_visible"]

    def test_empty_visible_triggers_show_all(self):
        raw = {
            "layers_visible": [],
            "layers_hidden": [],
            "popup_attributes": {},
            "explanation": "Empty",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert set(result["layers_visible"]) == ALL_LAYER_IDS

    def test_critical_attribute_null_when_invalid_layer(self):
        raw = {
            "layers_visible": ["hospitals"],
            "layers_hidden": [],
            "popup_attributes": {},
            "critical_attribute_layer_id": "nonexistent",
            "critical_attribute_key": "beds",
            "explanation": "Test",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert result["critical_attribute"] is None

    def test_critical_attribute_null_when_key_missing(self):
        raw = {
            "layers_visible": ["hospitals"],
            "layers_hidden": [],
            "popup_attributes": {},
            "critical_attribute_layer_id": "hospitals",
            "critical_attribute_key": None,
            "explanation": "Test",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        assert result["critical_attribute"] is None

    def test_output_shape(self):
        """The returned dict must have exactly these keys."""
        raw = {
            "layers_visible": ["hospitals"],
            "layers_hidden": [],
            "popup_attributes": {},
            "explanation": "Test",
            "_model": "test",
        }
        result = _validate_and_normalize(raw, self.SCHEMAS)
        expected_keys = {
            "layers_visible", "layers_hidden", "popup_attributes",
            "critical_attribute", "explanation", "model",
        }
        assert set(result.keys()) == expected_keys


# ── Defensive JSON parsing ────────────────────────────────────────────────────

class TestParseJsonDefensive:
    def test_plain_json(self):
        assert _parse_json_defensive('{"a": 1}') == {"a": 1}

    def test_think_block_stripped(self):
        text = '<think>reasoning here</think>{"layers_visible": ["hospitals"]}'
        result = _parse_json_defensive(text)
        assert result["layers_visible"] == ["hospitals"]

    def test_markdown_fenced(self):
        text = '```json\n{"a": 1}\n```'
        result = _parse_json_defensive(text)
        assert result == {"a": 1}

    def test_text_before_json(self):
        text = 'Some preamble text {"key": "val"}'
        result = _parse_json_defensive(text)
        assert result == {"key": "val"}

    def test_no_think_prefix(self):
        text = '/no_think\n{"x": 42}'
        result = _parse_json_defensive(text)
        assert result == {"x": 42}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = _parse_json_defensive(text)
        assert result["outer"]["inner"] == [1, 2, 3]


# ── Integration: configure_view with mocked OpenRouter ────────────────────────

def _mock_openrouter_response(content: dict, model: str = "qwen/qwen3-8b-04-28") -> dict:
    """Build a fake OpenRouter API response."""
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": json.dumps(content),
                "reasoning": "I thought about it.",
            },
            "finish_reason": "stop",
        }],
        "model": model,
        "usage": {"total_tokens": 100},
    }


def _mock_openrouter_null_content(model: str = "qwen/qwen3-8b-04-28") -> dict:
    """Simulate the known Qwen3-8B bug: content=null."""
    return {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "reasoning": None,
            },
            "finish_reason": "stop",
        }],
        "model": model,
        "usage": {"total_tokens": 6},
    }


def _make_mock_client(api_response: dict):
    """Create a properly mocked httpx.AsyncClient for OpenRouter calls.

    httpx.Response.json() is synchronous, so we use a MagicMock (not AsyncMock)
    for the response, and an AsyncMock for the client's async context manager.
    """
    from unittest.mock import MagicMock

    mock_resp = MagicMock()
    mock_resp.json.return_value = api_response
    mock_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestConfigureViewIntegration:
    """Test configure_view() with mocked HTTP to OpenRouter."""

    async def test_correct_response_applied(self):
        llm_output = {
            "layers_visible": ["hospitals"],
            "layers_hidden": ["schools", "social", "fire_stations", "lublin_boundary",
                              "air_quality", "events", "simulation_threat", "transport_units"],
            "popup_attributes": {"hospitals": ["name", "beds_available_estimate"]},
            "critical_attribute_layer_id": None,
            "critical_attribute_key": None,
            "critical_attribute_label": None,
            "explanation": "Pokazuję tylko szpitale.",
        }
        mock_client = _make_mock_client(_mock_openrouter_response(llm_output))

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await configure_view("pokaż tylko szpitale")

        assert result["layers_visible"] == ["hospitals"]
        assert "schools" in result["layers_hidden"]
        assert result["explanation"] == "Pokazuję tylko szpitale."

    async def test_null_content_triggers_fallback(self):
        mock_client = _make_mock_client(_mock_openrouter_null_content())

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await configure_view("pokaż tylko szpitale")

        assert result["model"] == "fallback"
        assert "hospitals" in result["layers_visible"]

    async def test_network_error_triggers_fallback(self):
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await configure_view("pokaż szpitale")

        assert result["model"] == "fallback"

    async def test_schema_sent_to_openrouter(self):
        """Verify that the request body contains json_schema with layer enum."""
        llm_output = {
            "layers_visible": ["hospitals"],
            "layers_hidden": [],
            "popup_attributes": {},
            "critical_attribute_layer_id": None,
            "critical_attribute_key": None,
            "critical_attribute_label": None,
            "explanation": "Test",
        }
        mock_client = _make_mock_client(_mock_openrouter_response(llm_output))

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            await configure_view("test")

        call_kwargs = mock_client.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["response_format"]["type"] == "json_schema"
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        enum_values = schema["schema"]["properties"]["layers_visible"]["items"]["enum"]
        assert "hospitals" in enum_values
        assert "schools" in enum_values

    async def test_thinking_content_extracted(self):
        """Model returns content wrapped in <think> block — should still parse."""
        llm_output = {
            "layers_visible": ["hospitals", "fire_stations"],
            "layers_hidden": ["schools", "social", "lublin_boundary",
                              "air_quality", "events", "simulation_threat", "transport_units"],
            "popup_attributes": {},
            "critical_attribute_layer_id": "hospitals",
            "critical_attribute_key": "beds_available_estimate",
            "critical_attribute_label": "Dostępne łóżka",
            "explanation": "Widok kryzysowy pożar.",
        }
        wrapped = f"<think>Let me analyze this query...</think>{json.dumps(llm_output)}"
        api_response = {
            "choices": [{"message": {"role": "assistant", "content": wrapped}, "finish_reason": "stop"}],
            "model": "qwen/qwen3-8b-04-28",
            "usage": {"total_tokens": 200},
        }
        mock_client = _make_mock_client(api_response)

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await configure_view("pożar w fabryce")

        assert "hospitals" in result["layers_visible"]
        assert "fire_stations" in result["layers_visible"]
        assert result["critical_attribute"] is not None

    async def test_hide_query_returns_correct_hidden(self):
        """End-to-end: 'ukryj szkoły' should hide schools and show everything else."""
        all_ids = [s.layer_id for s in get_all_schemas()]
        llm_output = {
            "layers_visible": [lid for lid in all_ids if lid != "schools"],
            "layers_hidden": ["schools"],
            "popup_attributes": {},
            "critical_attribute_layer_id": None,
            "critical_attribute_key": None,
            "critical_attribute_label": None,
            "explanation": "Ukryto szkoły.",
        }
        mock_client = _make_mock_client(_mock_openrouter_response(llm_output))

        with patch("services.openrouter.httpx.AsyncClient", return_value=mock_client):
            result = await configure_view("ukryj szkoły")

        assert "schools" in result["layers_hidden"]
        assert "schools" not in result["layers_visible"]
        assert "hospitals" in result["layers_visible"]
