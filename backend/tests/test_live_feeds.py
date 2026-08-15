from __future__ import annotations

from datetime import datetime, timedelta, timezone

from piios_backend.services.live_feeds import LiveFeedService


def test_cooldown_snapshots_are_unavailable_not_cached(monkeypatch) -> None:
    service = LiveFeedService()
    monkeypatch.setattr(service, "_enabled", lambda: True)
    service._cooldown_until = datetime.now(timezone.utc) + timedelta(minutes=1)

    history = service.history("TEST")
    fundamentals = service.fundamentals("TEST")
    fx = service.fx_rate("USD", "INR")

    assert history.mode == "UNAVAILABLE_COOLDOWN"
    assert history.frame is None
    assert fundamentals.mode == "UNAVAILABLE_COOLDOWN"
    assert fundamentals.info == {}
    assert fx.mode == "UNAVAILABLE_COOLDOWN"
    assert fx.rate is None
    assert {history.error, fundamentals.error, fx.error} == {"cooldown_active"}