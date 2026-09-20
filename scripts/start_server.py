"""Starts the weather MCP server as a standalone process, listening on HTTP.

Unlike `python -m weather_mcp.server` (stdio transport, which only works when
a client launches it as a subprocess), this keeps the server running in one
terminal so a separate client can connect to it from another terminal.

Run with:
    uv run python scripts/start_server.py
Then, in another terminal:
    uv run python scripts/query_server.py "Austin, TX"
"""
from __future__ import annotations

from weather_mcp.server import mcp

HOST = "127.0.0.1"
PORT = 8765

if __name__ == "__main__":
    print(f"Weather MCP server listening at http://{HOST}:{PORT}/mcp")
    mcp.run(transport="streamable-http", host=HOST, port=PORT)
