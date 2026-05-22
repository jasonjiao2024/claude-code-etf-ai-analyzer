#!/usr/bin/env python3
"""ETF deep-dive analyzer.

Pulls ETF-specific metadata via yfinance: fund family, AUM, top-N holdings,
sector + asset-class breakdown, aggregate fund-level valuation (P/E, P/B),
dividend yield + distribution frequency, and performance metrics including
max drawdown over the available history.

Limitation: yfinance does not expose expense ratio (TER). Look it up on the
provider's fund page (iShares / Invesco / Vanguard / WisdomTree / etc.).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


def _parse_unix_date(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc).date().isoformat()
        except Exception:
            return None
    return str(v)


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
        return x if not (np.isnan(x) or np.isinf(x)) else None
    except (TypeError, ValueError):
        return None


def _infer_domicile(fund_family: str | None) -> str | None:
    if not fund_family:
        return None
    f = fund_family.lower()
    if "ireland" in f:
        return "Ireland"
    if "luxembourg" in f:
        return "Luxembourg"
    if "united states" in f or "u.s." in f:
        return "United States"
    return None


def fetch_basic_info(t: yf.Ticker) -> dict[str, Any]:
    try:
        info = t.info or {}
    except Exception:
        info = {}
    name = info.get("longName") or info.get("shortName")
    fund_family = info.get("fundFamily")
    return {
        "name": name,
        "short_name": info.get("shortName"),
        "isin": info.get("isin"),
        "fund_family": fund_family,
        "domicile_guess": _infer_domicile(fund_family),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "category": info.get("category"),
        "inception_date": _parse_unix_date(info.get("fundInceptionDate")),
        "legal_type": info.get("legalType"),
        "quote_type": info.get("quoteType"),
        "ucits": ("UCITS" in name.upper()) if name else None,
        "aum": info.get("totalAssets"),
        "trailing_annual_dividend_yield": _f(info.get("trailingAnnualDividendYield")),
        "trailing_annual_dividend_rate": _f(info.get("trailingAnnualDividendRate")),
        "ytd_return_info": _f(info.get("ytdReturn")),
        "three_year_avg_return": _f(info.get("threeYearAverageReturn")),
        "five_year_avg_return": _f(info.get("fiveYearAverageReturn")),
    }


def fetch_funds_data(t: yf.Ticker, max_holdings: int) -> dict[str, Any]:
    out: dict[str, Any] = {
        "fund_overview": None,
        "top_holdings": [],
        "n_holdings_visible": 0,
        "top_n_concentration": None,
        "sectors": [],
        "asset_classes": {},
        "equity_aggregate": {},
    }
    try:
        fd = t.funds_data
    except Exception:
        return out

    try:
        ov = fd.fund_overview
        if isinstance(ov, dict):
            out["fund_overview"] = {
                "category": ov.get("categoryName") or ov.get("category"),
                "family": ov.get("family"),
                "legal_type": ov.get("legalType"),
            }
    except Exception:
        pass

    try:
        th = fd.top_holdings
        if th is not None and not th.empty:
            cols = list(th.columns)
            weight_col = next((c for c in cols if "percent" in c.lower() or c.lower() == "weight"), None)
            name_col = next((c for c in cols if c.lower() in ("name", "holding name")), None)
            holdings: list[dict[str, Any]] = []
            for sym, row in th.iterrows():
                w = _f(row[weight_col]) if weight_col else None
                holdings.append({
                    "symbol": str(sym),
                    "name": row[name_col] if name_col else None,
                    "weight": w,
                })
            out["top_holdings"] = holdings[:max_holdings]
            out["n_holdings_visible"] = len(holdings)
            weights = [h["weight"] for h in holdings[:max_holdings] if h["weight"] is not None]
            out["top_n_concentration"] = sum(weights) if weights else None
    except Exception as e:
        print(f"warning: top_holdings parse failed: {e}", file=sys.stderr)

    try:
        sw = fd.sector_weightings
        if isinstance(sw, dict):
            out["sectors"] = sorted(
                [{"sector": k, "weight": _f(v)} for k, v in sw.items() if _f(v) is not None],
                key=lambda r: r["weight"] or 0,
                reverse=True,
            )
    except Exception:
        pass

    try:
        ac = fd.asset_classes
        if isinstance(ac, dict):
            out["asset_classes"] = {k: _f(v) for k, v in ac.items() if _f(v) is not None}
    except Exception:
        pass

    try:
        eh = fd.equity_holdings
        if eh is not None and not eh.empty:
            agg: dict[str, Any] = {}
            for row_label, row in eh.iterrows():
                col = next(iter(eh.columns), None)
                if col is None:
                    continue
                v = _f(row[col])
                if v is not None:
                    key = str(row_label).lower().replace("/", "_").replace(" ", "_")
                    agg[key] = v
            out["equity_aggregate"] = agg
    except Exception:
        pass

    return out


def compute_dividend_info(t: yf.Ticker, info_block: dict[str, Any]) -> dict[str, Any]:
    out = {
        "yield": info_block.get("trailing_annual_dividend_yield"),
        "annual_rate": info_block.get("trailing_annual_dividend_rate"),
        "ttm_sum": None,
        "n_distributions_ttm": 0,
        "frequency": None,
        "is_accumulating": None,
    }
    try:
        divs = t.dividends
    except Exception:
        divs = None
    if divs is None or len(divs) == 0:
        out["frequency"] = "accumulating (no distributions observed)"
        out["is_accumulating"] = True
        out["ttm_sum"] = 0.0
        return out

    out["is_accumulating"] = False
    tz = divs.index.tz
    cutoff = pd.Timestamp.now(tz=tz) - pd.Timedelta(days=365)
    ttm = divs[divs.index >= cutoff]
    n = int(len(ttm))
    out["ttm_sum"] = float(ttm.sum()) if n else 0.0
    out["n_distributions_ttm"] = n
    out["frequency"] = (
        "none" if n == 0
        else "annual" if n == 1
        else "semi-annual" if n in (2, 3)
        else "quarterly" if n in (4, 5)
        else "monthly"
    )
    return out


def compute_performance(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {}
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    close = df["close"]
    n = len(close)

    def back_n(k: int) -> float | None:
        return float(close.iloc[-1] / close.iloc[-k] - 1) if n > k else None

    last_idx = close.index[-1]
    tz = last_idx.tz
    year_start = pd.Timestamp(year=last_idx.year, month=1, day=1, tz=tz)
    ytd_data = close[close.index >= year_start]
    ytd = float(ytd_data.iloc[-1] / ytd_data.iloc[0] - 1) if len(ytd_data) > 1 else None

    cummax = close.cummax()
    drawdown = (close - cummax) / cummax
    max_dd = float(drawdown.min()) if not drawdown.empty else None
    peak_date = trough_date = recovery_date = None
    recovery_days = None
    if max_dd is not None and max_dd < 0:
        trough_date = drawdown.idxmin()
        peak_value = cummax[trough_date]
        prior = close[(close.index <= trough_date) & (close >= peak_value * 0.99995)]
        if len(prior) > 0:
            peak_date = prior.index[0]
        recovery = close[(close.index > trough_date) & (close >= peak_value)]
        if not recovery.empty:
            recovery_date = recovery.index[0]
            if peak_date is not None:
                recovery_days = int((recovery_date - peak_date).days)

    n_days = (close.index[-1] - close.index[0]).days if n > 1 else 0
    total_ret = float(close.iloc[-1] / close.iloc[0] - 1) if n > 1 else None
    annualised = (
        (1 + total_ret) ** (365.25 / n_days) - 1
        if n_days > 0 and total_ret is not None and total_ret > -1
        else None
    )

    daily_ret = close.pct_change().dropna()
    vol_ann = float(daily_ret.std() * (252 ** 0.5)) if len(daily_ret) > 1 else None
    sharpe = (annualised / vol_ann) if (annualised is not None and vol_ann and vol_ann > 0) else None

    return {
        "price": float(close.iloc[-1]),
        "return_1m": back_n(21),
        "return_3m": back_n(63),
        "return_6m": back_n(126),
        "return_ytd": ytd,
        "return_1y": back_n(252),
        "total_return_over_history": total_ret,
        "annualised_return": annualised,
        "annualised_volatility": vol_ann,
        "sharpe_ish": sharpe,
        "max_drawdown": max_dd,
        "max_drawdown_peak_date": str(peak_date.date()) if peak_date is not None else None,
        "max_drawdown_trough_date": str(trough_date.date()) if trough_date is not None else None,
        "max_drawdown_recovery_date": str(recovery_date.date()) if recovery_date is not None else None,
        "max_drawdown_recovery_days": recovery_days,
        "history_start": str(close.index[0].date()),
        "history_end": str(close.index[-1].date()),
        "history_n_days": n_days,
        "history_n_rows": n,
    }


def fetch_holdings_dict(t: yf.Ticker) -> dict[str, dict[str, Any]]:
    """Return {symbol: {'name': str, 'weight': float}} from .funds_data.top_holdings."""
    out: dict[str, dict[str, Any]] = {}
    try:
        fd = t.funds_data
        th = fd.top_holdings
    except Exception:
        return out
    if th is None or th.empty:
        return out
    weight_col = next((c for c in th.columns if "percent" in c.lower() or c.lower() == "weight"), None)
    name_col = next((c for c in th.columns if c.lower() in ("name", "holding name")), None)
    for sym, row in th.iterrows():
        w = _f(row[weight_col]) if weight_col else None
        if w is None:
            continue
        out[str(sym)] = {
            "name": row[name_col] if name_col else None,
            "weight": w,
        }
    return out


def do_compare(tickers: list[str]) -> dict[str, Any]:
    """Compute pairwise holdings overlap (Jaccard + weight-aware) across N tickers."""
    holdings: dict[str, dict[str, dict[str, Any]]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for tk in tickers:
        t = yf.Ticker(tk)
        h = fetch_holdings_dict(t)
        holdings[tk] = h
        try:
            info = t.info or {}
        except Exception:
            info = {}
        metadata[tk] = {
            "name": info.get("longName") or info.get("shortName") or tk,
            "currency": info.get("currency"),
            "aum": info.get("totalAssets"),
            "n_visible_holdings": len(h),
            "visible_weight_sum": round(sum(d["weight"] for d in h.values()), 4) if h else 0.0,
        }
        if not h:
            metadata[tk]["error"] = "no holdings returned by yfinance"

    pairs: list[dict[str, Any]] = []
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            ha, hb = holdings[a], holdings[b]
            sa, sb = set(ha), set(hb)
            inter, union = sa & sb, sa | sb
            jaccard = len(inter) / len(union) if union else 0.0
            weighted_overlap = sum(min(ha[s]["weight"], hb[s]["weight"]) for s in inter)
            a_weight_in_shared = sum(ha[s]["weight"] for s in inter)
            b_weight_in_shared = sum(hb[s]["weight"] for s in inter)
            shared_details = sorted(
                [
                    {
                        "symbol": s,
                        "name": ha[s].get("name") or hb[s].get("name"),
                        "weight_a": round(ha[s]["weight"], 4),
                        "weight_b": round(hb[s]["weight"], 4),
                    }
                    for s in inter
                ],
                key=lambda r: r["weight_a"] + r["weight_b"],
                reverse=True,
            )
            pairs.append({
                "a": a, "b": b,
                "n_shared": len(inter),
                "n_union": len(union),
                "jaccard": round(jaccard, 4),
                "weighted_overlap": round(weighted_overlap, 4),
                "a_top_weight_in_shared": round(a_weight_in_shared, 4),
                "b_top_weight_in_shared": round(b_weight_in_shared, 4),
                "shared_holdings": shared_details,
            })

    # Holdings unique to each ETF (vs union of all others' visible holdings)
    unique_by_ticker: dict[str, list[str]] = {}
    for tk in tickers:
        others = set().union(*[set(holdings[o]) for o in tickers if o != tk])
        unique_by_ticker[tk] = sorted(set(holdings[tk]) - others)

    return {
        "mode": "compare",
        "tickers": tickers,
        "metadata": metadata,
        "pairs": pairs,
        "unique_to_each": unique_by_ticker,
        "interpretation_note": (
            "Jaccard = |A∩B| / |A∪B|, ignores weights. "
            "weighted_overlap = sum_over_shared(min(w_a, w_b)) — measures actual portfolio overlap by capital. "
            "a_top_weight_in_shared = how much of A's top-N weight is in shared names. "
            "yfinance only exposes top ~10 holdings per ETF, so this analysis is a top-of-book proxy, not the full portfolio overlap."
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="ETF deep-dive analyzer")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ticker", help="Single-ETF deep dive")
    mode.add_argument("--compare", help="Comma-separated tickers (2+) for holdings-overlap analysis")
    p.add_argument("--period", default="max", help="History period for --ticker mode (default: max)")
    p.add_argument("--max-holdings", type=int, default=10)
    args = p.parse_args()

    if args.compare:
        tickers = [t.strip().upper() for t in args.compare.split(",") if t.strip()]
        if len(tickers) < 2:
            print(json.dumps({"error": "--compare requires 2+ comma-separated tickers"}, indent=2))
            return 1
        print(json.dumps(do_compare(tickers), indent=2, default=str))
        return 0

    ticker = args.ticker.upper()
    t = yf.Ticker(ticker)

    try:
        df = t.history(period=args.period, interval="1d", auto_adjust=False)
    except Exception as e:
        print(json.dumps({"error": f"history fetch: {e}", "ticker": ticker}, indent=2))
        return 1
    if df.empty:
        print(json.dumps({
            "error": "no historical data",
            "ticker": ticker,
            "hint": "Check ticker; UCITS ETFs often need .L/.MI/.DE/.AS suffix.",
        }, indent=2))
        return 1

    basic = fetch_basic_info(t)
    funds = fetch_funds_data(t, args.max_holdings)
    dist = compute_dividend_info(t, basic)
    perf = compute_performance(df)

    out = {
        "metadata": {
            "ticker": ticker,
            "name": basic.get("name"),
            "short_name": basic.get("short_name"),
            "isin": basic.get("isin"),
            "fund_family": basic.get("fund_family"),
            "domicile_guess": basic.get("domicile_guess"),
            "ucits": basic.get("ucits"),
            "legal_type": basic.get("legal_type"),
            "exchange": basic.get("exchange"),
            "currency": basic.get("currency"),
            "category": basic.get("category"),
            "inception_date": basic.get("inception_date"),
            "quote_type": basic.get("quote_type"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "size_and_cost": {
            "aum": basic.get("aum"),
            "expense_ratio": None,
            "expense_ratio_note": "Not available via yfinance. Check the provider fund page (iShares / Invesco / Vanguard / WisdomTree).",
        },
        "distribution": dist,
        "asset_classes": funds["asset_classes"],
        "holdings": {
            "top_n": funds["top_holdings"],
            "n_holdings_visible": funds["n_holdings_visible"],
            "top_n_concentration": funds["top_n_concentration"],
        },
        "sectors": funds["sectors"],
        "equity_aggregate": funds["equity_aggregate"],
        "performance": perf,
        "fund_overview": funds.get("fund_overview"),
    }

    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
