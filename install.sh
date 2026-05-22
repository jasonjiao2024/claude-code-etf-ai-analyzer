#!/bin/bash
# Installer for the Claude Code ETF AI Analyzer skill bundle.
# Copies skills + runtime into ~/.claude/, creates Python venvs, installs deps.
# Idempotent — safe to re-run; it replaces files and recreates venvs.

set -euo pipefail

BUNDLE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
CLAUDE_DIR="${HOME}/.claude"

echo "==> Installing into ${CLAUDE_DIR}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found. Install Python 3.11+ first." >&2
  exit 1
fi
PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "    python3 = ${PY_VERSION}"

echo "==> Copying skill folders"
mkdir -p "${CLAUDE_DIR}/skills"
for skill in finance-xlsx finance-pptx finance-pdf stock-analyzer sector-scanner etf-analyzer etf-backtest; do
  echo "    - ${skill}"
  rm -rf "${CLAUDE_DIR}/skills/${skill}"
  cp -R "${BUNDLE_DIR}/skills/${skill}" "${CLAUDE_DIR}/skills/${skill}"
done

echo "==> Copying finance-skills runtime"
mkdir -p "${CLAUDE_DIR}/scripts"
rm -rf "${CLAUDE_DIR}/scripts/finance-skills"
cp -R "${BUNDLE_DIR}/scripts/finance-skills" "${CLAUDE_DIR}/scripts/finance-skills"

chmod +x "${CLAUDE_DIR}/scripts/finance-skills/run_skill.sh"
chmod +x "${CLAUDE_DIR}/skills/stock-analyzer/run.sh"
chmod +x "${CLAUDE_DIR}/skills/sector-scanner/run.sh"
chmod +x "${CLAUDE_DIR}/skills/etf-analyzer/run.sh"
chmod +x "${CLAUDE_DIR}/skills/etf-backtest/run.sh"

echo "==> Creating Python venvs and installing deps (this takes ~2–3 min)"

echo "    - finance-skills venv (anthropic)"
python3 -m venv "${CLAUDE_DIR}/scripts/finance-skills/.venv"
"${CLAUDE_DIR}/scripts/finance-skills/.venv/bin/pip" install --upgrade --quiet pip
"${CLAUDE_DIR}/scripts/finance-skills/.venv/bin/pip" install --quiet anthropic

echo "    - stock-analyzer venv (yfinance + mplfinance + textblob)"
python3 -m venv "${CLAUDE_DIR}/skills/stock-analyzer/.venv"
"${CLAUDE_DIR}/skills/stock-analyzer/.venv/bin/pip" install --upgrade --quiet pip
"${CLAUDE_DIR}/skills/stock-analyzer/.venv/bin/pip" install --quiet yfinance pandas numpy mplfinance matplotlib textblob

echo "    - sector-scanner venv (yfinance + textblob)"
python3 -m venv "${CLAUDE_DIR}/skills/sector-scanner/.venv"
"${CLAUDE_DIR}/skills/sector-scanner/.venv/bin/pip" install --upgrade --quiet pip
"${CLAUDE_DIR}/skills/sector-scanner/.venv/bin/pip" install --quiet yfinance pandas numpy textblob

echo "    - etf-analyzer venv (yfinance)"
python3 -m venv "${CLAUDE_DIR}/skills/etf-analyzer/.venv"
"${CLAUDE_DIR}/skills/etf-analyzer/.venv/bin/pip" install --upgrade --quiet pip
"${CLAUDE_DIR}/skills/etf-analyzer/.venv/bin/pip" install --quiet yfinance pandas numpy

echo "    - etf-backtest venv (yfinance + matplotlib)"
python3 -m venv "${CLAUDE_DIR}/skills/etf-backtest/.venv"
"${CLAUDE_DIR}/skills/etf-backtest/.venv/bin/pip" install --upgrade --quiet pip
"${CLAUDE_DIR}/skills/etf-backtest/.venv/bin/pip" install --quiet yfinance pandas numpy matplotlib

# Runtime directories for cache / charts
mkdir -p "${CLAUDE_DIR}/skills/stock-analyzer/cache" "${CLAUDE_DIR}/skills/stock-analyzer/charts"
mkdir -p "${CLAUDE_DIR}/skills/sector-scanner/cache"
mkdir -p "${CLAUDE_DIR}/skills/etf-analyzer/cache"
mkdir -p "${CLAUDE_DIR}/skills/etf-backtest/charts"

cat <<EOF

==> Done. Seven skills installed.

    yfinance-backed (no API key needed):
      stock-analyzer    — single ticker + 15 technical indicators + chart + sentiment
      sector-scanner    — sector / ETF momentum ranking + sentiment overlay (SPDR + UCITS universes)
      etf-analyzer      — ETF deep-dive (holdings, sectors, AUM, drawdown) + --compare overlap mode
      etf-backtest      — single ETF or basket backtest with drawdown chart

    Anthropic-hosted wrappers (need ANTHROPIC_API_KEY exported):
      finance-xlsx, finance-pptx, finance-pdf

    For finance-*, export your Anthropic key:
      export ANTHROPIC_API_KEY=sk-ant-...
      # add to ~/.zshrc or ~/.bashrc to persist

    Restart Claude Code (CLI or VS Code) to pick up the new skills.

    Smoke tests:
      ~/.claude/skills/stock-analyzer/run.sh --ticker AAPL --technical --no-chart --no-sentiment
      ~/.claude/skills/sector-scanner/run.sh --ucits --no-sentiment --top 5
      ~/.claude/skills/etf-analyzer/run.sh --ticker AINF.L
      ~/.claude/skills/etf-backtest/run.sh --tickers SWDA.L --period 5y --no-chart

EOF
