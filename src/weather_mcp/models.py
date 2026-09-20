"""Typed data models shared across the weather MCP server's clients and services."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Units = Literal["metric", "imperial"]


@dataclass(frozen=True)
class Coordinates:
    """A latitude/longitude pair."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class ResolvedLocation:
    """The result of turning a free-text place name into a specific, geocoded place."""

    query: str
    name: str
    country: str
    admin1: str | None
    coordinates: Coordinates
    timezone: str


@dataclass(frozen=True)
class CurrentConditions:
    """A snapshot of current weather at a point in time."""

    observed_at: str
    temperature: float
    feels_like: float
    humidity_percent: float
    wind_speed: float
    wind_direction_degrees: float
    precipitation: float
    weather_description: str
    units: Units


@dataclass(frozen=True)
class DailyForecast:
    """A single day's forecast summary."""

    date: str
    temperature_min: float
    temperature_max: float
    precipitation_probability_percent: float
    uv_index_max: float
    wind_speed_max: float
    weather_description: str


@dataclass(frozen=True)
class HourlyPoint:
    """A single hour's forecast, always in metric units.

    Used internally by the activity advisor's scoring logic rather than
    returned directly to MCP clients, so it does not need unit conversion.
    """

    timestamp: str
    temperature_c: float
    precipitation_probability_percent: float
    wind_speed_kph: float
    uv_index: float
