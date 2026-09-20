"""Manual smoke-test script: launches the weather MCP server as a subprocess over
stdio (exactly like a real MCP client would) and calls each of its tools once,
printing the results. Useful as a first sanity check before wiring the server
into Claude Desktop or another MCP client.

Run with:
    uv run python scripts/manual_client.py "Austin, TX"
    # or, with a plain venv active:
    python scripts/manual_client.py "Austin, TX"
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main(location: str) -> None:
    """Start the server subprocess, call each tool once, and print the results."""
    server_params = StdioServerParameters(command=sys.executable, args=["-m", "weather_mcp.server"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

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
