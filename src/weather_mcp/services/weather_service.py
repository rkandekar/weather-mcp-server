"""Application-level weather use cases: resolving a location and shaping API data
for MCP tool responses.
"""
from __future__ import annotations

from weather_mcp.cache import TTLCache
from weather_mcp.clients.geocoding_client import GeocodingClient
from weather_mcp.clients.weather_client import WeatherClient
from weather_mcp.models import ResolvedLocation, Units


class WeatherService:
    """Combines geocoding and forecast lookups into the shapes MCP tools return.

    A small TTL cache sits in front of geocoding, since a place name's
    coordinates essentially never change and shouldn't cost a network round
    trip on every call within the same session.
    """

    def __init__(
        self,
        geocoding_client: GeocodingClient,
        weather_client: WeatherClient,
        cache_ttl_seconds: float,
    ) -> None:
        """Create the service.

        Args:
            geocoding_client: Resolves place names to coordinates.
            weather_client: Fetches current/forecast weather data.
            cache_ttl_seconds: How long a resolved location stays cached.
        """
        self._geocoding_client = geocoding_client
        self._weather_client = weather_client
        self._location_cache: TTLCache[ResolvedLocation] = TTLCache(cache_ttl_seconds)

    async def _resolve_location(self, location: str) -> ResolvedLocation:
        """Resolve a free-text location string to coordinates, using the cache first."""
        cache_key = location.strip().lower()
        cached = self._location_cache.get(cache_key)
        if cached is not None:
            return cached

        resolved = await self._geocoding_client.resolve(location)
        self._location_cache.set(cache_key, resolved)
        return resolved

    async def get_current_weather(self, location: str, units: Units = "metric") -> dict:
        """Return current weather conditions for a location as a JSON-serializable dict.

        Args:
            location: Free-text place name, e.g. "Austin, TX".
            units: "metric" or "imperial".

        Raises:
            LocationNotFoundError: If `location` cannot be resolved.
        """
        resolved = await self._resolve_location(location)
        conditions = await self._weather_client.get_current_conditions(resolved.coordinates, units)
        return {
            "location": _describe_location(resolved),
            "observed_at": conditions.observed_at,
            "temperature": conditions.temperature,
            "feels_like": conditions.feels_like,
            "humidity_percent": conditions.humidity_percent,
            "wind_speed": conditions.wind_speed,
            "wind_direction_degrees": conditions.wind_direction_degrees,
            "precipitation": conditions.precipitation,
            "conditions": conditions.weather_description,
            "units": units,
        }

    async def get_forecast(self, location: str, days: int = 5, units: Units = "metric") -> dict:
        """Return a multi-day forecast for a location as a JSON-serializable dict.

        Args:
            location: Free-text place name.
            days: Number of days to forecast, 1-16.
            units: "metric" or "imperial".

        Raises:
            LocationNotFoundError: If `location` cannot be resolved.
            ValueError: If `days` is out of range.
        """
        if not 1 <= days <= 16:
            raise ValueError("days must be between 1 and 16")

        resolved = await self._resolve_location(location)
        forecast = await self._weather_client.get_daily_forecast(resolved.coordinates, days, units)
        return {
            "location": _describe_location(resolved),
            "units": units,
            "days": [day.__dict__ for day in forecast],
        }


def _describe_location(resolved: ResolvedLocation) -> str:
    """Format a resolved location as "City, Region, Country" for display."""
    parts = [resolved.name, resolved.admin1, resolved.country]
    return ", ".join(part for part in parts if part)
