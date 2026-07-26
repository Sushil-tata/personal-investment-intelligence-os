import pytest

from piios_backend.core.config import settings


@pytest.fixture(autouse=True)
def disable_live_feeds_for_tests():
    original = settings.live_market_feeds
    settings.live_market_feeds = False
    try:
        yield
    finally:
        settings.live_market_feeds = original
