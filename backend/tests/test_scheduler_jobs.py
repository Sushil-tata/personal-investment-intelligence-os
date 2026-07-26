from piios_backend.jobs.scheduler import build_scheduler


def test_scheduler_has_required_jobs() -> None:
    scheduler = build_scheduler()
    job_ids = {job.id for job in scheduler.get_jobs()}
    assert "daily_market_data_refresh" in job_ids
    assert "daily_watchlist_score_refresh" in job_ids
    assert "alert_generation" in job_ids
    assert "weekly_portfolio_drift" in job_ids
    assert "weekly_recommendation_refresh" in job_ids
