"""Runtime configuration for the weather MCP server, sourced from environment variables.

Kept as a small, explicit dataclass (rather than a global-settings singleton or a
framework like pydantic-settings) so every dependency declares what it needs and
tests can construct a `Settings` instance directly without touching the environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


@dataclass(frozen=True)
class Settings:
    """Immutable server configuration. Construct via `Settings.from_env()`."""

    geocoding_base_url: str = DEFAULT_GEOCODING_URL
    forecast_base_url: str = DEFAULT_FORECAST_URL
    air_quality_base_url: str = DEFAULT_AIR_QUALITY_URL
    http_timeout_seconds: float = 10.0
    cache_ttl_seconds: float = 600.0

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables, falling back to sane defaults.

        Recognized variables: WEATHER_MCP_GEOCODING_URL, WEATHER_MCP_FORECAST_URL,
        WEATHER_MCP_AIR_QUALITY_URL, WEATHER_MCP_HTTP_TIMEOUT_SECONDS,
        WEATHER_MCP_CACHE_TTL_SECONDS. None require a value for the server to run
        against the free, keyless Open-Meteo API.
        """
        return cls(
            geocoding_base_url=os.getenv("WEATHER_MCP_GEOCODING_URL", DEFAULT_GEOCODING_URL),
            forecast_base_url=os.getenv("WEATHER_MCP_FORECAST_URL", DEFAULT_FORECAST_URL),
            air_quality_base_url=os.getenv("WEATHER_MCP_AIR_QUALITY_URL", DEFAULT_AIR_QUALITY_URL),
            http_timeout_seconds=float(os.getenv("WEATHER_MCP_HTTP_TIMEOUT_SECONDS", "10")),
            cache_ttl_seconds=float(os.getenv("WEATHER_MCP_CACHE_TTL_SECONDS", "600")),
        )
