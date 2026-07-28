from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


REVISION_PRE_HARDENING = "0009_w2b_m4_traceability"
REVISION_HARDENED = "0010_w2b1_audit_immutability"


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _fk_ondelete_for_traces(engine, constrained_column: str) -> str | None:
    inspector = inspect(engine)
    for fk in inspector.get_foreign_keys("decision_recommendation_traces"):
        cols = fk.get("constrained_columns") or []
        if cols == [constrained_column]:
            options = fk.get("options") or {}
            ondelete = options.get("ondelete")
            return str(ondelete).upper() if ondelete is not None else None
    return None


def test_wave2b1_audit_immutability_migration_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "wave2b1_audit_immutability.sqlite"
    db_url = f"sqlite:///{db_path}"
    config = _alembic_config(db_url)

    command.upgrade(config, REVISION_HARDENED)
    engine = create_engine(db_url)

    assert _fk_ondelete_for_traces(engine, "proposal_id") in {"RESTRICT", "NO ACTION"}
    assert _fk_ondelete_for_traces(engine, "proposal_version_id") in {"RESTRICT", "NO ACTION"}
    assert _fk_ondelete_for_traces(engine, "input_snapshot_id") in {"RESTRICT", "NO ACTION"}

    command.downgrade(config, REVISION_PRE_HARDENING)
    assert _fk_ondelete_for_traces(engine, "proposal_id") == "CASCADE"
    assert _fk_ondelete_for_traces(engine, "proposal_version_id") == "CASCADE"
    assert _fk_ondelete_for_traces(engine, "input_snapshot_id") == "CASCADE"

    command.upgrade(config, REVISION_HARDENED)
    assert _fk_ondelete_for_traces(engine, "proposal_id") in {"RESTRICT", "NO ACTION"}
    assert _fk_ondelete_for_traces(engine, "proposal_version_id") in {"RESTRICT", "NO ACTION"}
    assert _fk_ondelete_for_traces(engine, "input_snapshot_id") in {"RESTRICT", "NO ACTION"}
