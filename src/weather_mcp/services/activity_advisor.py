"""Activity-aware weather scoring: the feature that goes beyond a plain weather lookup.

A weather website reports numbers; it doesn't tell you that Tuesday morning
beats Thursday afternoon for a run. This module encodes simple domain rubrics
for common outdoor activities, scores upcoming days (and the best hourly
window within each day) against those rubrics, and returns a ranked,
explained recommendation - the kind of synthesis an LLM-facing tool should do
so the assistant doesn't have to eyeball a forecast table itself.
"""
from __future__ import annotations

from dataclasses import dataclass

from weather_mcp.clients.geocoding_client import GeocodingClient
from weather_mcp.clients.weather_client import WeatherClient
from weather_mcp.models import DailyForecast, HourlyPoint


@dataclass(frozen=True)
class ActivityRubric:
    """Ideal-condition thresholds used to score a day against one activity."""

    ideal_temp_c: tuple[float, float]
    max_wind_kph: float
    max_precipitation_probability: float
    max_uv_index: float
    max_aqi: float


ACTIVITY_RUBRICS: dict[str, ActivityRubric] = {
    "running": ActivityRubric((8, 18), 25, 30, 7, 100),
    "cycling": ActivityRubric((10, 24), 20, 20, 8, 100),
    "hiking": ActivityRubric((10, 24), 30, 30, 9, 120),
    "beach": ActivityRubric((24, 32), 25, 15, 11, 100),
    "outdoor_event": ActivityRubric((15, 27), 20, 15, 8, 100),
    "picnic": ActivityRubric((16, 26), 15, 10, 7, 100),
}

DAYLIGHT_HOURS = range(6, 21)
WINDOW_LENGTH_HOURS = 3


class ActivityAdvisor:
    """Recommends the best day and time window for an outdoor activity at a location."""

    def __init__(self, geocoding_client: GeocodingClient, weather_client: WeatherClient) -> None:
        """Create the advisor.

        Args:
            geocoding_client: Resolves place names to coordinates.
            weather_client: Fetches forecast and air-quality data.
        """
        self._geocoding_client = geocoding_client
        self._weather_client = weather_client

    async def recommend(self, location: str, activity: str, days: int = 5) -> dict:
        """Score the next `days` days for `activity` and return a ranked recommendation.

        Args:
            location: Free-text place name.
            activity: One of the keys in ACTIVITY_RUBRICS (e.g. "hiking", "beach").
            days: How many upcoming days to consider, 1-10.

        Returns:
            A dict with the resolved location, the activity, and a
            best-first list of per-day results, each including a 0-100
            score, human-readable reasons, and (when hourly data allows) a
            recommended time window on that day.

        Raises:
            LocationNotFoundError: If `location` cannot be resolved.
            ValueError: If `activity` is unsupported or `days` is out of range.
        """
        rubric = ACTIVITY_RUBRICS.get(activity)
        if rubric is None:
            raise ValueError(f"Unsupported activity {activity!r}. Choose from: {', '.join(ACTIVITY_RUBRICS)}")
        if not 1 <= days <= 10:
            raise ValueError("days must be between 1 and 10")

        resolved = await self._geocoding_client.resolve(location)
        daily_forecast = await self._weather_client.get_daily_forecast(resolved.coordinates, days)
        hourly_points = await self._weather_client.get_hourly_points(resolved.coordinates, days)
        aqi_by_date = await self._weather_client.get_air_quality_daily_average(resolved.coordinates, days)

        hourly_by_date: dict[str, list[HourlyPoint]] = {}
        for point in hourly_points:
            hourly_by_date.setdefault(point.timestamp.split("T")[0], []).append(point)

        results = []
        for day in daily_forecast:
            score, reasons = _score_day(day, rubric, aqi_by_date.get(day.date, 0.0))
            results.append(
                {
                    "date": day.date,
                    "score": score,
                    "conditions": day.weather_description,
                    "temperature_range_c": [day.temperature_min, day.temperature_max],
                    "reasons": reasons,
                    "best_time_window": _best_hourly_window(hourly_by_date.get(day.date, []), rubric),
                }
            )

        results.sort(key=lambda item: item["score"], reverse=True)
        return {
            "location": ", ".join(part for part in [resolved.name, resolved.admin1, resolved.country] if part),
            "activity": activity,
            "recommendations": results,
        }


