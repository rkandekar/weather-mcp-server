"""Unit tests for GeocodingClient, with the Open-Meteo API mocked out (no network)."""
import pytest

from weather_mcp.clients.geocoding_client import GeocodingClient, LocationNotFoundError
from weather_mcp.config import Settings


@pytest.fixture
def client(settings: Settings) -> GeocodingClient:
    return GeocodingClient(settings)


async def test_resolve_returns_top_match(client: GeocodingClient, httpx_mock):
    httpx_mock.add_response(
        json={
            "results": [
                {
                    "name": "Austin",
                    "country": "United States",
                    "admin1": "Texas",
                    "latitude": 30.27,
                    "longitude": -97.74,
                    "timezone": "America/Chicago",
                }
            ]
        }
    )

    resolved = await client.resolve("Austin, TX")

    assert resolved.name == "Austin"
    assert resolved.country == "United States"
    assert resolved.admin1 == "Texas"
    assert resolved.coordinates.latitude == 30.27
    assert resolved.coordinates.longitude == -97.74


async def test_resolve_raises_when_no_match(client: GeocodingClient, httpx_mock):
    httpx_mock.add_response(json={"results": []})

    with pytest.raises(LocationNotFoundError):
        await client.resolve("Notarealplace1234")
