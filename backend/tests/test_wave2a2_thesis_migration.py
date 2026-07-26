from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def test_thesis_versioning_migration_backfills_legacy_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "wave2a2_migration.sqlite"
    db_url = f"sqlite:///{db_path}"
    config = _alembic_config(db_url)

    command.upgrade(config, "0005_identity_master_tables")

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO investment_theses (
                    thesis_id, ticker, asset_name, theme, bucket, thesis,
                    bull_case, bear_case, why_now, why_not_now,
                    invalidation_trigger, valuation_notes, expected_holding_period,
                    source_documents, confidence_score, status, created_at, updated_at
                ) VALUES (
                    't99', 'AAPL', 'Apple', 'Consumer Platform', 'Strategic Alpha', 'Legacy thesis',
                    'Bull case', 'Bear case', 'Why now', 'Why not now',
                    'Trigger', 'Valuation', '3-5 years',
                    '["rd_aapl_1"]', 71.0, 'RESEARCHED', '2026-07-26T10:00:00+00:00', '2026-07-26T10:00:00+00:00'
                )
                """
            )
        )

    command.upgrade(config, "0006_thesis_versioned_domain")

    insp = inspect(engine)
    assert "thesis_roots" in insp.get_table_names()
    assert "thesis_versions" in insp.get_table_names()

    with engine.begin() as conn:
        root_count = conn.execute(text("SELECT COUNT(*) FROM thesis_roots WHERE thesis_id = 't99'"))
        version_count = conn.execute(text("SELECT COUNT(*) FROM thesis_versions WHERE thesis_id = 't99'"))
        assert int(root_count.scalar_one()) == 1
        assert int(version_count.scalar_one()) == 1

    command.downgrade(config, "0005_identity_master_tables")
    insp_after_downgrade = inspect(engine)
    assert "thesis_roots" not in insp_after_downgrade.get_table_names()
    assert "thesis_versions" not in insp_after_downgrade.get_table_names()
