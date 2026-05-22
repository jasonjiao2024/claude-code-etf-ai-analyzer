---
name: sector-scanner
description: Sector / ETF momentum scanner with news-sentiment overlay. Scans the 11 SPDR sector ETFs (or a custom ticker list) and ranks them by a composite "trend score" combining 1m+3m returns, RSI sweet spot, MACD bullishness, trend confirmation vs SMA-50/SMA-200, ADX strength, and TextBlob sentiment aggregated across each sector's top constituents. Returns leaders + laggards. DESCRIPTIVE, not predictive — reports what is currently leading, never claims a forecast. Use for "what sector is hot?", "what's trending?", "best ETF right now?", or sector-rotation analysis.
tags: [sector rotation, momentum, sentiment, ETF screening, market scan, trend scoring]
---

# Sector / ETF Momentum Scanner

Wraps `scripts/scan.py` (yfinance + pandas + textblob, in the bundled `.venv`). For each ticker in the universe: fetches 6-month daily history, computes momentum + technical metrics, optionally aggregates news sentiment across the sector's top constituents, and emits a composite-score ranking.

## Honest framing — read this first

This is a **descriptive scanner**, not a forecaster. It identifies which sector / ETF currently shows the strongest momentum + sentiment profile. Momentum is a real, documented anomaly (Jegadeesh & Titman 1993 onward) but past trend does not guarantee future returns — momentum can and does reverse.

**Never report results as predictions.** Say "XLK is currently leading the SPDR basket on the trend-score composite," not "XLK is the next trendy sector." If the user explicitly asks for a prediction, decline and offer this scan instead.

## When to use

- "What sector is hot right now?"
- "Which ETFs are trending?"
- "What should I rotate into?"
- "Is tech still leading?"
- "What's the next trendy ETF?" → run scan, surface leaders, **explicitly add the caveat that this isn't a prediction**

## How to invoke

```bash
~/.claude/skills/sector-scanner/run.sh                          # default: 11 SPDR sectors + sentiment
~/.claude/skills/sector-scanner/run.sh --include-thematic       # adds 12 US thematics (IBIT, ARKK, TAN, ICLN, LIT, SOXX, XBI, KWEB, URA, JETS, HACK, GDX)
~/.claude/skills/sector-scanner/run.sh --ucits                  # 21 UCITS / UK-tradable ETFs (T212-friendly)
~/.claude/skills/sector-scanner/run.sh --ucits --include-thematic  # UCITS + US thematics in one scan
~/.claude/skills/sector-scanner/run.sh --no-sentiment           # ~10s instead of ~30-60s
~/.claude/skills/sector-scanner/run.sh --universe SPY,QQQ,VTI,IWM,VWO   # custom basket
~/.claude/skills/sector-scanner/run.sh --top 5                  # show top/bottom 5 instead of 3
```

### UCITS universe (`--ucits`)

22 LSE / Xetra UCITS ETFs covering broad market, US sectors, thematics, commodity, and crypto. All verified against yfinance. Use for T212 UK accounts.

| Group         | Tickers                                                                 |
| ------------- | ----------------------------------------------------------------------- |
| Broad market  | `SWDA.L`, `CSPX.L`, `CNDX.L`, `IEMA.L`                                  |
| US sectors    | `IUIT.L`, `IUFS.L`, `IUHC.L`, `IUCD.L`, `IUES.L`, `IUIS.L`, `IUUS.L`    |
| Thematics     | `AINF.L`, `AIAI.L`, `RBOT.L`, `ISUN.L`, `INRG.L`, `WCBR.L`, `ARMR.L`, `URNM.L`, `HEAL.L` |
| Commodity / crypto | `SGLD.L`, `BTCE.DE`                                                |

Sentiment for the seven US-sector lines (`IUIT.L` etc.) reuses the SPDR top-5 constituents (AAPL/MSFT/NVDA for tech, etc.) since the underlying baskets are essentially identical. Thematics and broad-market UCITS use only the ETF ticker for sentiment, which yields sparse Yahoo headlines — sentiment will often be `None` or based on a tiny sample.

## Composite trend score (0..1)

Weighted average across these dimensions. If a component is unavailable, the remaining weights renormalize.