def _score_day(day: DailyForecast, rubric: ActivityRubric, aqi: float) -> tuple[int, list[str]]:
    """Score a single day 0-100 against an activity rubric, listing any penalties applied."""
    score = 100.0
    reasons: list[str] = []
    low, high = rubric.ideal_temp_c
    avg_temp = (day.temperature_min + day.temperature_max) / 2

    if avg_temp < low:
        score -= min(40, (low - avg_temp) * 4)
        reasons.append(f"Cooler than ideal ({avg_temp:.0f}C vs {low:.0f}-{high:.0f}C)")
    elif avg_temp > high:
        score -= min(40, (avg_temp - high) * 4)
        reasons.append(f"Warmer than ideal ({avg_temp:.0f}C vs {low:.0f}-{high:.0f}C)")

    if day.precipitation_probability_percent > rubric.max_precipitation_probability:
        score -= 25
        reasons.append(f"High chance of precipitation ({day.precipitation_probability_percent:.0f}%)")

    if day.wind_speed_max > rubric.max_wind_kph:
        score -= 15
        reasons.append(f"Windy ({day.wind_speed_max:.0f} km/h)")

    if day.uv_index_max > rubric.max_uv_index:
        score -= 10
        reasons.append(f"High UV index ({day.uv_index_max:.0f})")

    if aqi > rubric.max_aqi:
        score -= 15
        reasons.append(f"Elevated air quality index ({aqi:.0f})")

    if not reasons:
        reasons.append("Conditions are within the ideal range for this activity")

    return max(0, round(score)), reasons


def _best_hourly_window(points: list[HourlyPoint], rubric: ActivityRubric) -> str | None:
    """Find the WINDOW_LENGTH_HOURS-hour daylight window with the best average conditions.

    Args:
        points: Hourly points for a single day (any order; only daylight hours are used).
        rubric: The activity rubric to score hours against.

    Returns:
        A "HH:00-HH:00" string, or None if there isn't enough hourly data for the day.
    """
    daylight_points = sorted(
        (p for p in points if _hour_of(p.timestamp) in DAYLIGHT_HOURS),
        key=lambda p: p.timestamp,
    )
    if len(daylight_points) < WINDOW_LENGTH_HOURS:
        return None

    best_start_index = 0
    best_average = float("-inf")
    for start in range(len(daylight_points) - WINDOW_LENGTH_HOURS + 1):
        window = daylight_points[start : start + WINDOW_LENGTH_HOURS]
        average = sum(_hourly_suitability(p, rubric) for p in window) / WINDOW_LENGTH_HOURS
        if average > best_average:
            best_average = average
            best_start_index = start

    start_hour = _hour_of(daylight_points[best_start_index].timestamp)
    return f"{start_hour:02d}:00-{start_hour + WINDOW_LENGTH_HOURS:02d}:00"


def _hourly_suitability(point: HourlyPoint, rubric: ActivityRubric) -> float:
    """Score a single hourly point; higher is better. Used only to rank windows within a day."""
    low, high = rubric.ideal_temp_c
    if point.temperature_c < low:
        temp_penalty = low - point.temperature_c
    elif point.temperature_c > high:
        temp_penalty = point.temperature_c - high
    else:
        temp_penalty = 0.0
    precip_penalty = max(0.0, point.precipitation_probability_percent - rubric.max_precipitation_probability) / 5
    wind_penalty = max(0.0, point.wind_speed_kph - rubric.max_wind_kph) / 5
    return -(temp_penalty + precip_penalty + wind_penalty)


def _hour_of(timestamp: str) -> int:
    """Extract the hour component (0-23) from an ISO-8601 timestamp like '2026-09-19T14:00'."""
    return int(timestamp.split("T")[1].split(":")[0])
