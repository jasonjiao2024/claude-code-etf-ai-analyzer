#!/usr/bin/env python3
"""Stock analyzer backend — yfinance data + technical indicators + sentiment + candlestick chart.

Emits a single JSON document to stdout matching the contract in SKILL.md.
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

import numpy as np
import pandas as pd
import yfinance as yf

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CACHE_DIR = SKILL_DIR / "cache"
CHART_DIR = SKILL_DIR / "charts"
CACHE_TTL_SEC = 15 * 60


def detect_market(ticker: str) -> tuple[str, str, str]:
    t = ticker.upper()
    if t.endswith(".HK"):
        return "Hong Kong", "hk", "HKD"
    if t.endswith(".SS"):
        return "Shanghai", "cn", "CNY"
    if t.endswith(".SZ"):
        return "Shenzhen", "cn", "CNY"
    if t.endswith(".T"):
        return "Tokyo", "jp", "JPY"
    if t.endswith(".L"):
        return "London", "uk", "GBP"
    return "United States", "us", "USD"


def cache_path(ticker: str, period: str, interval: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", f"{ticker}_{period}_{interval}.json")
    return CACHE_DIR / safe


def load_cache(p: Path) -> dict[str, Any] | None:
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > CACHE_TTL_SEC:
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def save_cache(p: Path, data: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, default=str))


def fetch_history(ticker: str, period: str, interval: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
    if df.empty:
        raise ValueError(f"no historical data for {ticker} (period={period}, interval={interval})")
    df.columns = [c.lower() for c in df.columns]
    return df


def fetch_quote(ticker: str) -> dict[str, Any]:
    t = yf.Ticker(ticker)
    info: dict[str, Any] = {}
    try:
        info = t.info or {}
    except Exception:
        pass
    fast = getattr(t, "fast_info", None)

    def fast_attr(name: str) -> Any:
        if fast is None:
            return None
        try:
            return getattr(fast, name, None)
        except Exception:
            return None

    return {
        "name": info.get("longName") or info.get("shortName"),
        "current": info.get("regularMarketPrice") or fast_attr("last_price"),
        "previous_close": info.get("regularMarketPreviousClose") or fast_attr("previous_close"),
        "open": info.get("regularMarketOpen") or fast_attr("open"),
        "high": info.get("regularMarketDayHigh") or fast_attr("day_high"),
        "low": info.get("regularMarketDayLow") or fast_attr("day_low"),
        "volume": info.get("regularMarketVolume") or fast_attr("last_volume"),
        "market_cap": info.get("marketCap") or fast_attr("market_cap"),
        "pe_ratio": info.get("trailingPE"),
        "revenue": info.get("totalRevenue"),
        "net_income": info.get("netIncomeToCommon"),
        "currency": info.get("currency") or fast_attr("currency"),
    }


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _macd(s: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    line = _ema(s, fast) - _ema(s, slow)
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig, line - sig


def _bollinger(s: pd.Series, n: int = 20, k: float = 2.0):
    mid = _sma(s, n)
    sd = s.rolling(n).std()
    return mid + k * sd, mid, mid - k * sd


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    prev = close.shift(1)
    tr = pd.concat([(high - low), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k_period: int = 14, d_period: int = 3):
    ll = low.rolling(k_period).min()
    hh = high.rolling(k_period).max()
    k = 100 * (close - ll) / (hh - ll).replace(0, np.nan)
    return k, k.rolling(d_period).mean()


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 20) -> pd.Series:
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(n).mean()
    mean_dev = (tp - sma_tp).abs().rolling(n).mean()
    return (tp - sma_tp) / (0.015 * mean_dev.replace(0, np.nan))


def _roc(s: pd.Series, n: int = 12) -> pd.Series:
    return ((s - s.shift(n)) / s.shift(n)) * 100


def _obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    return (np.sign(close.diff().fillna(0)) * volume).cumsum()


def _vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical = (high + low + close) / 3
    return (typical * volume).cumsum() / volume.cumsum().replace(0, np.nan)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    up = high.diff()
    down = -low.diff()
    plus_dm = up.where((up > down) & (up > 0), 0.0)
    minus_dm = down.where((down > up) & (down > 0), 0.0)
    atr_v = _atr(high, low, close, n)
    plus_di = 100 * (plus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_v)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / n, adjust=False).mean() / atr_v)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def _last(s: pd.Series) -> float | None:
    if s.empty:
        return None
    v = s.iloc[-1]
    return float(v) if pd.notna(v) else None


def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    close, high, low, volume = df["close"], df["high"], df["low"], df["volume"]
    macd_l, macd_s, macd_h = _macd(close)
    bb_u, bb_m, bb_l = _bollinger(close)
    k_, d_ = _stochastic(high, low, close)
    return {
        "sma_20": _last(_sma(close, 20)),
        "sma_50": _last(_sma(close, 50)),
        "sma_200": _last(_sma(close, 200)),
        "ema_12": _last(_ema(close, 12)),
        "ema_26": _last(_ema(close, 26)),
        "rsi_14": _last(_rsi(close, 14)),
        "macd": {"macd": _last(macd_l), "signal": _last(macd_s), "histogram": _last(macd_h)},
        "bb_upper": _last(bb_u),
        "bb_middle": _last(bb_m),
        "bb_lower": _last(bb_l),
        "atr_14": _last(_atr(high, low, close, 14)),
        "stochastic": {"k": _last(k_), "d": _last(d_)},
        "cci_20": _last(_cci(high, low, close, 20)),
        "roc_12": _last(_roc(close, 12)),
        "obv": _last(_obv(close, volume)),
        "vwap": _last(_vwap(high, low, close, volume)),
        "adx_14": _last(_adx(high, low, close, 14)),
    }


def derive_signals(ind: dict[str, Any], price: float) -> dict[str, str]:
    rsi_v = ind.get("rsi_14")
    rsi_sig = (
        "overbought" if rsi_v and rsi_v > 70
        else "oversold" if rsi_v and rsi_v < 30
        else "neutral" if rsi_v is not None
        else "unknown"
    )

    macd_h = ind.get("macd", {}).get("histogram")
    macd_sig = (
        "bullish" if macd_h is not None and macd_h > 0
        else "bearish" if macd_h is not None and macd_h < 0
        else "neutral" if macd_h is not None
        else "unknown"
    )

    bb_u, bb_l = ind.get("bb_upper"), ind.get("bb_lower")
    if bb_u and bb_l:
        bb_sig = "overbought" if price >= bb_u else "oversold" if price <= bb_l else "normal"
    else:
        bb_sig = "unknown"

    sma_50, sma_200 = ind.get("sma_50"), ind.get("sma_200")
    adx_v = ind.get("adx_14")
    if sma_50 and sma_200:
        if price > sma_50 > sma_200:
            trend = "strong_uptrend" if adx_v and adx_v > 25 else "uptrend"
        elif price < sma_50 < sma_200:
            trend = "strong_downtrend" if adx_v and adx_v > 25 else "downtrend"
        else:
            trend = "sideways"
    else:
        trend = "unknown"

    k = ind.get("stochastic", {}).get("k")
    stoch_sig = (
        "overbought" if k and k > 80
        else "oversold" if k and k < 20
        else "neutral" if k is not None
        else "unknown"
    )

    score = 0
    score += {"oversold": 1, "overbought": -1}.get(rsi_sig, 0)
    score += {"bullish": 1, "bearish": -1}.get(macd_sig, 0)
    score += {"oversold": 1, "overbought": -1}.get(bb_sig, 0)
    score += {"strong_uptrend": 2, "uptrend": 1, "downtrend": -1, "strong_downtrend": -2}.get(trend, 0)
    if score >= 3:
        rec = "strong_buy"
    elif score >= 1:
        rec = "buy"
    elif score == 0:
        rec = "hold"
    elif score >= -2:
        rec = "sell"
    else:
        rec = "strong_sell"

    return {
        "rsi_signal": rsi_sig,
        "macd_signal": macd_sig,
        "bb_signal": bb_sig,
        "trend": trend,
        "stochastic_signal": stoch_sig,
        "recommendation": rec,
    }


def make_chart(df: pd.DataFrame, ticker: str) -> str | None:
    try:
        import mplfinance as mpf
    except ImportError:
        return None
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    safe_t = re.sub(r"[^A-Za-z0-9._-]", "_", ticker)
    out_path = CHART_DIR / f"{safe_t}_{int(time.time())}.png"
    addplots = []
    sma_50 = df["close"].rolling(50).mean()
    sma_200 = df["close"].rolling(200).mean()
    if sma_50.notna().sum() > 5:
        addplots.append(mpf.make_addplot(sma_50, color="orange"))
    if sma_200.notna().sum() > 5:
        addplots.append(mpf.make_addplot(sma_200, color="purple"))
    plot_df = df.rename(columns={
        "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume",
    })
    try:
        mpf.plot(
            plot_df,
            type="candle",
            style="yahoo",
            addplot=addplots or None,
            volume=True,
            title=f"{ticker} — Candlestick (SMA 50 orange, SMA 200 purple)",
            savefig=dict(fname=str(out_path), dpi=120, bbox_inches="tight"),
        )
    except Exception as e:
        print(f"warning: chart render failed: {e}", file=sys.stderr)
        return None
    return str(out_path)


def fetch_sentiment(ticker: str) -> dict[str, Any] | None:
    try:
        from textblob import TextBlob
    except ImportError:
        return None
    try:
        news = getattr(yf.Ticker(ticker), "news", []) or []
    except Exception:
        news = []
    headlines: list[dict[str, Any]] = []
    pols: list[float] = []
    subs: list[float] = []
    for n in news[:10]:
        content = n.get("content") if isinstance(n, dict) else None
        title = (
            (content.get("title") if isinstance(content, dict) else None)
            or n.get("title")
            or n.get("headline")
            or ""
        )
        if not title:
            continue
        tb = TextBlob(title)
        pol, sub = float(tb.sentiment.polarity), float(tb.sentiment.subjectivity)
        pols.append(pol)
        subs.append(sub)
        publisher = None
        link = None
        if isinstance(content, dict):
            prov = content.get("provider") or {}
            publisher = prov.get("displayName") if isinstance(prov, dict) else None
            cu = content.get("canonicalUrl") or {}
            link = cu.get("url") if isinstance(cu, dict) else None
        headlines.append({
            "title": title,
            "publisher": publisher or n.get("publisher"),
            "link": link or n.get("link"),
            "polarity": pol,
            "subjectivity": sub,
        })
    return {
        "average_polarity": sum(pols) / len(pols) if pols else None,
        "average_subjectivity": sum(subs) / len(subs) if subs else None,
        "headlines": headlines,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Stock analyzer (yfinance-backed)")
    p.add_argument("--ticker", required=True)
    p.add_argument("--technical", action="store_true", help="include technical indicators + signals")
    p.add_argument("--period", default="6mo", help="1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, max")
    p.add_argument("--interval", default="1d", help="1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--no-chart", action="store_true")
    p.add_argument("--no-sentiment", action="store_true")
    args = p.parse_args()

    ticker = args.ticker.upper()
    market_name, market_code, default_currency = detect_market(ticker)

    cp = cache_path(ticker, args.period, args.interval)
    cached = None if args.no_cache else load_cache(cp)
    if cached:
        cached.setdefault("metadata", {})["cached"] = True
        print(json.dumps(cached, indent=2, default=str))
        return 0

    try:
        df = fetch_history(ticker, args.period, args.interval)
        quote = fetch_quote(ticker)
    except Exception as e:
        print(json.dumps({
            "error": f"data fetch failed: {e}",
            "ticker": ticker,
            "hint": "Check ticker symbol; for HK use .HK, Shanghai .SS, Shenzhen .SZ. Retry with --no-cache if rate-limited.",
        }, indent=2))
        return 1

    last_close = float(df["close"].iloc[-1])
    current = quote.get("current") or last_close
    prev = quote.get("previous_close")
    if prev is None:
        prev = float(df["close"].iloc[-2]) if len(df) > 1 else last_close
    change = current - prev if (current is not None and prev is not None) else None
    change_pct = (change / prev * 100) if (change is not None and prev) else None

    out: dict[str, Any] = {
        "metadata": {
            "ticker": ticker,
            "name": quote.get("name"),
            "market": market_code,
            "market_name": market_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "currency": quote.get("currency") or default_currency,
            "period": args.period,
            "interval": args.interval,
            "cached": False,
        },
        "price": {
            "current": current,
            "previous_close": prev,
            "change": change,
            "change_pct": change_pct,
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "volume": quote.get("volume"),
        },
        "fundamentals": {
            "market_cap": quote.get("market_cap"),
            "pe_ratio": quote.get("pe_ratio"),
            "revenue": quote.get("revenue"),
            "net_income": quote.get("net_income"),
        },
    }

    if args.technical:
        ind = compute_indicators(df)
        out["technical"] = {"indicators": ind, "signals": derive_signals(ind, current)}

    if not args.no_chart:
        chart_path = make_chart(df, ticker)
        if chart_path:
            out["chart"] = chart_path

    if not args.no_sentiment:
        sent = fetch_sentiment(ticker)
        if sent:
            out["news_sentiment"] = sent

    hist_tail = df.tail(60).reset_index()
    hist_tail.columns = [str(c).lower() for c in hist_tail.columns]
    date_col = next((c for c in ("date", "datetime") if c in hist_tail.columns), hist_tail.columns[0])
    out["history"] = [
        {
            "date": str(row[date_col]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        }
        for _, row in hist_tail.iterrows()
    ]

    save_cache(cp, out)
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
