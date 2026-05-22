#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PY="${SCRIPT_DIR}/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "ERROR: venv missing at ${SCRIPT_DIR}/.venv" >&2
  echo "Recreate with:" >&2
  echo "  python3 -m venv ${SCRIPT_DIR}/.venv && ${SCRIPT_DIR}/.venv/bin/pip install --upgrade anthropic" >&2
  exit 1
fi
exec "$PY" "${SCRIPT_DIR}/run_skill.py" "$@"
