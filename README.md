# Weather MCP Server

An [MCP](https://modelcontextprotocol.io) server, written in Python, that gives an LLM assistant two kinds of ability:

1. **Plain weather lookups** — current conditions and multi-day forecasts for any place name.
2. **Activity planning advice** — "when should I go for a run/hike/beach day this week?", answered by scoring the forecast (temperature, rain, wind, UV, air quality) against activity-specific rubrics and returning a ranked, explained recommendation with a suggested time window. This is the part a weather *website* doesn't do: it requires combining several data sources, applying domain judgment, and producing a decision — exactly the kind of synthesis worth exposing as a tool for an LLM to call, rather than a page for a human to read.

No API key or account is required. Weather and geocoding data come from [Open-Meteo](https://open-meteo.com), which is free for non-commercial use without registration.

## Quick start

Start the server (used when wiring it into an MCP client like Claude Desktop; it just waits on stdio):

```bash
uv run python -m weather_mcp.server
```

Call it (spins up its own server subprocess, calls all 3 tools, prints results — no separate start step needed):

```bash
uv run python scripts/manual_client.py "Austin, TX"
```

## Architecture

```
                         ┌───────────────────────┐
 MCP client (Claude,     │   weather_mcp.server   │   FastMCP tools/resource/prompt
 the inspector, your     │  (thin wiring only)    │   - get_current_weather
 own script) ───stdio───▶│                        │   - get_weather_forecast
                         └───────────┬────────────┘   - recommend_best_time_for_activity
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                  ▼
         ┌─────────────────────┐           ┌───────────────────────────┐
         │  WeatherService      │           │  ActivityAdvisor           │
         │  (current + forecast │           │  (scoring rubrics, ranked  │
         │   shaping + caching) │           │   day/time recommendation) │
         └──────────┬───────────┘           └──────────┬─────────────────┘
                     │                                  │
                     └────────────────┬─────────────────┘
                                       ▼
                     ┌─────────────────────────────────┐
                     │  GeocodingClient / WeatherClient │  async httpx wrappers
                     └────────────────┬──────────────────┘
                                       ▼
                              Open-Meteo public APIs
```

**Layering rationale:**

- **`server.py`** only declares MCP tools/resource/prompt and delegates to services. This keeps the MCP-specific glue (decorators, error shaping) separate from logic you'd want to unit test without an MCP client.
- **`services/`** holds the two use cases (`WeatherService`, `ActivityAdvisor`) as plain classes with documented methods — testable with fake clients, no network or MCP involved.
- **`clients/`** holds thin async HTTP wrappers (`GeocodingClient`, `WeatherClient`) around Open-Meteo's REST APIs — the only place that knows about HTTP or JSON shapes.
- **`cache.py`** is a small in-memory TTL cache in front of geocoding lookups, since a place name's coordinates don't change between calls in a session.
- **`models.py`** defines frozen dataclasses passed between layers instead of raw dicts, so typos in field names fail fast.

Project layout:

```
weather-mcp-server/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── src/weather_mcp/
│   ├── server.py               # MCP tools/resource/prompt (entrypoint)
│   ├── config.py                # Settings.from_env()
│   ├── cache.py                 # TTLCache
│   ├── models.py                # shared dataclasses
│   ├── clients/
│   │   ├── geocoding_client.py  # GeocodingClient
│   │   └── weather_client.py    # WeatherClient
│   └── services/
│       ├── weather_service.py   # WeatherService
│       └── activity_advisor.py  # ActivityAdvisor (the "interesting" feature)
├── scripts/manual_client.py     # runnable script that calls the server over stdio
└── tests/                       # pytest unit + integration tests
```

## The MCP tools

| Tool | Purpose |
|---|---|
| `get_current_weather(location, units="metric")` | Current temperature, feels-like, humidity, wind, precipitation, conditions. |
| `get_weather_forecast(location, days=5, units="metric")` | Daily min/max temp, rain chance, UV, wind, conditions for 1–16 days. |
| `recommend_best_time_for_activity(location, activity, days=5)` | Ranked days (0–100 score, reasons, best 3-hour window) for `running`, `cycling`, `hiking`, `beach`, `outdoor_event`, or `picnic`. |

There's also one MCP **resource** (`weather://capabilities`, a static description for client discovery UIs) and one MCP **prompt** (`plan_outdoor_day`), included mainly so this project demonstrates all three MCP primitives, since it's a first MCP server.

## Prerequisites, and what to do if you can't install Python (no admin rights)

This machine already has a usable Python: `python3` (3.9.6) is on `PATH` via Apple's Command Line Tools, and both `pip` and the `venv` module work — **no admin rights are needed for anything below**, including installing packages into a virtual environment (a venv lives entirely inside your home directory).

There's one wrinkle: the MCP SDK requires **Python 3.10+**, and the system Python here is 3.9.6. You do not need admin rights to get a newer Python — recommended approach:

### Recommended: `uv` (no admin, installs entirely in your home directory)

[`uv`](https://docs.astral.sh/uv/) is a single self-contained binary that installs to `~/.local/bin` (no `sudo`), and can download standalone Python builds into `~/.local/share/uv` — again, no admin rights, nothing touches `/Library` or `/usr`. It's also what Anthropic's own MCP quickstart recommends.

```bash
# Install uv itself (no sudo)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your shell, or: source ~/.local/bin/env

# From the project directory:
cd ~/weather-mcp-server
uv python install 3.12   # downloads Python 3.12 into your home dir, no admin needed
uv sync --extra dev       # creates .venv/ and installs all dependencies
```

That's it — `uv sync` reads `pyproject.toml`, creates `.venv/`, and installs both runtime and dev (`pytest`, etc.) dependencies.

### Alternative: plain `venv` (works if you obtain a Python ≥3.10 some other way)

If you can get a newer interpreter onto the machine some other way (e.g. `pyenv`, which also installs entirely under `~/.pyenv` and compiles Python from source with no admin rights — slower than `uv`, but another no-admin option), the standard flow works too:

```bash
cd ~/weather-mcp-server
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### What *not* to do

Downloading the official python.org `.pkg` installer typically writes to `/Library/Frameworks` and prompts for an admin password — that's the one path that won't work without admin rights. `uv` and `pyenv` avoid this because they install entirely under your home directory.

## Running locally

With `uv` (recommended):

```bash
uv run python -m weather_mcp.server
```

With a plain venv (after `source .venv/bin/activate`):

```bash
python -m weather_mcp.server
```

The server speaks JSON-RPC over stdio and will sit there waiting for a client — that's expected; it's not a web server and has no port to open in a browser. To actually see it do something, use the manual test script or connect it to an MCP client:

**Try it with the manual script** (see [Testing](#testing) below) — the fastest way to see real output.

**Connect it to Claude Desktop** by adding to its MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "weather": {
      "command": "uv",
      "args": ["--directory", "/Users/Rakesh.Kandekar/weather-mcp-server", "run", "python", "-m", "weather_mcp.server"]
    }
  }
}
```

(Swap the `command`/`args` for `.venv/bin/python -m weather_mcp.server` if you used the plain-venv route.) Restart Claude Desktop afterward.

**Inspect it interactively** with the official [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
uv run mcp dev src/weather_mcp/server.py
```

### Configuration

All optional — sane defaults point at the public Open-Meteo APIs:

| Env var | Default | Purpose |
|---|---|---|
| `WEATHER_MCP_GEOCODING_URL` | Open-Meteo geocoding endpoint | Override for testing/self-hosting |
| `WEATHER_MCP_FORECAST_URL` | Open-Meteo forecast endpoint | Override for testing/self-hosting |
| `WEATHER_MCP_AIR_QUALITY_URL` | Open-Meteo air-quality endpoint | Override for testing/self-hosting |
| `WEATHER_MCP_HTTP_TIMEOUT_SECONDS` | `10` | HTTP request timeout |
| `WEATHER_MCP_CACHE_TTL_SECONDS` | `600` | How long resolved locations stay cached |

## Containerizing it locally

Docker was not found on this machine; install [Docker Desktop](https://www.docker.com/products/docker-desktop/) if you want to try this (that installer does need admin rights, since it installs a system virtualization component — there's no way around that one).

Build the image locally:

```bash
docker build -t weather-mcp-server .
```

Run it — **`-i` is required** (keeps stdin open) since MCP servers speak stdio, not HTTP; there's no port to publish:

```bash
docker run -i --rm weather-mcp-server
```

To point Claude Desktop or another MCP client at the container instead of a local Python process, use `docker run -i --rm weather-mcp-server` as the `command`/`args` in its config, the same way you would `uv run ...` above.

`docker-compose.yml` is included mainly to make `docker compose build` convenient; because compose services are meant to stay running and stdio MCP servers are meant to be attached to interactively, prefer `docker run -i` directly for actually talking to the server.

## Testing

### Automated tests (`pytest`)

Unit tests mock all HTTP calls (via `pytest-httpx`) or use fake clients, so they run offline and fast:

```bash
uv run pytest
# or, with a venv activated:
pytest
```

A separate integration suite (`tests/test_server_integration.py`) launches the real server as a subprocess over stdio, exactly as a real MCP client would, and calls each tool against the live Open-Meteo API. It's excluded by default (see `addopts` in `pyproject.toml`) since it needs network access; run it explicitly:

```bash
uv run pytest -m integration
```

### Manual script (the fastest way to see it work)

`scripts/manual_client.py` starts the server and calls all three tools against a real location, printing formatted JSON — no pytest knowledge required:

```bash
uv run python scripts/manual_client.py "Austin, TX"
```

Expected output looks like:

```
Available tools: ['get_current_weather', 'get_weather_forecast', 'recommend_best_time_for_activity']

--- Current weather ---
{
  "location": "Austin, Texas, United States",
  "temperature": 29.4,
  ...
}

--- 3-day forecast ---
{ ... }

--- Hiking recommendation ---
{
  "recommendations": [
    {"date": "2026-09-21", "score": 88, "best_time_window": "07:00-10:00", ...},
    ...
  ]
}
```

## Extending this server

Some natural next steps, if you want to keep building:

- Add a `favorite_locations` MCP resource backed by a small local file, so the assistant can remember places you ask about often.
- Swap `ActivityRubric` thresholds to load from a config file instead of the hardcoded dict in `activity_advisor.py`, if you want users to tune them.
- Add severe-weather alerts (the US National Weather Service API has a free alerts endpoint) as a fourth tool.
