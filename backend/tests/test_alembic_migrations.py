from pathlib import Path


def test_alembic_assets_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "alembic.ini").exists()
    assert (root / "alembic" / "env.py").exists()
    assert (root / "alembic" / "versions" / "0001_initial_schema.py").exists()
    assert (root / "alembic" / "versions" / "0004_portfolio_layers.py").exists()
    assert (root / "alembic" / "versions" / "0005_identity_master_tables.py").exists()
