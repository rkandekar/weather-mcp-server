"""MCP server entrypoint: declares tools/resources/prompts and wires them to the
service layer in `weather_mcp.services`.

The MCP primitives (tools, a resource, a prompt) are kept as thin functions per
the `MCPServer` decorator API; all real logic lives in testable classes below
them, so this module is really just a wiring diagram.

Run directly with:
    python -m weather_mcp.server
or, once installed as a console script:
    weather-mcp
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from weather_mcp.clients.geocoding_client import GeocodingClient, LocationNotFoundError
from weather_mcp.clients.weather_client import WeatherClient
from weather_mcp.config import Settings
from weather_mcp.services.activity_advisor import ACTIVITY_RUBRICS, ActivityAdvisor
from weather_mcp.services.weather_service import WeatherService

settings = Settings.from_env()
_geocoding_client = GeocodingClient(settings)
_weather_client = WeatherClient(settings)
weather_service = WeatherService(_geocoding_client, _weather_client, cache_ttl_seconds=settings.cache_ttl_seconds)
activity_advisor = ActivityAdvisor(_geocoding_client, _weather_client)

mcp = MCPServer("weather")


@mcp.tool()
async def get_current_weather(location: str, units: str = "metric") -> dict:
    """Get current weather conditions for a location.

    Args:
        location: A place name, e.g. "Austin, TX" or "Paris, France".
        units: "metric" (Celsius, km/h) or "imperial" (Fahrenheit, mph).
    """
    try:
        return await weather_service.get_current_weather(location, units)
    except LocationNotFoundError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def get_weather_forecast(location: str, days: int = 5, units: str = "metric") -> dict:
    """Get a multi-day weather forecast for a location.

    Args:
        location: A place name, e.g. "Austin, TX" or "Paris, France".
        days: Number of days to forecast, 1-16.
        units: "metric" (Celsius, km/h) or "imperial" (Fahrenheit, mph).
    """
    try:
        return await weather_service.get_forecast(location, days=days, units=units)
    except LocationNotFoundError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
async def recommend_best_time_for_activity(location: str, activity: str, days: int = 5) -> dict:
    """Recommend the best day and time window at a location for an outdoor activity.

    Unlike a plain forecast, this scores each upcoming day (temperature, rain
    chance, wind, UV, and air quality) against an activity-specific rubric and
    returns a ranked, explained recommendation - useful for "when should I go
    for a run this week?" style questions that a weather website won't answer.

    Args:
        location: A place name, e.g. "Austin, TX" or "Paris, France".
        activity: One of "running", "cycling", "hiking", "beach", "outdoor_event", "picnic".
        days: How many upcoming days to consider, 1-10.
    """
    try:
        return await activity_advisor.recommend(location, activity, days=days)
    except LocationNotFoundError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.resource("weather://capabilities")
def capabilities() -> str:
    """Static resource describing what this server offers, for client discovery/help UIs."""
    return (
        "Weather MCP Server\n"
        "Tools: get_current_weather, get_weather_forecast, recommend_best_time_for_activity\n"
        f"Supported activities: {', '.join(ACTIVITY_RUBRICS)}\n"
        "Data source: Open-Meteo (free, no API key required)."
    )


@mcp.prompt()
def plan_outdoor_day(location: str, activity: str = "hiking") -> str:
    """Prompt template that guides the assistant to use the activity advisor tool."""
    return (
        f"Use the recommend_best_time_for_activity tool for {activity} in {location}, "
        "then summarize the single best day and time window in two sentences, "
        "mentioning temperature and precipitation risk."
    )


def main() -> None:
    """Process entrypoint used by `python -m weather_mcp.server` and the `weather-mcp` console script."""
    mcp.run()


if __name__ == "__main__":
    main()
