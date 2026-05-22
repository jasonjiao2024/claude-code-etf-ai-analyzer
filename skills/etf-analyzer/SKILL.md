---
name: etf-analyzer
description: ETF-specific deep-dive analyzer. Pulls fund metadata via yfinance: AUM, top-N holdings + concentration, sector and asset-class breakdown, aggregate fund-level P/E and P/B, dividend yield + distribution frequency (accumulating vs distributing), UCITS status, domicile, inception date, and performance metrics (1m/3m/6m/YTD/1y/total/annualised return, annualised volatility, Sharpe-ish ratio, max drawdown + recovery time). Use when the user asks about an ETF's holdings, concentration, expense, fund size, dividends, or wants to understand what's *inside* an ETF beyond price. Goes deeper than stock-analyzer for ETF tickers.
tags: [ETF analysis, holdings, AUM, sector allocation, dividend yield, fund metadata, UCITS, drawdown]
---

# ETF Deep-Dive Analyzer

Wraps `scripts/analyze.py`. For any ETF ticker, pulls everything yfinance exposes via `.info` and `.funds_data`, computes performance + drawdown, and emits a single JSON document on stdout.

## When to use

- "What's inside AINF.L?"
- "Top holdings of QQQ"
- "How concentrated is INRG.L?"
- "Does ISUN.L pay dividends?"
- "Sector breakdown of VWRP.L"
- "How big is AUM for X?"
- "Max drawdown of TAN since launch?"
- Any "tell me about this ETF" question beyond price/indicators (use `stock-analyzer` for the candlestick chart + technical signals).

## How to invoke

Two modes, mutually exclusive:

```bash
# Mode 1: single-ETF deep dive
~/.claude/skills/etf-analyzer/run.sh --ticker <SYM> [--period max] [--max-holdings 10]

# Mode 2: pairwise holdings overlap across 2+ ETFs
~/.claude/skills/etf-analyzer/run.sh --compare <SYM1>,<SYM2>[,<SYM3>...]
```

Examples:

| User intent                                | Command                                                                            |
| ------------------------------------------ | ---------------------------------------------------------------------------------- |
| "What's inside AINF.L?"                    | `~/.claude/skills/etf-analyzer/run.sh --ticker AINF.L`                             |
| "Top 25 holdings of QQQ"                   | `~/.claude/skills/etf-analyzer/run.sh --ticker QQQ --max-holdings 25`              |
| "Performance of INRG.L over 5 yr"          | `~/.claude/skills/etf-analyzer/run.sh --ticker INRG.L --period 5y`                 |
| "How much do AINF and IUIT overlap?"       | `~/.claude/skills/etf-analyzer/run.sh --compare AINF.L,IUIT.L`                     |
| "Compare three AI ETFs"                    | `~/.claude/skills/etf-analyzer/run.sh --compare AINF.L,AIAI.L,RBOT.L`              |

Flags:
- `--ticker SYM` — Single deep dive. UCITS suffixes: `.L`, `.MI`, `.DE`, `.AS`, `.SW`.
- `--compare T1,T2,...` — Comma-separated 2+ tickers for overlap analysis.
- `--period {1mo,3mo,6mo,1y,2y,5y,10y,max}` — history window (single-ticker mode only). Default `max`.
- `--max-holdings N` — top-N to surface (default 10, single-ticker mode only).

## --compare output schema

```json
{
  "mode": "compare",
  "tickers": ["AINF.L", "IUIT.L"],
  "metadata": {
    "AINF.L": {"name": "...", "currency": "GBP", "aum": 910240320, "n_visible_holdings": 10, "visible_weight_sum": 0.497},
    "IUIT.L": {...}
  },
  "pairs": [
    {
      "a": "AINF.L", "b": "IUIT.L",
      "n_shared": 7, "n_union": 13,
      "jaccard": 0.538,
      "weighted_overlap": 0.21,
      "a_top_weight_in_shared": 0.32,
      "b_top_weight_in_shared": 0.45,
      "shared_holdings": [{"symbol": "NVDA", "name": "NVIDIA Corp", "weight_a": 0.041, "weight_b": 0.085}, ...]
    }
  ],
  "unique_to_each": {
    "AINF.L": ["2330.TW", "INTC", "MU"],
    "IUIT.L": ["CRM", "ADBE"]
  }
}
```

### Interpreting overlap

- **Jaccard 0.0-0.2** = mostly differentiated. Holding both gives real diversification.
- **Jaccard 0.2-0.5** = moderate overlap. Different top weights but shared themes.
- **Jaccard > 0.5** = heavy overlap of top names. Holding both is largely redundant at the top of the book.
- **weighted_overlap** is the more honest measure: it says "if you held equal-dollar positions in A and B, this fraction of your capital is in the same names." A weighted_overlap of 0.30 = 30% of your money is doubled up.
- **Top yfinance returns only ~10 holdings per ETF.** The overlap is calculated on top-of-book only — it does not reflect the full portfolio. State this caveat when reporting.

