"""Connects to an already-running weather MCP server (started separately with
scripts/start_server.py) over HTTP and calls its tools for one location.

Run this as many times as you like from another terminal; it just connects,
asks its questions, and disconnects — it never stops the server.

Run with:
    uv run python scripts/query_server.py "Austin, TX"
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

SERVER_URL = "http://127.0.0.1:8765/mcp"


async def main(location: str) -> None:
    async with streamable_http_client(SERVER_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            current = await session.call_tool("get_current_weather", {"location": location})
            print("\n--- Current weather ---")
            print(_first_text(current))

            forecast = await session.call_tool("get_weather_forecast", {"location": location, "days": 3})
            print("\n--- 3-day forecast ---")
            print(_first_text(forecast))

            advice = await session.call_tool(
                "recommend_best_time_for_activity",
                {"location": location, "activity": "hiking", "days": 3},
            )
            print("\n--- Hiking recommendation ---")
            print(_first_text(advice))


def _first_text(result) -> str:
    """Pretty-print the first text content block of a tool call result."""
    for block in result.content:
        if block.type == "text":
            try:
                return json.dumps(json.loads(block.text), indent=2)
            except json.JSONDecodeError:
                return block.text
    return "<no text content>"


if __name__ == "__main__":
    location_arg = sys.argv[1] if len(sys.argv) > 1 else "Austin, TX"
    asyncio.run(main(location_arg))
