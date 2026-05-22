# Claude Code ETF AI Analyzer

Seven AI-powered finance skills for [Claude Code](https://claude.com/claude-code), focused on ETF and equity analysis: deep-dive holdings, sector/momentum scanning, basket backtests with drawdown, and document generation. CLI and VS Code share `~/.claude/skills/`, so installing once covers both.

## Quick start

```bash
git clone https://github.com/jasonjiao2024/claude-code-etf-ai-analyzer.git
cd claude-code-etf-ai-analyzer
./install.sh
```

Requires Python 3.11+. The installer copies files into `~/.claude/skills/` and `~/.claude/scripts/finance-skills/`, then creates five Python venvs and `pip install`s the deps. Restart Claude Code afterward.

Idempotent — safe to re-run.

## What you get

| Skill              | What it does                                                                                                          | Needs                  |
| ------------------ | --------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| **`etf-analyzer`** | Deep dive on any ETF: AUM, top-10 holdings + concentration, sector / geography / asset-class breakdown, aggregate P/E, dividend yield + frequency, UCITS status, domicile, inception, full performance + max drawdown. Includes `--compare` mode for pairwise holdings overlap (Jaccard + weight-weighted) across 2+ ETFs. | nothing (yfinance) |
| **`etf-backtest`** | Historical backtest of a single ETF or a weighted basket. Computes annualised return + vol + Sharpe-ish, max drawdown (depth, peak/trough/recovery, duration), worst rolling 3m/6m/12m, calendar-year returns. Renders drawdown chart PNG. | nothing (yfinance) |
| **`sector-scanner`** | Ranks a sector / ETF universe by composite trend score (returns + technicals + sentiment). Three universes built in: 11 SPDR sectors, 12 US thematics, **22-ETF UCITS list** (T212-tradable). Descriptive, not predictive. | nothing (yfinance) |
| **`stock-analyzer`** | Single-ticker analysis (works on stocks AND ETFs): price + 15+ technical indicators (RSI / MACD / Bollinger / SMA / EMA / ADX / Stochastic / CCI / ROC / OBV / VWAP / ATR) + candlestick chart with SMA overlays + news sentiment. Multi-market: US, HK `.HK`, Shanghai `.SS`, Shenzhen `.SZ`, Tokyo `.T`, London `.L`. | nothing (yfinance) |
| `finance-xlsx`     | Generates real `.xlsx` workbooks (P&L, dashboards, portfolio sheets) via the Anthropic-hosted `xlsx` skill.            | `ANTHROPIC_API_KEY`    |
| `finance-pptx`     | Generates real `.pptx` decks (executive summaries, IC presentations) via the Anthropic-hosted `pptx` skill.            | `ANTHROPIC_API_KEY`    |
| `finance-pdf`      | Generates formal `.pdf` documents via the Anthropic-hosted `pdf` skill.                                                | `ANTHROPIC_API_KEY`    |

Each skill's `SKILL.md` documents the full interface (flags, JSON schema, how to interpret).

## Common workflows

```bash
# Single ETF — what's inside, what's it done?
~/.claude/skills/etf-analyzer/run.sh --ticker AINF.L

# Compare overlap: "do I diversify by holding both A and B?"
~/.claude/skills/etf-analyzer/run.sh --compare AINF.L,IUIT.L,SOXX

# Backtest a 50/50 basket since 2020 with drawdown chart
~/.claude/skills/etf-backtest/run.sh --tickers SWDA.L,SGLD.L --weights 0.6,0.4 --period max

# Scan the UCITS (T212-tradable) universe for what's leading right now
~/.claude/skills/sector-scanner/run.sh --ucits

# Single-ticker chart + signals (works on ETFs too)
~/.claude/skills/stock-analyzer/run.sh --ticker ISUN.L --technical
```

After install, you can also just *ask* in any Claude Code conversation — "what's inside AINF.L", "compare AINF.L and IUIT.L by holdings", "backtest SWDA.L since 2020" — and Claude will auto-trigger the right skill.

## UCITS universe (sector-scanner `--ucits`)

22 LSE / Xetra UCITS ETFs verified against yfinance, covering broad market (`SWDA.L`, `CSPX.L`, `CNDX.L`, `IEMA.L`), US sector sub-funds (`IUIT.L`, `IUFS.L`, `IUHC.L`, `IUCD.L`, `IUES.L`, `IUIS.L`, `IUUS.L`), thematics (`AINF.L`, `AIAI.L`, `RBOT.L`, `ISUN.L`, `INRG.L`, `WCBR.L`, `ARMR.L`, `URNM.L`, `HEAL.L`), and commodities / crypto (`SGLD.L`, `BTCE.DE`). Edit `skills/sector-scanner/scripts/scan.py` to add or remove tickers.

## VS Code

Claude Code's VS Code extension reads the same `~/.claude/skills/` directory as the CLI. After install + a VS Code restart, the skills register automatically.

## Disclaimer

- **`sector-scanner` is descriptive, not predictive.** It tells you what is *currently* leading; it does not forecast. Momentum is a documented anomaly but reverses without warning.
- **`etf-backtest` is rear-view.** A 2-year backtest in a steady uptrend tells you almost nothing about tail risk. Past performance is not predictive of future returns.
- **No expense ratio in `etf-analyzer`.** yfinance does not expose TER. Look it up on the provider's fund page.
- **Holdings data limited to top ~10** in yfinance's `top_holdings` endpoint — `etf-analyzer` overlap analysis is a top-of-book proxy, not the full portfolio.
- **No transaction costs, taxes, FX, or rebalancing** in the backtest. Real-world returns will be lower.
- **None of this is financial advice.** The composite signals are deterministic functions of the indicators; they don't know your portfolio, time horizon, or risk tolerance.


## Uninstall

```bash
rm -rf ~/.claude/skills/{finance-xlsx,finance-pptx,finance-pdf,stock-analyzer,sector-scanner,etf-analyzer,etf-backtest}
rm -rf ~/.claude/scripts/finance-skills
```

## License

MIT — see [LICENSE](LICENSE).
