from datetime import datetime, timezone


def _stamp(name: str) -> dict:
    return {"job": name, "at": datetime.now(timezone.utc).isoformat()}


def daily_market_data_refresh() -> dict:
    return _stamp("daily_market_data_refresh")


def daily_watchlist_score_refresh() -> dict:
    return _stamp("daily_watchlist_score_refresh")


def alert_generation_job() -> dict:
    return _stamp("alert_generation")


def weekly_portfolio_drift_check() -> dict:
    return _stamp("weekly_portfolio_drift_check")


def weekly_recommendation_refresh() -> dict:
    return _stamp("weekly_recommendation_refresh")
