"""End-to-end tests that launch the real MCP server as a subprocess over stdio -
exactly like Claude Desktop or another MCP client would - and call its tools.

These hit the live, free Open-Meteo API, so they are marked `integration` and
are skipped by a plain `pytest` run (see `addopts` in pyproject.toml). Run them
explicitly, with network access, via:

    pytest -m integration
"""
import json
import sys
from contextlib import asynccontextmanager

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _session():
    """Start the server as a subprocess and yield an initialized MCP client session.

    A plain async context manager rather than a pytest fixture: opened and
    closed directly inside each test's own task, since the underlying anyio
    stdio transport uses a task group that must enter and exit in the same
    task, which pytest-asyncio's fixture teardown does not guarantee.
    """
    params = StdioServerParameters(command=sys.executable, args=["-m", "weather_mcp.server"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client_session:
            await client_session.initialize()
            yield client_session


def _json_payload(result) -> dict:
    """Extract and parse the JSON text content from a tool call result."""
    for block in result.content:
        if block.type == "text":
            return json.loads(block.text)
    raise AssertionError("tool result had no text content")


async def test_lists_expected_tools():
    async with _session() as session:
        tools = await session.list_tools()
        names = {tool.name for tool in tools.tools}
        assert {"get_current_weather", "get_weather_forecast", "recommend_best_time_for_activity"} <= names


async def test_get_current_weather_returns_temperature():
    async with _session() as session:
        result = await session.call_tool("get_current_weather", {"location": "Austin, TX"})
        payload = _json_payload(result)

        assert "temperature" in payload
        assert payload["units"] == "metric"


async def test_forecast_returns_the_requested_number_of_days():
    async with _session() as session:
        result = await session.call_tool("get_weather_forecast", {"location": "Austin, TX", "days": 3})
        payload = _json_payload(result)

        assert len(payload["days"]) == 3


async def test_unknown_location_returns_an_error_payload():
    async with _session() as session:
        result = await session.call_tool("get_current_weather", {"location": "Notarealplace1234"})
        payload = _json_payload(result)

        assert "error" in payload


async def test_activity_recommendation_is_ranked_best_first():
    async with _session() as session:
        result = await session.call_tool(
            "recommend_best_time_for_activity",
            {"location": "Austin, TX", "activity": "hiking", "days": 3},
        )
        payload = _json_payload(result)

        scores = [day["score"] for day in payload["recommendations"]]
        assert scores == sorted(scores, reverse=True)


async def test_unsupported_activity_returns_an_error_payload():
    async with _session() as session:
        result = await session.call_tool(
            "recommend_best_time_for_activity",
            {"location": "Austin, TX", "activity": "skydiving", "days": 3},
        )
        payload = _json_payload(result)

        assert "error" in payload