## JSON output schema

```json
{
  "metadata": {
    "ticker": "AINF.L",
    "name": "iShares AI Infrastructure UCITS ETF USD (Acc)",
    "isin": "...",
    "fund_family": "BlackRock Asset Management Ireland - ETF",
    "domicile_guess": "Ireland",
    "ucits": true,
    "legal_type": "Exchange Traded Fund",
    "exchange": "LSE",
    "currency": "GBP",
    "inception_date": "2024-12-05",
    "quote_type": "ETF",
    "timestamp": "..."
  },
  "size_and_cost": {
    "aum": 910240320,
    "expense_ratio": null,
    "expense_ratio_note": "Not available via yfinance. Check the provider fund page."
  },
  "distribution": {
    "yield": 0.0, "annual_rate": null, "ttm_sum": 0.0,
    "n_distributions_ttm": 0,
    "frequency": "accumulating (no distributions observed)",
    "is_accumulating": true
  },
  "asset_classes": {"stockPosition": 0.9963, "cashPosition": 0.0037, ...},
  "holdings": {
    "top_n": [{"symbol": "INTC", "name": "Intel Corp", "weight": 0.078}, ...],
    "n_holdings_visible": 10,
    "top_n_concentration": 0.55
  },
  "sectors": [{"sector": "technology", "weight": 0.887}, ...],
  "equity_aggregate": {"price_earnings": ..., "price_book": ..., "price_sales": ..., "price_cashflow": ...},
  "performance": {
    "price": 7.744,
    "return_1m": 0.115, "return_3m": 0.085, "return_6m": ..., "return_ytd": ..., "return_1y": 0.94,
    "total_return_over_history": ..., "annualised_return": ..., "annualised_volatility": ...,
    "sharpe_ish": ...,
    "max_drawdown": -0.20,
    "max_drawdown_peak_date": "2024-12-09",
    "max_drawdown_trough_date": "2025-02-22",
    "max_drawdown_recovery_date": "2025-05-15",
    "max_drawdown_recovery_days": 157,
    "history_start": "2024-12-09", "history_end": "2026-05-22", "history_n_days": 529
  },
  "fund_overview": {"category": null, "family": "BlackRock Asset Management Ireland - ETF", "legal_type": "Exchange Traded Fund"}
}
```

## How to report results

1. **Lead with: name, AUM, domicile, currency, inception, UCITS yes/no.** These set context.
2. **Top holdings + concentration.** Cite the top 3-5 with weights. State the `top_n_concentration` percentage and what it means: < 30% diversified, 30-50% moderate, > 50% concentrated.
3. **Sector breakdown.** Surface the top 2-3 sectors and what % they are. For thematic ETFs this should be highly concentrated (e.g., AI infra → 89% technology).
4. **Asset class split.** Mostly equity is normal for stock ETFs; flag if there's notable cash/bond/other.
5. **Distributions.** If `is_accumulating=true`, say "accumulating — reinvests dividends internally." Otherwise state yield and frequency.
6. **Aggregate fund-level valuation.** P/E, P/B, P/S — useful for "is this ETF expensive?" Higher numbers = pricier basket.
7. **Performance section.** Quote return_1m/3m/1y/total + annualised return + annualised volatility + Sharpe. Then drawdown: "Lost X% from PEAK to TROUGH (DURATION days), recovered DURATION days later" — or "still in drawdown."
8. **Expense ratio**: explicitly say it's not available via yfinance and point to the provider page.
9. **Cite numbers.** Never invent.
10. **T212 context** when relevant — UCITS lines on LSE are tradable; flag if quoted in USD (FX fee) vs GBP (no fee).

## Limitations

- **No expense ratio (TER).** yfinance does not expose it. Provider fund pages are the source. Future work: hardcode TERs for the common UCITS basket.
- **Holdings data limited to top-10** in yfinance's `top_holdings` endpoint, even if you ask for more — yfinance just doesn't return more rows. `--max-holdings 25` will not give you 25; it'll give you however many yfinance returns (typically 10).
- **Sector weights** for some thematic ETFs may not sum to 1.0 if yfinance is missing categories.
- **Aggregate equity ratios** can look implausibly small (e.g., `price_earnings: 0.03`) — yfinance occasionally emits these as decimal fractions instead of raw ratios; treat as relative comparison only.
- **Drawdown is bounded by available history.** A 2-year-old ETF can only show drawdowns from the past 2 years — it has not been tested through a bear market if one didn't occur in that window. **State this explicitly when reporting.**
- **No tracking error vs benchmark.** yfinance doesn't expose the benchmark series. Computing tracking error requires fetching the benchmark separately.
- **Yahoo data has ~15-min delay** on the free tier and may rate-limit on heavy use.

## Data source

yfinance (`Ticker.info`, `Ticker.funds_data`, `Ticker.dividends`, `Ticker.history`). No API keys required.
