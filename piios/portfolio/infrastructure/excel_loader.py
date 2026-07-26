from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from piios.portfolio.application.dto import PortfolioImportResultDTO
from piios.portfolio.domain.entities import PortfolioSnapshot
from piios.portfolio.infrastructure.csv_loader import load_portfolio_snapshot_from_csv


def load_portfolio_snapshot_from_excel(
    file_path: str,
    reporting_currency: str = "USD",
    as_of_utc: datetime | None = None,
    portfolio_id: str = "portfolio-main",
    portfolio_name: str = "Primary Portfolio",
) -> tuple[PortfolioSnapshot | None, PortfolioImportResultDTO]:
    source = Path(file_path)
    df = pd.read_excel(source)
    temp_csv = source.with_suffix(".normalized.tmp.csv")
    try:
        df.columns = [str(col).strip().replace(" ", "_") for col in df.columns]
        df.to_csv(temp_csv, index=False)
        return load_portfolio_snapshot_from_csv(
            file_path=str(temp_csv),
            reporting_currency=reporting_currency,
            as_of_utc=as_of_utc,
            portfolio_id=portfolio_id,
            portfolio_name=portfolio_name,
        )
    finally:
        if temp_csv.exists():
            temp_csv.unlink()
