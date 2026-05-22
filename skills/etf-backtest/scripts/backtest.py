#!/usr/bin/env python3
"""ETF / basket backtest.

For a single ETF or a weighted basket, compute over a configurable date range:
- annualised return, annualised volatility, Sharpe-ish ratio
- max drawdown (depth, peak/trough/recovery dates, duration in calendar days)
- worst rolling 3m / 6m / 12m return (calendar months)
- calendar-year total returns
- per-asset stats (so you can see contribution to portfolio behaviour)

Optionally renders a drawdown curve PNG.

Caveats: total-return, not price-only — uses yfinance auto_adjust=True so distributions
are reinvested. No transaction costs, no taxes, no FX adjustment. Past performance
is not predictive of future returns. The whole point of looking at drawdowns is
to know what *could* happen, not what *will*.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CHART_DIR = SKILL_DIR / "charts"


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
        return x if not (np.isnan(x) or np.isinf(x)) else None
    except (TypeError, ValueError):
        return None


def fetch_prices(tickers: list[str], period: str | None, start: str | None, end: str | None) -> pd.DataFrame:
    """Return adjusted Close prices, one column per ticker, daily."""
    kwargs: dict[str, Any] = {"interval": "1d", "auto_adjust": True, "progress": False}
    if start or end:
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end
    else:
        kwargs["period"] = period or "5y"

    raw = yf.download(tickers, **kwargs)
    # yfinance returns MultiIndex columns when multiple tickers, flat when one
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw["Adj Close"]
    else:
        close = raw[["Close"]].copy()
        close.columns = tickers
    close = close.dropna(how="all")
    return close


def per_asset_stats(prices: pd.Series) -> dict[str, Any]:
    p = prices.dropna()
    if len(p) < 2:
        return {"error": "insufficient data"}
    daily_ret = p.pct_change().dropna()
    n_days = (p.index[-1] - p.index[0]).days
    total = float(p.iloc[-1] / p.iloc[0] - 1)
    ann = (1 + total) ** (365.25 / n_days) - 1 if n_days > 0 and total > -1 else None
    vol = float(daily_ret.std() * (252 ** 0.5))
    sharpe = (ann / vol) if (ann is not None and vol > 0) else None

    cummax = p.cummax()
    dd = (p - cummax) / cummax
    max_dd = float(dd.min())
    trough = dd.idxmin()
    peak_value = cummax[trough]
    prior = p[(p.index <= trough) & (p >= peak_value * 0.99995)]
    peak = prior.index[0] if len(prior) > 0 else None
    recovery_series = p[(p.index > trough) & (p >= peak_value)]
    recovery = recovery_series.index[0] if not recovery_series.empty else None
    rec_days = int((recovery - peak).days) if (recovery is not None and peak is not None) else None

    return {
        "total_return": total,
        "annualised_return": ann,
        "annualised_volatility": vol,
        "sharpe_ish": sharpe,
        "max_drawdown": max_dd,
        "max_drawdown_peak": str(peak.date()) if peak is not None else None,
        "max_drawdown_trough": str(trough.date()),
        "max_drawdown_recovery": str(recovery.date()) if recovery is not None else None,
        "max_drawdown_duration_days": rec_days,
        "n_days": n_days,
        "n_observations": int(len(p)),
        "start_date": str(p.index[0].date()),
        "end_date": str(p.index[-1].date()),
    }


def rolling_worst(prices: pd.Series, months: int) -> dict[str, Any]:
    p = prices.dropna()
    if p.empty:
        return {"return": None, "start": None, "end": None}
    days = int(months * 21)  # ~21 trading days/month
    if len(p) <= days:
        return {"return": None, "start": None, "end": None, "note": "history shorter than window"}
    rolled = p.pct_change(days).dropna()
    if rolled.empty:
        return {"return": None, "start": None, "end": None}
    worst_end = rolled.idxmin()
    worst_val = float(rolled.loc[worst_end])
    worst_start_idx = p.index.get_loc(worst_end) - days
    worst_start = p.index[worst_start_idx] if worst_start_idx >= 0 else p.index[0]
    return {
        "return": worst_val,
        "start": str(worst_start.date()),
        "end": str(worst_end.date()),
    }


def calendar_year_returns(prices: pd.Series) -> dict[str, float]:
    p = prices.dropna()
    if p.empty:
        return {}
    yearly = p.resample("YE").last()
    if len(yearly) < 2:
        return {}
    yearly_first = p.resample("YE").first()
    # year-over-year using year-end vs prior year-end; use first-of-year for the earliest year
    years: dict[str, float] = {}
    sorted_years = sorted(yearly.index.year.unique())
    for y in sorted_years:
        end_val = yearly[yearly.index.year == y].iloc[-1]
        prior_year = y - 1
        prior_end = yearly[yearly.index.year == prior_year]
        if len(prior_end) > 0:
            start_val = prior_end.iloc[-1]
        else:
            start_val = yearly_first[yearly_first.index.year == y].iloc[0]
        years[str(y)] = float(end_val / start_val - 1)
    return years


def portfolio_series(prices: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Build a buy-and-hold (no rebalancing) portfolio series from input weights.

    Requires all named assets to have data on every retained day; drops any row
    where any asset is NaN (e.g. cross-exchange holiday misalignments). The
    effective backtest period starts at the latest first-valid-date across
    components and ends at the earliest last-valid-date.
    """
    total_w = sum(weights.values())
    if total_w <= 0:
        raise ValueError("weights must sum to > 0")
    w = {k: v / total_w for k, v in weights.items()}

    # Keep only days where every requested asset has a price. This handles
    # cross-exchange NaNs (e.g. LSE half-day vs US trading) and asset-launch
    # alignment (basket starts from the latest launch date).
    aligned = prices[list(w.keys())].dropna(how="any")
    if aligned.empty or len(aligned) < 2:
        raise ValueError("no overlapping price data across all assets")

    starts = aligned.iloc[0]
    norm = aligned / starts
    weighted = norm.mul(pd.Series(w), axis=1)
    port = weighted.sum(axis=1)
    return port


