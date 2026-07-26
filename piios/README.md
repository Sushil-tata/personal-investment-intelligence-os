# PIIOS v2 Scaffold

This folder is a non-disruptive target architecture scaffold.

- Existing runtime remains in `backend/` and `dashboard/`.
- Migration planning artifacts are in `piios/knowledge/`.
- Legacy references are indexed in `piios/legacy/`.

Target module layout:
- `legacy/`
- `backend/`
- `frontend/`
- `agents/`
- `analytics/`
- `database/`
- `ingestion/`
- `tests/`
- `docs/`

Do not move/delete legacy files until module parity tests pass.
