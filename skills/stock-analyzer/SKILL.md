---
name: stock-analyzer
description: Financial stock analysis via yfinance — fetches real-time + historical prices, computes 15+ technical indicators (RSI, MACD, Bollinger, SMA/EMA, ADX, Stochastic, CCI, ROC, OBV, VWAP, ATR), renders candlestick charts with SMA overlays, runs news sentiment on Yahoo headlines (TextBlob), and emits buy/sell/hold signals. Multi-market support (US, HK .HK, Shanghai .SS, Shenzhen .SZ, Tokyo .T, London .L). Yahoo data has ~15-min delay on the free tier and may rate-limit.
tags: [stock analysis, technical indicators, charts, sentiment, yfinance, trading signals, multi-market]
---

# Stock Analyzer

Self-contained Claude Code skill for stock analysis. Backend is `scripts/main.py` (yfinance + pandas + mplfinance + textblob), run via `run.sh` which uses the bundled venv at `.venv/`. Returns a single JSON document on stdout matching the schema below.

## Capabilities

- **Price**: current, open/high/low/close, volume, prev close, day change %
- **Fundamentals**: market cap, P/E, revenue, net income (where Yahoo provides them)
- **Technical indicators**: SMA (20/50/200), EMA (12/26), RSI(14), MACD, Bollinger Bands (20,2), ATR(14), Stochastic %K/%D, CCI(20), ROC(12), OBV, VWAP, ADX(14)
- **Signals**: per-indicator (overbought/oversold/bullish/bearish/neutral/trend) + composite recommendation (strong_buy / buy / hold / sell / strong_sell)
- **Chart**: candlestick PNG with SMA-50 and SMA-200 overlays and volume panel
- **Sentiment**: TextBlob polarity + subjectivity on the latest Yahoo headlines (up to 10)
- **Cache**: 15-min file-based cache in `cache/`; skip with `--no-cache`

## How to invoke

Always call via the wrapper — it uses the bundled venv interpreter automatically:

```bash
~/.claude/skills/stock-analyzer/run.sh --ticker <SYMBOL> [flags]
```

Common patterns by user intent:

| User asks                              | Command                                                                                    |
| -------------------------------------- | ------------------------------------------------------------------------------------------ |
| "What's AAPL trading at?"              | `~/.claude/skills/stock-analyzer/run.sh --ticker AAPL --no-chart --no-sentiment`           |
| "Is TSLA overbought?" / "Analyze MSFT" | `~/.claude/skills/stock-analyzer/run.sh --ticker TSLA --technical`                         |
| "Show me a chart of AAPL"              | `~/.claude/skills/stock-analyzer/run.sh --ticker AAPL --technical`                         |
| "What's the sentiment on NVDA?"        | `~/.claude/skills/stock-analyzer/run.sh --ticker NVDA --no-chart`                          |
| "MSFT over the last 6 months"          | `~/.claude/skills/stock-analyzer/run.sh --ticker MSFT --period 6mo --technical`            |
| "Analyze Tencent"                      | `~/.claude/skills/stock-analyzer/run.sh --ticker 0700.HK --technical`                      |
| "How is Moutai performing?"            | `~/.claude/skills/stock-analyzer/run.sh --ticker 600519.SS --technical`                    |

Flags:
- `--ticker SYM` (required) — Yahoo Finance ticker. Suffix selects market: `.HK`, `.SS`, `.SZ`, `.T`, `.L`. No suffix = US.
- `--technical` — include `technical.indicators` + `technical.signals` in output
- `--period {1d,5d,1mo,3mo,6mo,1y,2y,5y,10y,max}` (default `6mo`)
- `--interval {1m,5m,15m,30m,1h,1d,1wk,1mo}` (default `1d`)
- `--no-cache` — force fresh fetch (use on rate-limit or stale data)
- `--no-chart` — skip candlestick PNG (faster, no `chart` field)
- `--no-sentiment` — skip news sentiment (faster, no `news_sentiment` field)

## JSON output schema

