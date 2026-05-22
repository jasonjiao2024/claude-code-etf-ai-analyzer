---
name: etf-backtest
description: Historical backtest for a single ETF or a weighted multi-ETF basket. Over a configurable date range, computes annualised return + volatility + Sharpe-ish ratio, max drawdown (depth, peak/trough/recovery dates, duration), worst rolling 3m / 6m / 12m return, and calendar-year total returns. Optionally renders a drawdown-curve PNG. Use when the user asks "what was the worst drawdown of X?", "how would a 60/40 basket have done?", "calendar-year returns of QQQ", or anything backward-looking and quantitative. Total-return basis (auto_adjust, distributions reinvested), no transaction costs / taxes / FX.
tags: [backtest, drawdown, rolling returns, portfolio, Sharpe ratio, historical performance]
---

# ETF / Basket Backtest

Wraps `scripts/backtest.py`. For 1+ tickers (+ optional weights) over a date range, computes the risk/return profile and renders a drawdown chart.

## When to use

- "What was AINF.L's worst drawdown?" → single ticker, max period available
- "How would 50% AINF.L + 50% ISUN.L have done over 2 years?" → 2-ticker equal-weight
- "Backtest 60/40 SWDA.L/SGLD.L since 2020" → custom weights + start date
- "Calendar-year returns of QQQ" → ask for cy_returns specifically
- "Worst rolling 12m for ICLN" → rolling_worst section
- "Compare AINF.L vs broad market" → run both as separate baskets, compare metrics

Do **not** use for: "should I buy X" (use stock-analyzer + sector-scanner instead — backtest is rear-view).

## How to invoke

```bash
~/.claude/skills/etf-backtest/run.sh --tickers <SYM>[,<SYM>...] [--weights W1[,W2...]] [--period 5y | --start YYYY-MM-DD --end YYYY-MM-DD] [--no-chart]
```

Examples:

| User intent                                          | Command                                                                                       |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| Single ETF, max history                              | `~/.claude/skills/etf-backtest/run.sh --tickers SWDA.L --period max`                          |
| 50/50 two-ETF basket, last 3 years                   | `~/.claude/skills/etf-backtest/run.sh --tickers AINF.L,ISUN.L --weights 0.5,0.5 --period 3y`  |
| Custom date range, equal-weight 3-ETF                | `~/.claude/skills/etf-backtest/run.sh --tickers SPY,QQQ,IWM --start 2022-01-01 --end 2023-12-31` |
| 60/40 stocks/gold                                    | `~/.claude/skills/etf-backtest/run.sh --tickers SWDA.L,SGLD.L --weights 0.6,0.4 --period 10y` |
| Skip chart, JSON only                                | add `--no-chart`                                                                              |

Flags:
- `--tickers T1[,T2...]` — comma-separated. Single ticker = single-asset backtest. Multi = basket.
- `--weights W1[,W2...]` — same length as tickers. Auto-normalised to sum to 1. Default: equal-weight.
- `--period {1mo,3mo,6mo,1y,2y,5y,10y,max}` — history window (default 5y). Used only if --start/--end omitted.
- `--start YYYY-MM-DD` / `--end YYYY-MM-DD` — explicit date range. Overrides --period.
- `--no-chart` — skip the drawdown PNG. Faster, no `chart` field in output.
- `--label STR` — custom label used for the chart filename and `metadata.label`.

## JSON output schema

```json
{
  "metadata": {"tickers": [...], "weights": {...}, "label": "...", "period": "5y", "start_arg": null, "end_arg": null, "timestamp": "..."},
  "portfolio": {
    "total_return": 1.34,        // +134% over the window
    "annualised_return": 0.182,  // 18.2% CAGR
    "annualised_volatility": 0.21,
    "sharpe_ish": 0.87,          // ann_return / ann_vol, no risk-free adjustment
    "max_drawdown": -0.34,
    "max_drawdown_peak": "2021-12-27",
    "max_drawdown_trough": "2022-10-12",
    "max_drawdown_recovery": "2024-01-18",  // or null if still in drawdown
    "max_drawdown_duration_days": 752,
    "n_days": 1825, "n_observations": 1258,
    "start_date": "2020-01-02", "end_date": "2025-01-02"
  },
  "rolling_worst": {
    "worst_3m":  {"return": -0.21, "start": "2022-04-04", "end": "2022-07-05"},
    "worst_6m":  {"return": -0.27, "start": "...", "end": "..."},
    "worst_12m": {"return": -0.18, "start": "...", "end": "..."}
  },
  "calendar_year_returns": {"2020": 0.18, "2021": 0.28, "2022": -0.19, "2023": 0.25, "2024": 0.23},
  "per_asset": {
    "AINF.L": {/* same shape as portfolio block */},
    "ISUN.L": {...}
  },
  "chart": "/Users/.../etf-backtest/charts/AINF.L_ISUN.L_<ts>_drawdown.png",
  "caveats": "..."
}
```

## How to report results

1. **Lead with the key risk numbers**: max drawdown (depth + duration), worst rolling 12m. Users need to know what they could have suffered.
2. **State the period explicitly** — "over the last 5 years" or "from 2020-01 to 2025-01." Don't let "annualised 18%" stand without context.
3. **For baskets**: cite the portfolio metrics first, then break down per-asset to show what's driving the result.
4. **Calendar-year returns**: useful for the "what about [bad year X]?" question. Cite the actual year and number.
5. **Sharpe-ish** is `annualised_return / annualised_volatility` with no risk-free adjustment. **Not a true Sharpe ratio.** Use for relative comparison only.
6. **The drawdown chart** shows two stacked panels: equity curve normalised to 1.0 at start (top) and drawdown % over time (bottom, filled red). Embed via `![Drawdown](<path>)` in chat where possible.
7. **Always caveat**: backtest is rear-view; transaction costs / taxes / FX are ignored; buy-and-hold (no rebalancing); past doesn't predict future.

## Methodology

- **Total-return**: yfinance `auto_adjust=True` reinvests dividends into price. So returns are total return, not price-only.
- **Buy-and-hold**: portfolio weights are applied at the *start* of the period; no rebalancing. If one asset rips 200% and another tanks, the weights at the end reflect that drift. This is a deliberate choice — rebalancing adds complexity and assumptions (frequency, costs).
- **Worst rolling N-month**: scans every N-month window in the history; reports the single worst end-point and its start.
- **Calendar-year**: year-end to year-end. For the earliest year (if data starts mid-year), uses first-available price as the start.
- **Drawdown**: peak-to-trough on the equity curve; "recovery" is the next date that closes ≥ the prior peak (or `null` if still underwater).

## Limitations

- **No transaction costs, fees, taxes, FX.** Real-world returns will be lower.
- **No rebalancing.** Add it manually if needed by running shorter sub-periods.
- **Survivorship bias.** Tickers that delisted aren't in yfinance. Backtesting only live tickers ignores funds that closed (often because they did badly).
- **Sample-size warning.** Backtests over short windows or low-volatility regimes are not informative about tail risk. A 2-year backtest in a steady uptrend tells you almost nothing about a future bear market.
- **yfinance can return slightly inconsistent close prices** across versions; small discrepancies vs broker P&L are normal.
- **Past performance is not predictive of future returns.** The whole purpose of a backtest is to know what *could* happen, not what *will*.

## Data source

yfinance (`yf.download` with `auto_adjust=True`). No API keys required.
