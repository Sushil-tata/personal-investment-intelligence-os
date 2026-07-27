from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def test_wave2b_m4_traceability_migration_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "wave2b_m4_traceability.sqlite"
    db_url = f"sqlite:///{db_path}"
    config = _alembic_config(db_url)

    command.upgrade(config, "0009_w2b_m4_traceability")
    engine = create_engine(db_url)
    insp = inspect(engine)
    names = set(insp.get_table_names())

    assert "decision_recommendation_traces" in names
    assert "decision_recommendation_trace_entries" in names

    command.downgrade(config, "0008_wave2b_m2_sqlmodel_persist")
    names_after_down = set(inspect(engine).get_table_names())
    assert "decision_recommendation_traces" not in names_after_down
    assert "decision_recommendation_trace_entries" not in names_after_down

    command.upgrade(config, "0009_w2b_m4_traceability")
    names_after_reup = set(inspect(engine).get_table_names())
    assert "decision_recommendation_traces" in names_after_reup
    assert "decision_recommendation_trace_entries" in names_after_reup
