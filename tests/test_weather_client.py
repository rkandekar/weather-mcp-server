"""Unit tests for WeatherClient, with the Open-Meteo API mocked out (no network)."""
import pytest

from weather_mcp.clients.weather_client import WeatherClient, describe_weather_code
from weather_mcp.config import Settings
from weather_mcp.models import Coordinates

AUSTIN = Coordinates(latitude=30.27, longitude=-97.74)


@pytest.fixture
def client(settings: Settings) -> WeatherClient:
    return WeatherClient(settings)


def test_describe_weather_code_known_and_unknown():
    assert describe_weather_code(0) == "Clear sky"
    assert describe_weather_code(9999) == "Unknown conditions"


async def test_get_current_conditions_maps_fields(client: WeatherClient, httpx_mock):
    httpx_mock.add_response(
        json={
            "current": {
                "time": "2026-09-19T12:00",
                "temperature_2m": 22.5,
                "apparent_temperature": 21.0,
                "relative_humidity_2m": 55,
                "precipitation": 0.0,
                "weather_code": 1,
                "wind_speed_10m": 10.2,
                "wind_direction_10m": 180,
            }
        }
    )

    conditions = await client.get_current_conditions(AUSTIN, units="metric")

    assert conditions.temperature == 22.5
    assert conditions.weather_description == "Mainly clear"
    assert conditions.units == "metric"


async def test_get_daily_forecast_maps_each_day(client: WeatherClient, httpx_mock):
    httpx_mock.add_response(
        json={
            "daily": {
                "time": ["2026-09-20", "2026-09-21"],
                "temperature_2m_min": [15.0, 16.0],
                "temperature_2m_max": [25.0, 26.0],
                "precipitation_probability_max": [10, 60],
                "uv_index_max": [5.0, 6.0],
                "wind_speed_10m_max": [12.0, 30.0],
                "weather_code": [0, 61],
            }
        }
    )

    days = await client.get_daily_forecast(AUSTIN, days=2)

    assert len(days) == 2
    assert days[0].date == "2026-09-20"
    assert days[0].weather_description == "Clear sky"
    assert days[1].precipitation_probability_percent == 60


async def test_get_air_quality_daily_average_skips_null_readings(client: WeatherClient, httpx_mock):
    httpx_mock.add_response(
        json={
            "hourly": {
                "time": ["2026-09-20T00:00", "2026-09-20T01:00", "2026-09-20T02:00"],
                "us_aqi": [40, None, 60],
            }
        }
    )

    averages = await client.get_air_quality_daily_average(AUSTIN, days=1)

    assert averages == {"2026-09-20": 50.0}
