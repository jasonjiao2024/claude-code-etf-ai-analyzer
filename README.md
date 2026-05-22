# Claude Code Finance Skills

Five skills for financial analysis in [Claude Code](https://claude.com/claude-code) (the CLI and the VS Code extension share `~/.claude/skills/`, so installing once covers both).

## Quick start

```bash
git clone https://github.com/jasonjiao2024/claude-finance-skills.git
cd claude-finance-skills
./install.sh
```

Requires Python 3.11+. The installer copies files into `~/.claude/skills/` and `~/.claude/scripts/finance-skills/`, then creates three Python venvs and `pip install`s their deps. Restart Claude Code afterward.

Idempotent — safe to re-run.

## Skills

| Skill            | What it does                                                                                                            | Needs                  |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------------------- |
| `finance-xlsx`   | Generates real `.xlsx` workbooks (P&L, dashboards, portfolio sheets) via the Anthropic-hosted `xlsx` skill.             | `ANTHROPIC_API_KEY`    |
| `finance-pptx`   | Generates real `.pptx` decks (executive summaries, IC presentations) via the Anthropic-hosted `pptx` skill.             | `ANTHROPIC_API_KEY`    |
| `finance-pdf`    | Generates formal `.pdf` documents via the Anthropic-hosted `pdf` skill.                                                 | `ANTHROPIC_API_KEY`    |
| `stock-analyzer` | Single-ticker: price + 15+ technical indicators (RSI, MACD, Bollinger, SMA/EMA, ADX, …) + candlestick chart + sentiment. | nothing (yfinance)     |
| `sector-scanner` | Ranks a sector/ETF universe by a composite "trend score" (returns + technicals + sentiment). Descriptive, not predictive. | nothing (yfinance)     |

Each skill's `SKILL.md` documents the full interface (flags, JSON schema, how to interpret).

## VS Code

Claude Code's VS Code extension reads the same `~/.claude/skills/` directory as the CLI. After install + a VS Code restart, the skills register automatically.

## Platform notes

Tested on macOS. On Linux it should work as-is. On Windows the `.sh` wrappers won't run natively — use WSL, or port them to `.ps1`. The Python backends are cross-platform.

## Honest framing

`sector-scanner` is **descriptive, not predictive**. It tells you what is currently leading; it does not forecast. Momentum is a documented anomaly but reverses without warning. Don't make trading decisions purely on the composite score.

## Uninstall

```bash
rm -rf ~/.claude/skills/{finance-xlsx,finance-pptx,finance-pdf,stock-analyzer,sector-scanner}
rm -rf ~/.claude/scripts/finance-skills
```
