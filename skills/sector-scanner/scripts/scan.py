#!/usr/bin/env python3
"""Sector / ETF momentum scanner with news-sentiment overlay.

Scans a universe of ETFs (default: 11 SPDR sector ETFs), computes a composite
"trend score" combining 1m+3m returns, RSI sweet spot, MACD bullishness, trend
confirmation vs SMA-50/SMA-200, ADX strength, and aggregated TextBlob sentiment
across each sector's top constituents. Emits a JSON document with leaders,
laggards, and the full ranked table.

This is DESCRIPTIVE, not predictive. The score reflects current state, not future returns.
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

SPDR_SECTORS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLI": "Industrials",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLC": "Communication Services",
}

# Approximate top-5 holdings per SPDR sector (drifts slowly; refresh annually).
SECTOR_CONSTITUENTS = {
    "XLK": ["AAPL", "MSFT", "NVDA", "AVGO", "ORCL"],
    "XLF": ["JPM", "BAC", "BRK-B", "WFC", "GS"],
    "XLE": ["XOM", "CVX", "COP", "EOG", "SLB"],
    "XLV": ["LLY", "UNH", "JNJ", "MRK", "ABBV"],
    "XLI": ["GE", "RTX", "CAT", "UNP", "HON"],
    "XLP": ["COST", "WMT", "PG", "KO", "PEP"],
    "XLY": ["AMZN", "TSLA", "HD", "MCD", "LOW"],
    "XLU": ["NEE", "DUK", "SO", "AEP", "CEG"],
    "XLB": ["LIN", "SHW", "FCX", "ECL", "APD"],
    "XLRE": ["PLD", "AMT", "EQIX", "WELL", "SPG"],
    "XLC": ["META", "GOOGL", "GOOG", "NFLX", "TMUS"],
}

THEMATIC_ETFS = {
    "IBIT": "iShares Bitcoin Trust",
    "ARKK": "ARK Innovation",
    "TAN": "Solar",
    "ICLN": "Clean Energy",
    "LIT": "Lithium & Battery",
    "SOXX": "Semiconductors",
    "XBI": "Biotech",
    "KWEB": "China Internet",
    "URA": "Uranium",
    "JETS": "Airlines",
    "HACK": "Cybersecurity",
    "GDX": "Gold Miners",
}


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    g = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    l = -d.clip(upper=0).ewm(alpha=1 / n, adjust=False).mean()
    rs = g / l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = _ema(s, fast) - _ema(s, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def _atr(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    p = c.shift(1)
    tr = pd.concat([(h - l), (h - p).abs(), (l - p).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _adx(h: pd.Series, l: pd.Series, c: pd.Series, n: int = 14) -> pd.Series:
    up = h.diff()
    dn = -l.diff()
    plus_dm = up.where((up > dn) & (up > 0), 0.0)
    minus_dm = dn.where((dn > up) & (dn > 0), 0.0)
    atr_v = _atr(h, l, c, n)
    plus_di = 100 * (plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_v)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_v)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def _f(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return f if not (np.isnan(f) or np.isinf(f)) else None
    except (TypeError, ValueError):
        return None


def fetch_metrics(ticker: str) -> dict[str, Any]:
    try:
        # 1y so SMA-200 has enough data (~252 trading days); 6mo is too short.
        df = yf.Ticker(ticker).history(period="1y", interval="1d", auto_adjust=False)
    except Exception as e:
        return {"ticker": ticker, "error": f"history fetch: {e}"}
    if df.empty:
        return {"ticker": ticker, "error": "no historical data"}
    df.columns = [c.lower() for c in df.columns]
    close, high, low = df["close"], df["high"], df["low"]
    last = float(close.iloc[-1])

    def pct_return(n: int) -> float | None:
        if len(close) <= n:
            return None
        return float(close.iloc[-1] / close.iloc[-n] - 1)

    rsi_v = _f(_rsi(close).iloc[-1])
    macd_l, macd_s, macd_h = _macd(close)
    sma_50 = _f(_sma(close, 50).iloc[-1])
    sma_200 = _f(_sma(close, 200).iloc[-1]) if len(close) >= 200 else None
    return {
        "ticker": ticker,
        "last": last,
        "return_1m": pct_return(21),
        "return_3m": pct_return(63),
        "rsi_14": rsi_v,
        "macd_hist": _f(macd_h.iloc[-1]),
        "macd_above_signal": (
            bool(macd_l.iloc[-1] > macd_s.iloc[-1])
            if pd.notna(macd_l.iloc[-1]) and pd.notna(macd_s.iloc[-1])
            else None
        ),
        "above_sma_50": (last > sma_50) if sma_50 is not None else None,
        "above_sma_200": (last > sma_200) if sma_200 is not None else None,
        "adx_14": _f(_adx(high, low, close).iloc[-1]),
    }


def fetch_sentiment(tickers: list[str]) -> dict[str, Any]:
    try:
        from textblob import TextBlob
    except ImportError:
        return {"polarity": None, "n_headlines": 0}
    pols: list[float] = []
    for t in tickers:
        try:
            news = getattr(yf.Ticker(t), "news", []) or []
        except Exception:
            continue
        for item in news[:5]:
            content = item.get("content") if isinstance(item, dict) else None
            title = (
                (content.get("title") if isinstance(content, dict) else None)
                or item.get("title")
                or ""
            )
            if title:
                pols.append(float(TextBlob(title).sentiment.polarity))
    return {
        "polarity": float(sum(pols) / len(pols)) if pols else None,
        "n_headlines": len(pols),
    }


def composite_score(
    m: dict[str, Any],
    sentiment: dict[str, Any],
    universe_returns_1m: list[float],
) -> tuple[float, dict[str, float]]:
    """Return (composite_score in 0..1, per-component sub-scores)."""
    parts: list[tuple[str, float, float]] = []  # (name, score 0-1, weight)

    r1m = m.get("return_1m")
    if r1m is not None and universe_returns_1m:
        below = sum(1 for x in universe_returns_1m if x < r1m)
        # +1 because the ticker itself is in the universe
        pct = below / max(len(universe_returns_1m), 1)
        parts.append(("return_pct_rank", pct, 0.30))

    rsi = m.get("rsi_14")
    if rsi is not None:
        rsi_score = max(0.0, 1.0 - abs(rsi - 60.0) / 40.0)
        parts.append(("rsi_sweetspot", rsi_score, 0.10))

    mh, mas = m.get("macd_hist"), m.get("macd_above_signal")
    if mh is not None and mas is not None:
        macd_s = 0.5 * (1.0 if mh > 0 else 0.0) + 0.5 * (1.0 if mas else 0.0)
        parts.append(("macd_bullish", macd_s, 0.15))

    a50, a200 = m.get("above_sma_50"), m.get("above_sma_200")
    if a50 is not None and a200 is not None:
        sma_s = 0.5 * (1.0 if a50 else 0.0) + 0.5 * (1.0 if a200 else 0.0)
        parts.append(("trend_confirm", sma_s, 0.15))
    elif a50 is not None:
        parts.append(("trend_confirm", 1.0 if a50 else 0.0, 0.15))

    adx_v = m.get("adx_14")
    if adx_v is not None:
        parts.append(("adx_strength", min(adx_v / 50.0, 1.0), 0.10))

    pol = sentiment.get("polarity")
    if pol is not None:
        parts.append(("sentiment", max(0.0, min(1.0, 0.5 + 0.5 * pol)), 0.20))

    if not parts:
        return 0.0, {}
    total_w = sum(w for _, _, w in parts)
    composite = sum(s * w for _, s, w in parts) / total_w
    return composite, {name: round(s, 4) for name, s, _ in parts}


def main() -> int:
    p = argparse.ArgumentParser(description="Sector/ETF momentum scanner with sentiment overlay")
    p.add_argument("--universe", help="Comma-separated tickers; overrides defaults")
    p.add_argument("--include-thematic", action="store_true", help="Add 12 thematic ETFs to default SPDR set")
    p.add_argument("--no-sentiment", action="store_true", help="Skip news sentiment (much faster)")
    p.add_argument("--top", type=int, default=3, help="Leaders/laggards count")
    args = p.parse_args()

    if args.universe:
        universe = [t.strip().upper() for t in args.universe.split(",") if t.strip()]
        names = {t: t for t in universe}
        constituents = {t: [t] for t in universe}
    else:
        universe = list(SPDR_SECTORS.keys())
        names = dict(SPDR_SECTORS)
        constituents = {k: list(v) for k, v in SECTOR_CONSTITUENTS.items()}
        if args.include_thematic:
            universe += list(THEMATIC_ETFS.keys())
            names.update(THEMATIC_ETFS)
            for t in THEMATIC_ETFS:
                constituents[t] = [t]

    print(f"Scanning {len(universe)} tickers (sentiment={not args.no_sentiment})...", file=sys.stderr)

    metrics: dict[str, dict[str, Any]] = {}
    for t in universe:
        metrics[t] = fetch_metrics(t)

    sentiments: dict[str, dict[str, Any]] = {}
    if args.no_sentiment:
        for t in universe:
            sentiments[t] = {"polarity": None, "n_headlines": 0}
    else:
        for t in universe:
            basket = list(dict.fromkeys([t] + constituents.get(t, [])))
            sentiments[t] = fetch_sentiment(basket)

    universe_r1m = [
        m["return_1m"] for m in metrics.values()
        if "error" not in m and m.get("return_1m") is not None
    ]

    rows: list[dict[str, Any]] = []
    for t in universe:
        m = metrics[t]
        if "error" in m:
            rows.append({"ticker": t, "name": names.get(t, t), "error": m["error"]})
            continue
        s = sentiments.get(t, {})
        composite, sub_scores = composite_score(m, s, universe_r1m)
        rows.append({
            "ticker": t,
            "name": names.get(t, t),
            "composite_score": round(composite, 4),
            "sub_scores": sub_scores,
            "components": {
                "return_1m": m.get("return_1m"),
                "return_3m": m.get("return_3m"),
                "rsi_14": m.get("rsi_14"),
                "macd_hist": m.get("macd_hist"),
                "macd_above_signal": m.get("macd_above_signal"),
                "above_sma_50": m.get("above_sma_50"),
                "above_sma_200": m.get("above_sma_200"),
                "adx_14": m.get("adx_14"),
                "sentiment_polarity": s.get("polarity"),
                "sentiment_n_headlines": s.get("n_headlines"),
            },
        })

    ranked = sorted(
        [r for r in rows if "error" not in r],
        key=lambda r: r["composite_score"],
        reverse=True,
    )
    errors = [r for r in rows if "error" in r]
    leaders = [dict(r, signal="leader") for r in ranked[: args.top]]
    laggards_src = ranked[-args.top:] if len(ranked) > args.top else []
    laggards = [dict(r, signal="laggard") for r in reversed(laggards_src)]

    out = {
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "universe": universe,
            "sentiment_included": not args.no_sentiment,
            "n_scanned": len(universe),
            "n_errors": len(errors),
            "weights": {
                "return_pct_rank": 0.30,
                "rsi_sweetspot": 0.10,
                "macd_bullish": 0.15,
                "trend_confirm": 0.15,
                "adx_strength": 0.10,
                "sentiment": 0.20,
            },
            "framing": "DESCRIPTIVE. Composite score reflects current trend strength, not a forecast.",
        },
        "leaders": leaders,
        "laggards": laggards,
        "ranked": ranked,
        "errors": errors,
    }
    print(json.dumps(out, indent=2, default=str))
    return 0 if ranked else 1


if __name__ == "__main__":
    sys.exit(main())
