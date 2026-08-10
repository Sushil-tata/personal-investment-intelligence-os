import pytest
from alembic import command
from alembic.config import Config
from pathlib import Path
from sqlalchemy import create_engine, text

from piios_backend.core.config import settings


@pytest.fixture(autouse=True)
def disable_live_feeds_for_tests():
    original = settings.live_market_feeds
    settings.live_market_feeds = False
    try:
        yield
    finally:
        settings.live_market_feeds = original


@pytest.fixture(scope="session", autouse=True)
def ensure_postgres_schema_migrated() -> None:
    if not settings.run_db_migrations_in_tests:
        return
    if not settings.db_url.startswith("postgresql"):
        return

    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", settings.db_url)
    command.upgrade(config, "head")

    # Legacy/local DBs can contain statuses outside ThesisStatus enum.
    # Normalize test DB rows so route-contract integration validates APIs, not stale local data artifacts.
    engine = create_engine(settings.db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE thesis_roots
                SET lifecycle_status = 'RESEARCHED'
                WHERE lifecycle_status IS NULL OR lifecycle_status NOT IN (
                    'DRAFT', 'RESEARCHED', 'RISK_CHECKED', 'PENDING_REVIEW', 'APPROVED', 'ARCHIVED'
                )
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE thesis_versions
                SET status = 'RESEARCHED'
                WHERE status IS NULL OR status NOT IN (
                    'DRAFT', 'RESEARCHED', 'RISK_CHECKED', 'PENDING_REVIEW', 'APPROVED', 'ARCHIVED'
                )
                """
            )
        )
