"""Shared pytest fixtures."""
import pytest

from weather_mcp.config import Settings


@pytest.fixture
def settings() -> Settings:
    """A default Settings instance pointing at the real (but mocked-in-tests) Open-Meteo URLs."""
    return Settings.from_env()
