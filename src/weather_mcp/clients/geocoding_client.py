"""HTTP client for resolving free-text place names to coordinates."""
from __future__ import annotations

import httpx

from weather_mcp.config import Settings
from weather_mcp.models import Coordinates, ResolvedLocation


class LocationNotFoundError(Exception):
    """Raised when a location query does not match any known place."""

    def __init__(self, query: str) -> None:
        super().__init__(f"Could not resolve location: {query!r}")
        self.query = query


class GeocodingClient:
    """Async wrapper around the Open-Meteo geocoding API.

    Open-Meteo's geocoding endpoint is free and requires no API key or signup,
    which keeps the barrier to entry low for a first MCP server: there is
    nothing to provision before the code runs.
    """

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        """Create a client.

        Args:
            settings: Server configuration, used for the base URL and timeout.
            http_client: Optional pre-built httpx client, primarily for tests.
        """
        self._settings = settings
        self._client = http_client or httpx.AsyncClient(timeout=settings.http_timeout_seconds)

    async def resolve(self, query: str) -> ResolvedLocation:
        """Resolve a free-text location query to its single best-match place.

        Args:
            query: Free text such as "Austin", "Austin, TX", or "Paris, France".

        Returns:
            The top-ranked ResolvedLocation for the query.

        Raises:
            LocationNotFoundError: If the query does not match any place.
        """
        response = await self._client.get(
            self._settings.geocoding_base_url,
            params={"name": query, "count": 1, "language": "en", "format": "json"},
        )
        response.raise_for_status()
        results = response.json().get("results") or []
        if not results:
            raise LocationNotFoundError(query)

        top = results[0]
        return ResolvedLocation(
            query=query,
            name=top["name"],
            country=top.get("country", ""),
            admin1=top.get("admin1"),
            coordinates=Coordinates(latitude=top["latitude"], longitude=top["longitude"]),
            timezone=top.get("timezone", "UTC"),
        )

    async def aclose(self) -> None:
        """Release the underlying HTTP connection pool."""
        await self._client.aclose()