| Dimension              | Weight | What it measures                                                    |
| ---------------------- | ------ | ------------------------------------------------------------------- |
| Return percentile rank | 0.30   | Rank of 1m return vs the scanned universe (higher = leader)         |
| RSI sweet spot         | 0.10   | Peak at RSI≈60 (healthy momentum, not yet overbought)               |
| MACD bullish           | 0.15   | Histogram > 0 AND macd line > signal line                           |
| Trend confirmation     | 0.15   | Price above SMA-50 and SMA-200                                      |
| ADX strength           | 0.10   | ADX/50 (trend conviction, capped at 1)                              |
| Sentiment polarity     | 0.20   | TextBlob avg across ETF + top constituent headlines, mapped to 0..1 |

## JSON output schema

```json
{
  "metadata": {
    "timestamp": "...",
    "universe": ["XLK", "XLF", ...],
    "sentiment_included": true,
    "n_scanned": 11,
    "n_errors": 0,
    "weights": { ... },
    "framing": "DESCRIPTIVE. Composite score reflects current trend strength, not a forecast."
  },
  "leaders":  [{"ticker": "XLK", "name": "Technology", "composite_score": 0.74, "sub_scores": {...}, "components": {...}, "signal": "leader"}, ...],
  "laggards": [{"ticker": "XLU", ..., "signal": "laggard"}, ...],
  "ranked":   [/* full sorted list, best to worst */],
  "errors":   [/* tickers that failed to fetch — usually rate-limit or bad ticker */]
}
```

Each entry's `components`:
- `return_1m`, `return_3m` — decimals (`0.045` = +4.5%)
- `rsi_14`, `macd_hist`, `macd_above_signal`
- `above_sma_50`, `above_sma_200`, `adx_14`
- `sentiment_polarity` (−1..+1), `sentiment_n_headlines`

`sub_scores` shows each component's 0-1 contribution to the composite — useful for explaining *why* a sector ranked where it did.

## How to report results

1. **State the top leaders** with name, composite_score, and the headline driver (e.g. "XLK leads on +6% 1-month return, RSI at 65 (sweet spot), and ADX 32 (strong trend).").
2. **Cite actual numbers** from `components` / `sub_scores`. Don't say "very bullish" — quote the values.
3. **Always include the caveat**: "This is current trend strength, not a forecast. Momentum can reverse."
4. **Surface laggards** as inverse signal — useful for mean-reversion candidates or to avoid.
5. **Flag thin sentiment** — if `sentiment_n_headlines` < 5, sentiment is noisy. Say so.
6. **Handle errors** — if entries are in `errors`, mention them and suggest retrying (likely yfinance rate-limit).
7. **T212 context** — the user trades on T212. Most US ETFs in the universe (SPDR sectors, thematics like ARKK/SOXX/JETS) are tradable on T212 as fractional shares. **Do not fabricate availability**; if uncertain, say so.

## Performance

- Default scan (11 SPDRs × sentiment across ETF + 5 constituents): ~30-60s. ~66 yfinance calls.
- `--no-sentiment` drops this to ~10s (~11 calls).
- yfinance rate-limits occasionally. If many tickers error, wait a minute and retry.

## Editing the universe

`SECTOR_CONSTITUENTS` and `THEMATIC_ETFS` are dicts at the top of `scripts/scan.py`. SPDR top holdings drift slowly — refresh annually. Add thematic ETFs as you care about them.

## Limitations

- **Not predictive.** Score reflects current state only.
- **Survivorship + lookback bias** — the universe is the universe today; sectors that died aren't in it.
- **Yahoo data**: ~15-min delay free tier; `news` endpoint is flaky and occasionally cross-contaminates tickers (an AAPL query can return NVDA headlines).
- **TextBlob sentiment** is pattern-based, adequate for direction (positive/negative), weak for nuance. Don't over-interpret magnitudes.
- **No market-regime adjustment** — in a broad bull market, everything looks like a leader; in a broad sell-off, everything looks weak. The relative ranking still has signal; the absolute scores don't.
- **No transaction costs, FX, tax, or tradability checks.**
- **Past performance ≠ future returns.** The whole point.

## Data source

yfinance (Yahoo Finance) for price + news. TextBlob for sentiment scoring. No external API keys required.
