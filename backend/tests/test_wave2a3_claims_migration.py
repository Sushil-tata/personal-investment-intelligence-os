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


def test_claims_evidence_migration_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "wave2a3_migration.sqlite"
    db_url = f"sqlite:///{db_path}"
    config = _alembic_config(db_url)

    command.upgrade(config, "0007_claims_evidence_provenance")

    engine = create_engine(db_url)
    insp = inspect(engine)
    table_names = set(insp.get_table_names())
    assert "thesis_claims" in table_names
    assert "evidence_sources" in table_names
    assert "evidence_items" in table_names
    assert "claim_evidence_interpretations" in table_names
    assert "provenance_records" in table_names

    claim_fks = {fk["name"] for fk in insp.get_foreign_keys("thesis_claims")}
    assert "fk_thesis_claims_thesis_version_id" in claim_fks

    evidence_fks = {fk["name"] for fk in insp.get_foreign_keys("evidence_items")}
    assert "fk_evidence_items_source_id" in evidence_fks

    command.downgrade(config, "0006_thesis_versioned_domain")
    insp_after_down = inspect(engine)
    down_tables = set(insp_after_down.get_table_names())
    assert "thesis_claims" not in down_tables
    assert "evidence_sources" not in down_tables
    assert "evidence_items" not in down_tables
    assert "claim_evidence_interpretations" not in down_tables
    assert "provenance_records" not in down_tables

    command.upgrade(config, "0007_claims_evidence_provenance")
    insp_after_up = inspect(engine)
    up_tables = set(insp_after_up.get_table_names())
    assert "thesis_claims" in up_tables
    assert "evidence_sources" in up_tables
    assert "evidence_items" in up_tables
    assert "claim_evidence_interpretations" in up_tables
    assert "provenance_records" in up_tables
