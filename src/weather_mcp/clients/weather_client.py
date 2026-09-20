"""HTTP client for current conditions, forecasts, and air quality from Open-Meteo."""
from __future__ import annotations

import httpx

from weather_mcp.config import Settings
from weather_mcp.models import Coordinates, CurrentConditions, DailyForecast, HourlyPoint, Units

# WMO weather interpretation codes (a subset covering the common cases), per
# https://open-meteo.com/en/docs - the API returns integers, not descriptions.
WMO_WEATHER_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: int) -> str:
    """Translate a WMO weather code into a short human-readable description."""
    return WMO_WEATHER_DESCRIPTIONS.get(code, "Unknown conditions")


class WeatherClient:
    """Async wrapper around the Open-Meteo forecast and air-quality APIs."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        """Create a client.

        Args:
            settings: Server configuration, used for base URLs and timeout.
            http_client: Optional pre-built httpx client, primarily for tests.
        """
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    @staticmethod
    def _unit_params(units: Units) -> dict[str, str]:
        """Map our "metric"/"imperial" choice to Open-Meteo's unit query params."""
        if units == "imperial":
            return {"temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch"}
        return {"temperature_unit": "celsius", "wind_speed_unit": "kmh", "precipitation_unit": "mm"}

    async def get_current_conditions(self, coordinates: Coordinates, units: Units = "metric") -> CurrentConditions:
        """Fetch the current weather conditions at a coordinate.

        Args:
            coordinates: Latitude/longitude to query.
            units: "metric" (Celsius, km/h, mm) or "imperial" (Fahrenheit, mph, in).
        """
        params = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "timezone": "auto",
            **self._unit_params(units),
        }
        response = await self._client.get(self._settings.forecast_base_url, params=params)
        response.raise_for_status()
        current = response.json()["current"]
        return CurrentConditions(
            observed_at=current["time"],
            temperature=current["temperature_2m"],
            feels_like=current["apparent_temperature"],
            humidity_percent=current["relative_humidity_2m"],
            wind_speed=current["wind_speed_10m"],
            wind_direction_degrees=current["wind_direction_10m"],
            precipitation=current["precipitation"],
            weather_description=describe_weather_code(current["weather_code"]),
            units=units,
        )

    async def get_daily_forecast(
        self, coordinates: Coordinates, days: int, units: Units = "metric"
    ) -> list[DailyForecast]:
        """Fetch a day-by-day forecast summary.

        Args:
            coordinates: Latitude/longitude to query.
            days: Number of days to forecast, 1-16 (an Open-Meteo limit).
            units: "metric" or "imperial".
        """
        params = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_probability_max,"
            "uv_index_max,wind_speed_10m_max,weather_code",
            "forecast_days": days,
            "timezone": "auto",
            **self._unit_params(units),
        }
        response = await self._client.get(self._settings.forecast_base_url, params=params)
        response.raise_for_status()
        daily = response.json()["daily"]
        return [
            DailyForecast(
                date=daily["time"][i],
                temperature_min=daily["temperature_2m_min"][i],
                temperature_max=daily["temperature_2m_max"][i],
                precipitation_probability_percent=daily["precipitation_probability_max"][i],
                uv_index_max=daily["uv_index_max"][i],
                wind_speed_max=daily["wind_speed_10m_max"][i],
                weather_description=describe_weather_code(daily["weather_code"][i]),
            )
            for i in range(len(daily["time"]))
        ]

    async def get_hourly_points(self, coordinates: Coordinates, days: int) -> list[HourlyPoint]:
        """Fetch hourly temperature/precipitation/wind/UV points, always in metric units.

        Metric is fixed here (rather than parameterized) because these points
        feed the activity-scoring rubrics internally; they are never returned
        to an MCP client directly, so display units don't apply. Timestamps
        are in the location's local time (not UTC), which matters here since
        the activity advisor reports recommended hours to the end user.

        Args:
            coordinates: Latitude/longitude to query.
            days: Number of days of hourly data to fetch, 1-16.
        """
        params = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,uv_index",
            "forecast_days": days,
            "timezone": "auto",
        }
        response = await self._client.get(self._settings.forecast_base_url, params=params)
        response.raise_for_status()
        hourly = response.json()["hourly"]
        return [
            HourlyPoint(
                timestamp=hourly["time"][i],
                temperature_c=hourly["temperature_2m"][i],
                precipitation_probability_percent=hourly["precipitation_probability"][i],
                wind_speed_kph=hourly["wind_speed_10m"][i],
                uv_index=hourly["uv_index"][i],
            )
            for i in range(len(hourly["time"]))
        ]

    async def get_air_quality_daily_average(self, coordinates: Coordinates, days: int) -> dict[str, float]:
        """Fetch hourly US AQI and return the average value per calendar date.

        Args:
            coordinates: Latitude/longitude to query.
            days: Number of days of air-quality data to fetch.

        Returns:
            A mapping of ISO date string (e.g. "2026-09-20") to average AQI.
            Dates with no readings are omitted rather than defaulted to zero.
        """
        params = {
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "hourly": "us_aqi",
            "forecast_days": days,
            "timezone": "auto",
        }
        response = await self._client.get(self._settings.air_quality_base_url, params=params)
        response.raise_for_status()
        hourly = response.json()["hourly"]

        readings_by_date: dict[str, list[float]] = {}
        for timestamp, aqi in zip(hourly["time"], hourly["us_aqi"]):
            if aqi is None:
                continue
            date = timestamp.split("T")[0]
            readings_by_date.setdefault(date, []).append(aqi)

        return {date: sum(values) / len(values) for date, values in readings_by_date.items()}

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()
