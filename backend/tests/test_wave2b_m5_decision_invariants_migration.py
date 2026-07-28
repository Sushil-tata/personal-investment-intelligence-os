from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


REVISION_PRE_M5 = "0010_w2b1_audit_immutability"
REVISION_M5 = "0011_w2b_m5_decision_invariants"


def _alembic_config(db_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _constraint_names(engine) -> set[str]:
    inspector = inspect(engine)
    checks = inspector.get_check_constraints("decision_investment_decisions")
    return {row["name"] for row in checks if row.get("name")}


def test_wave2b_m5_decision_invariants_migration_upgrade_downgrade_reupgrade(tmp_path: Path) -> None:
    db_path = tmp_path / "wave2b_m5_decision_invariants.sqlite"
    db_url = f"sqlite:///{db_path}"
    config = _alembic_config(db_url)

    expected = {
        "ck_decision_modified_requires_payload",
        "ck_decision_non_modified_forbids_payload",
        "ck_decision_overridden_requires_alternative",
        "ck_decision_non_overridden_forbids_alternative",
        "ck_decision_modified_action_weight_pair",
        "ck_decision_modified_position_weight_pair",
        "ck_decision_modified_action_weight_order",
        "ck_decision_modified_position_weight_order",
    }

    command.upgrade(config, REVISION_M5)
    engine = create_engine(db_url)
    assert expected.issubset(_constraint_names(engine))

    command.downgrade(config, REVISION_PRE_M5)
    assert expected.isdisjoint(_constraint_names(engine))

    command.upgrade(config, REVISION_M5)
    assert expected.issubset(_constraint_names(engine))
