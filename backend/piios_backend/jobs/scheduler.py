from apscheduler.schedulers.background import BackgroundScheduler

from piios_backend.jobs.tasks import (
    alert_generation_job,
    daily_market_data_refresh,
    daily_watchlist_score_refresh,
    weekly_portfolio_drift_check,
    weekly_recommendation_refresh,
)


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(daily_market_data_refresh, "cron", hour=18, minute=0, id="daily_market_data_refresh")
    scheduler.add_job(daily_watchlist_score_refresh, "cron", hour=18, minute=30, id="daily_watchlist_score_refresh")
    scheduler.add_job(alert_generation_job, "cron", hour=19, minute=0, id="alert_generation")
    scheduler.add_job(weekly_portfolio_drift_check, "cron", day_of_week="mon", hour=9, minute=0, id="weekly_portfolio_drift")
    scheduler.add_job(weekly_recommendation_refresh, "cron", day_of_week="mon", hour=10, minute=0, id="weekly_recommendation_refresh")
    return scheduler
