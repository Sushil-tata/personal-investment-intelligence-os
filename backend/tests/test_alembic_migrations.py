from pathlib import Path


def test_alembic_assets_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").exists()
    assert (root / "alembic" / "env.py").exists()
    assert (root / "alembic" / "versions" / "0001_initial_schema.py").exists()
    assert (root / "alembic" / "versions" / "0004_portfolio_layers.py").exists()
    assert (root / "alembic" / "versions" / "0005_identity_master_tables.py").exists()
    assert (root / "alembic" / "versions" / "0006_thesis_versioned_domain.py").exists()
    assert (root / "alembic" / "versions" / "0007_claims_evidence_provenance.py").exists()
    assert (root / "alembic" / "versions" / "0008_wave2b_m2_sqlmodel_persist.py").exists()
