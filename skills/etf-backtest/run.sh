#!/bin/bash
set -euo pipefail
SKILL_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PY="${SKILL_DIR}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: venv missing at ${SKILL_DIR}/.venv" >&2
  echo "Recreate with:" >&2
  echo "  python3 -m venv ${SKILL_DIR}/.venv && ${SKILL_DIR}/.venv/bin/pip install yfinance pandas numpy matplotlib" >&2
  exit 1
fi
exec "$PY" "${SKILL_DIR}/scripts/backtest.py" "$@"
