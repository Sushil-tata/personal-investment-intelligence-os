# Legacy Index

This index points to current legacy implementation sources to be migrated incrementally.

Primary legacy portfolio/research files:
- `dashboard/pages/01_Portfolio.py`
- `dashboard/pages/05_Stock_Scorecard.py`
- `dashboard/pages/10_Investment_Thesis_Registry.py`
- `backend/piios_backend/api/routes/portfolio.py`
- `backend/piios_backend/api/routes/portfolio_layers.py`
- `backend/piios_backend/services/portfolio_layers.py`
- `backend/piios_backend/repositories/portfolio_layers.py`

Migration policy:
- Keep legacy files operational until replacement modules pass contract and regression tests.
- Introduce compatibility shims where needed.
- Archive legacy files only after cutover sign-off.
