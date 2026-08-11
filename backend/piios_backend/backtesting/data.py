from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json

import pandas as pd
import yfinance as yf

from piios_backend.services.recommendation_mvp import _DATA_DIR


@dataclass(frozen=True)
class TickerHistoryMeta:
    ticker: str
    provider: str
    retrieval_timestamp: str
    first_date: str | None
    last_date: str | None
    observation_count: int


@dataclass
class FrozenHistorySnapshot:
    provider: str
    retrieval_timestamp: str
    by_ticker: dict[str, pd.DataFrame]
    metadata: dict[str, TickerHistoryMeta]
    failures: dict[str, str]


def load_india_universe() -> list[str]:
    path = _DATA_DIR / "universe_india.txt"
    if not path.exists():
        raise FileNotFoundError(f"Missing India universe file: {path}")
    out: list[str] = []
    for line in path.read_text().splitlines():
        ticker = line.strip().upper()
        if ticker and not ticker.startswith("#"):
            out.append(ticker)
    return sorted(set(out))


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    if isinstance(frame.index, pd.DatetimeIndex):
        idx = frame.index.tz_localize(None) if frame.index.tz is not None else frame.index
        frame = frame.copy()
        frame.index = idx.normalize()
    keep_cols = [c for c in ["Open", "High", "Low", "Close", "Adj Close", "Volume"] if c in frame.columns]
    return frame[keep_cols].sort_index()


def _extract_ticker_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        if ticker not in raw.columns.get_level_values(0):
            return pd.DataFrame()
        frame = raw[ticker].copy()
    else:
        frame = raw.copy()
    return _normalize_frame(frame.dropna(how="all"))


def freeze_price_history(
    tickers: list[str],
    *,
    start_date: date,
    end_date: date,
    chunk_size: int = 80,
) -> FrozenHistorySnapshot:
    retrieval_timestamp = datetime.now(timezone.utc).isoformat()
    by_ticker: dict[str, pd.DataFrame] = {}
    failures: dict[str, str] = {}

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date + timedelta(days=1))

    for idx in range(0, len(tickers), chunk_size):
        chunk = tickers[idx : idx + chunk_size]
        try:
            raw = yf.download(
                tickers=chunk,
                start=start,
                end=end,
                interval="1d",
                auto_adjust=False,
                progress=False,
                group_by="ticker",
                threads=True,
            )
        except Exception as exc:
            for ticker in chunk:
                failures[ticker] = f"download_error:{exc}"
            continue

        for ticker in chunk:
            frame = _extract_ticker_frame(raw, ticker)
            if frame.empty:
                failures[ticker] = "empty_history"
                continue
            by_ticker[ticker] = frame

    metadata: dict[str, TickerHistoryMeta] = {}
    for ticker in tickers:
        frame = by_ticker.get(ticker)
        if frame is None or frame.empty:
            metadata[ticker] = TickerHistoryMeta(
                ticker=ticker,
                provider="yfinance",
                retrieval_timestamp=retrieval_timestamp,
                first_date=None,
                last_date=None,
                observation_count=0,
            )
            continue
        metadata[ticker] = TickerHistoryMeta(
            ticker=ticker,
            provider="yfinance",
            retrieval_timestamp=retrieval_timestamp,
            first_date=frame.index.min().date().isoformat(),
            last_date=frame.index.max().date().isoformat(),
            observation_count=int(len(frame)),
        )

    return FrozenHistorySnapshot(
        provider="yfinance",
        retrieval_timestamp=retrieval_timestamp,
        by_ticker=by_ticker,
        metadata=metadata,
        failures=failures,
    )


def latest_complete_month_date(calendar: pd.DatetimeIndex, now: date) -> date:
    if len(calendar) == 0:
        raise ValueError("calendar is empty")
    max_day = calendar.max().date()
    if max_day.year == now.year and max_day.month == now.month:
        month_mask = (calendar.year < now.year) | ((calendar.year == now.year) & (calendar.month < now.month))
        prior = calendar[month_mask]
        if len(prior) == 0:
            return max_day
        return prior.max().date()
    return max_day


def monthly_ranking_dates(calendar: pd.DatetimeIndex, start: date, end: date) -> list[date]:
    if len(calendar) == 0:
        return []
    usable = calendar[(calendar.date >= start) & (calendar.date <= end)]
    if len(usable) == 0:
        return []
    month_end = usable.to_series().groupby([usable.year, usable.month]).max().tolist()
    return [ts.date() for ts in month_end]


def save_runtime_csv(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)


def save_runtime_json(payload: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