def render_drawdown_chart(port: pd.Series, label: str) -> str:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", label)
    out_path = CHART_DIR / f"{safe}_{int(time.time())}_drawdown.png"
    cummax = port.cummax()
    dd = (port - cummax) / cummax * 100
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    ax1.plot(port.index, port.values, color="steelblue", lw=1.4)
    ax1.set_title(f"{label} — equity curve (normalised to 1.0 at start)")
    ax1.set_ylabel("Equity (× starting value)")
    ax1.grid(alpha=0.3)
    ax2.fill_between(dd.index, dd.values, 0, color="crimson", alpha=0.4)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_xlabel("Date")
    ax2.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


def main() -> int:
    p = argparse.ArgumentParser(description="ETF / basket backtest with drawdown + rolling-worst")
    p.add_argument("--tickers", required=True, help="Comma-separated tickers (1+)")
    p.add_argument("--weights", help="Comma-separated weights, same length as tickers (default: equal-weight)")
    p.add_argument("--period", default="5y", help="History period if --start/--end not given (default 5y)")
    p.add_argument("--start", help="Start date YYYY-MM-DD (overrides --period)")
    p.add_argument("--end", help="End date YYYY-MM-DD")
    p.add_argument("--no-chart", action="store_true")
    p.add_argument("--label", help="Label for the output (default: derived from tickers)")
    args = p.parse_args()

    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    if not tickers:
        print(json.dumps({"error": "no tickers"}, indent=2))
        return 1
    if args.weights:
        ws = [float(x) for x in args.weights.split(",") if x.strip()]
        if len(ws) != len(tickers):
            print(json.dumps({"error": "weights length mismatch"}, indent=2))
            return 1
        weights = dict(zip(tickers, ws))
    else:
        weights = {t: 1.0 / len(tickers) for t in tickers}

    try:
        prices = fetch_prices(tickers, args.period, args.start, args.end)
    except Exception as e:
        print(json.dumps({"error": f"price fetch: {e}", "tickers": tickers}, indent=2))
        return 1
    if prices.empty:
        print(json.dumps({"error": "no price data", "tickers": tickers}, indent=2))
        return 1

    # Per-asset stats
    per_asset: dict[str, Any] = {}
    for tk in tickers:
        if tk in prices.columns:
            per_asset[tk] = per_asset_stats(prices[tk])
        else:
            per_asset[tk] = {"error": "missing in price frame"}

    # Portfolio (buy-and-hold, no rebalance)
    if len(tickers) == 1:
        port = prices[tickers[0]].dropna()
        port = port / port.iloc[0]
        portfolio_stats = per_asset_stats(prices[tickers[0]])
    else:
        port = portfolio_series(prices, weights)
        portfolio_stats = per_asset_stats(port)

    rolling = {
        "worst_3m": rolling_worst(port, 3),
        "worst_6m": rolling_worst(port, 6),
        "worst_12m": rolling_worst(port, 12),
    }
    cy_returns = calendar_year_returns(port)

    label = args.label or "+".join(tickers)
    chart_path = None
    if not args.no_chart and len(port) > 10:
        try:
            chart_path = render_drawdown_chart(port, label)
        except Exception as e:
            print(f"warning: chart render failed: {e}", file=sys.stderr)

    out = {
        "metadata": {
            "tickers": tickers,
            "weights": weights,
            "label": label,
            "period": args.period if not (args.start or args.end) else None,
            "start_arg": args.start,
            "end_arg": args.end,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "portfolio": portfolio_stats,
        "rolling_worst": rolling,
        "calendar_year_returns": cy_returns,
        "per_asset": per_asset,
        "chart": chart_path,
        "caveats": (
            "Total-return basis (auto_adjust=True, distributions reinvested). "
            "Buy-and-hold (no rebalancing). No transaction costs, taxes, or FX. "
            "Past performance is not predictive."
        ),
    }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
