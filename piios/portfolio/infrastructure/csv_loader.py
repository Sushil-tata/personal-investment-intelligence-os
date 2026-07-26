from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from piios.portfolio.application.dto import DataIssueDTO, HoldingDTO, PortfolioImportResultDTO, PortfolioSnapshotDTO
from piios.portfolio.domain.entities import Account, CashBalance, DataQualityIssue, Holding, Portfolio, PortfolioSnapshot, Security
from piios.portfolio.domain.enums import DataIssueSeverity, PortfolioBucket
from piios.portfolio.domain.exceptions import ValidationError
from piios.portfolio.domain.value_objects import CostBasis, Currency, Money, Price, Quantity, SecurityIdentifier


MANDATORY_COLUMNS = {
    "holding_id",
    "ticker",
    "name",
    "quantity",
    "price",
    "trading_currency",
    "account_id",
    "bucket",
    "asset_class",
    "listing_country",
    "economic_country",
}


def _normalize_column_name(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _parse_bucket(raw: str) -> PortfolioBucket:
    mapping = {item.value.lower(): item for item in PortfolioBucket}
    key = raw.strip().lower()
    if key not in mapping:
        raise ValidationError(f"Unknown bucket: {raw}")
    return mapping[key]


def _issue(severity: DataIssueSeverity, code: str, message: str, row_number: int | None = None, field_name: str | None = None) -> DataQualityIssue:
    return DataQualityIssue(severity=severity, code=code, message=message, row_number=row_number, field_name=field_name)


def _to_snapshot_dto(snapshot: PortfolioSnapshot) -> PortfolioSnapshotDTO:
    holdings = []
    for h in snapshot.portfolio.holdings:
        holdings.append(
            HoldingDTO(
                holding_id=h.holding_id,
                ticker=h.security.identifier.ticker,
                name=h.security.name,
                account_id=h.account_id,
                bucket=h.bucket.value,
                quantity=h.quantity.value,
                price=h.price.amount,
                trading_currency=h.security.trading_currency.code,
                asset_class=h.security.asset_class,
                listing_country=h.security.listing_country,
                economic_country=h.security.economic_country,
                sector=h.security.sector,
                industry=h.security.industry,
                theme=h.security.theme,
            )
        )
    cash_balances = [
        {"account_id": c.account_id, "currency": c.balance.currency.code, "amount": c.balance.amount}
        for c in snapshot.portfolio.cash_balances
    ]
    return PortfolioSnapshotDTO(
        snapshot_id=snapshot.snapshot_id,
        portfolio_id=snapshot.portfolio.portfolio_id,
        portfolio_name=snapshot.portfolio.name,
        reporting_currency=snapshot.portfolio.reporting_currency.code,
        as_of_utc=snapshot.as_of_utc,
        source_filename=snapshot.source_filename,
        holdings=holdings,
        cash_balances=cash_balances,
    )


def load_portfolio_snapshot_from_csv(
    file_path: str,
    reporting_currency: str = "USD",
    as_of_utc: datetime | None = None,
    portfolio_id: str = "portfolio-main",
    portfolio_name: str = "Primary Portfolio",
) -> tuple[PortfolioSnapshot | None, PortfolioImportResultDTO]:
    source = Path(file_path)
    issues: list[DataQualityIssue] = []

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            issues.append(_issue(DataIssueSeverity.ERROR, "MISSING_HEADER", "CSV file has no header row"))
            dto = PortfolioImportResultDTO(snapshot=None, issues=[DataIssueDTO(**i.__dict__) for i in issues])
            return None, dto

        normalized_headers = [_normalize_column_name(col) for col in reader.fieldnames]
        if len(set(normalized_headers)) != len(normalized_headers):
            issues.append(_issue(DataIssueSeverity.ERROR, "DUPLICATE_COLUMNS", "CSV contains duplicate normalized column names"))

        missing_columns = sorted(MANDATORY_COLUMNS - set(normalized_headers))
        if missing_columns:
            issues.append(
                _issue(
                    DataIssueSeverity.ERROR,
                    "MISSING_MANDATORY_COLUMNS",
                    f"Missing mandatory columns: {', '.join(missing_columns)}",
                )
            )
            dto = PortfolioImportResultDTO(snapshot=None, issues=[DataIssueDTO(**i.__dict__) for i in issues])
            return None, dto

        column_map = {orig: _normalize_column_name(orig) for orig in reader.fieldnames}
        holdings: list[Holding] = []
        accounts: dict[str, Account] = {}

        for idx, raw_row in enumerate(reader, start=2):
            row = {column_map[k]: (v or "").strip() for k, v in raw_row.items()}
            try:
                quantity = Quantity.from_value(row["quantity"])
                if quantity.value < Decimal("0"):
                    raise ValidationError("Quantity cannot be negative")
                price = Price.from_value(row["price"], row["trading_currency"])
                bucket = _parse_bucket(row["bucket"])
            except Exception as exc:
                issues.append(_issue(DataIssueSeverity.ERROR, "INVALID_ROW", str(exc), row_number=idx))
                continue

            missing_optional = []
            for optional_field in ("sector", "industry", "theme"):
                if not row.get(optional_field):
                    missing_optional.append(optional_field)
            for field_name in missing_optional:
                issues.append(
                    _issue(
                        DataIssueSeverity.WARNING,
                        "MISSING_CLASSIFICATION",
                        f"Missing {field_name} for holding {row.get('holding_id') or row.get('ticker')}",
                        row_number=idx,
                        field_name=field_name,
                    )
                )

            if not row.get("economic_country"):
                issues.append(
                    _issue(
                        DataIssueSeverity.WARNING,
                        "MISSING_ECONOMIC_COUNTRY",
                        f"Missing economic_country for holding {row.get('ticker')}",
                        row_number=idx,
                        field_name="economic_country",
                    )
                )

            security = Security(
                identifier=SecurityIdentifier(ticker=row["ticker"], exchange=row.get("exchange") or None),
                name=row["name"],
                asset_class=row["asset_class"],
                trading_currency=Currency(row["trading_currency"]),
                listing_country=row["listing_country"],
                economic_country=row["economic_country"],
                sector=row.get("sector") or None,
                industry=row.get("industry") or None,
                theme=row.get("theme") or None,
                is_listed_equity=(row.get("is_listed_equity", "true").lower() in {"true", "1", "yes", "y"}),
                is_liquid=(row.get("is_liquid", "true").lower() in {"true", "1", "yes", "y"}),
            )

            holding = Holding(
                holding_id=row["holding_id"],
                account_id=row["account_id"],
                bucket=bucket,
                security=security,
                quantity=quantity,
                price=price,
                cost_basis=CostBasis(unit_cost=Money.from_value(row.get("cost_basis", row["price"]), row["trading_currency"])),
                raw_source=row,
            )
            holdings.append(holding)

            if row["account_id"] not in accounts:
                accounts[row["account_id"]] = Account(
                    account_id=row["account_id"],
                    account_name=row.get("account_name") or row["account_id"],
                    base_currency=Currency(row.get("account_currency") or reporting_currency),
                )

        if not holdings and any(i.severity == DataIssueSeverity.ERROR for i in issues):
            dto = PortfolioImportResultDTO(snapshot=None, issues=[DataIssueDTO(**i.__dict__) for i in issues])
            return None, dto

        snapshot_time = as_of_utc or datetime.now(timezone.utc)
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            name=portfolio_name,
            reporting_currency=Currency(reporting_currency),
            accounts=list(accounts.values()),
            holdings=holdings,
            cash_balances=[
                CashBalance(account_id=acc.account_id, balance=Money.from_value(0, reporting_currency))
                for acc in accounts.values()
            ],
        )
        snapshot = PortfolioSnapshot(
            snapshot_id=f"snap-{snapshot_time.strftime('%Y%m%d%H%M%S')}",
            portfolio=portfolio,
            as_of_utc=snapshot_time,
            source_filename=source.name,
        )

        dto = PortfolioImportResultDTO(snapshot=_to_snapshot_dto(snapshot), issues=[DataIssueDTO(**i.__dict__) for i in issues])
        return snapshot, dto
