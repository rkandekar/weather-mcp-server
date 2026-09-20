"""Unit tests for the activity scoring logic, using fake clients (no network)."""
import pytest

from weather_mcp.models import Coordinates, DailyForecast, HourlyPoint, ResolvedLocation
from weather_mcp.services.activity_advisor import ActivityAdvisor


class _FakeGeocodingClient:
    async def resolve(self, query: str) -> ResolvedLocation:
        return ResolvedLocation(
            query=query,
            name="Austin",
            country="United States",
            admin1="Texas",
            coordinates=Coordinates(30.27, -97.74),
            timezone="America/Chicago",
        )


class _FakeWeatherClient:
    def __init__(self, daily=None, hourly=None, aqi=None):
        self._daily = daily or []
        self._hourly = hourly or []
        self._aqi = aqi or {}

    async def get_daily_forecast(self, coordinates, days, units="metric"):
        return self._daily[:days]

    async def get_hourly_points(self, coordinates, days):
        return self._hourly

    async def get_air_quality_daily_average(self, coordinates, days):
        return self._aqi


def _day(date, temp_min, temp_max, precip=10, uv=5, wind=10):
    return DailyForecast(
        date=date,
        temperature_min=temp_min,
        temperature_max=temp_max,
        precipitation_probability_percent=precip,
        uv_index_max=uv,
        wind_speed_max=wind,
        weather_description="Clear sky",
    )


async def test_ideal_day_scores_highest_and_is_ranked_first():
    daily = [
        _day("2026-09-20", 5, 10, precip=80, wind=40),  # cold, rainy, windy: bad for running
        _day("2026-09-21", 14, 16, precip=5, uv=3, wind=8),  # squarely in the ideal range
    ]
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient(daily=daily))

    result = await advisor.recommend("Austin, TX", "running", days=2)

    assert result["activity"] == "running"
    assert result["recommendations"][0]["date"] == "2026-09-21"
    assert result["recommendations"][0]["score"] > result["recommendations"][1]["score"]
    assert "Conditions are within the ideal range" in result["recommendations"][0]["reasons"][0]


async def test_bad_day_lists_specific_penalty_reasons():
    daily = [_day("2026-09-20", 30, 35, precip=90, uv=11, wind=40)]
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient(daily=daily))

    result = await advisor.recommend("Austin, TX", "running", days=1)

    reasons = " ".join(result["recommendations"][0]["reasons"])
    assert "Warmer than ideal" in reasons
    assert "precipitation" in reasons
    assert "Windy" in reasons


async def test_unsupported_activity_raises_value_error():
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient())

    with pytest.raises(ValueError):
        await advisor.recommend("Austin, TX", "skydiving", days=1)


async def test_days_out_of_range_raises_value_error():
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient())

    with pytest.raises(ValueError):
        await advisor.recommend("Austin, TX", "running", days=0)


async def test_best_time_window_prefers_the_calmer_hours():
    hourly = [
        HourlyPoint("2026-09-20T06:00", temperature_c=25, precipitation_probability_percent=80, wind_speed_kph=40, uv_index=1),
        HourlyPoint("2026-09-20T07:00", temperature_c=14, precipitation_probability_percent=0, wind_speed_kph=5, uv_index=1),
        HourlyPoint("2026-09-20T08:00", temperature_c=15, precipitation_probability_percent=0, wind_speed_kph=5, uv_index=1),
        HourlyPoint("2026-09-20T09:00", temperature_c=16, precipitation_probability_percent=0, wind_speed_kph=5, uv_index=1),
    ]
    daily = [_day("2026-09-20", 10, 18)]
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient(daily=daily, hourly=hourly))

    result = await advisor.recommend("Austin, TX", "running", days=1)

    assert result["recommendations"][0]["best_time_window"] == "07:00-10:00"


async def test_best_time_window_is_none_without_enough_hourly_data():
    daily = [_day("2026-09-20", 10, 18)]
    advisor = ActivityAdvisor(_FakeGeocodingClient(), _FakeWeatherClient(daily=daily, hourly=[]))

    result = await advisor.recommend("Austin, TX", "running", days=1)

    assert result["recommendations"][0]["best_time_window"] is None