```json
{
  "metadata": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "market": "us",
    "market_name": "United States",
    "timestamp": "2026-05-22T15:30:00Z",
    "currency": "USD",
    "period": "6mo",
    "interval": "1d",
    "cached": false
  },
  "price": {
    "current": 185.23, "previous_close": 184.50,
    "change": 0.73, "change_pct": 0.40,
    "open": 184.50, "high": 186.00, "low": 183.75, "volume": 52341000
  },
  "fundamentals": {
    "market_cap": 2900000000000, "pe_ratio": 29.5,
    "revenue": 383000000000, "net_income": 97000000000
  },
  "technical": {
    "indicators": {
      "sma_20": 183.20, "sma_50": 182.34, "sma_200": 175.67,
      "ema_12": 184.11, "ema_26": 182.45,
      "rsi_14": 62.5,
      "macd": {"macd": 2.34, "signal": 1.89, "histogram": 0.45},
      "bb_upper": 190.50, "bb_middle": 185.00, "bb_lower": 179.50,
      "atr_14": 3.21, "stochastic": {"k": 70.1, "d": 65.8},
      "cci_20": 110.3, "roc_12": 4.2, "obv": 12345678,
      "vwap": 184.55, "adx_14": 28.4
    },
    "signals": {
      "rsi_signal": "neutral", "macd_signal": "bullish",
      "bb_signal": "normal", "trend": "uptrend",
      "stochastic_signal": "neutral", "recommendation": "buy"
    }
  },
  "chart": "/Users/.../stock-analyzer/charts/AAPL_1747920000.png",
  "news_sentiment": {
    "average_polarity": 0.45, "average_subjectivity": 0.62,
    "headlines": [
      {"title": "...", "publisher": "...", "link": "...", "polarity": 0.5, "subjectivity": 0.6}
    ]
  },
  "history": [{"date": "...", "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}, ...]
}
```

On error, output is `{"error": "...", "ticker": "...", "hint": "..."}` and exit code 1.

## How to respond to the user

1. **Parse the JSON.** If `error` field present, explain the error and suggest a fix (most often: bad ticker, rate-limit → retry with `--no-cache`, or market closed).
2. **State price + change first** in the user's local terms. Include currency (from `metadata.currency`).
3. **For technical queries**: cite specific indicator values, interpret what each signal means (don't just say "RSI is 62.5" — say "RSI at 62.5 is in neutral territory; overbought begins at 70"). End with the composite `recommendation`.
4. **For chart queries**: embed the chart path as markdown image — `![Chart](<chart-path>)` using the literal path from `chart`. Then describe one or two visible patterns.
5. **For sentiment queries**: report `average_polarity` (−1 to +1) and `average_subjectivity` (0 to 1), and surface 1–2 headlines.
6. **Cache awareness**: if `metadata.cached` is true, mention the data may be up to 15 min old. The user can pass `--no-cache` for fresh data.
7. **Never invent numbers.** Only cite values that appear in the JSON.

## Limitations

- Yahoo free tier: ~15-min delay; rate limits possible.
- Some indicators need minimum history (SMA-200 needs ≥200 days). Short-period requests will return `null` for those.
- yfinance `info` and `news` endpoints are flaky and occasionally break across yfinance versions — fundamentals/sentiment may be missing or empty.
- Technical signals are descriptive, not predictive. Not financial advice.
- CN A-share data availability is the most limited (US > HK > CN).

## Maintenance

```bash
~/.claude/skills/stock-analyzer/.venv/bin/pip install --upgrade yfinance pandas mplfinance textblob
# Clear cache if stale:
rm -rf ~/.claude/skills/stock-analyzer/cache/*
# Clear charts:
rm -rf ~/.claude/skills/stock-analyzer/charts/*
```

## Data sources

- Primary: `yfinance` (Yahoo Finance).
- Sentiment: TextBlob on Yahoo news headlines.
- No T212 / brokerage integration — this is read-only market data. For T212 actions use the `trading212-api` skill.
