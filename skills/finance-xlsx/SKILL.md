---
name: finance-xlsx
description: Generate financial Excel workbooks (P&L statements, portfolio analytics, KPI dashboards, sector allocation, YoY comparisons) via the Anthropic-hosted `xlsx` skill. Use when the user wants a real `.xlsx` file with sheets, formulas, formatting, and charts — not just a markdown table in chat. Requires ANTHROPIC_API_KEY in the environment.
---

# finance-xlsx

Wraps the Anthropic-hosted `xlsx` skill so it's invocable from Claude Code. The skill runs in Anthropic's code-execution container, builds the workbook (multiple sheets, formulas, conditional formatting, charts), then this wrapper downloads the result locally.

## Use this when

- "Build a quarterly P&L workbook in Excel..."
- "Create a portfolio holdings spreadsheet with charts..."
- "Make me an .xlsx of YoY revenue comparison with sector breakdown..."

Skip if the user only wants a quick view — print a markdown table in chat instead. Each call costs API tokens + code-execution time.

## How to invoke

1. Pin the output directory (default `./outputs/`, create if missing).
2. Write a complete prompt describing the workbook (sheets, columns, data, formulas, charts) to a temp file. Avoid inline `--prompt` for anything non-trivial — shell quoting will bite you.
3. Run:
   ```bash
   ~/.claude/scripts/finance-skills/run_skill.sh \
     --skill xlsx \
     --prompt-file <path/to/prompt.txt> \
     --output-dir <output-dir> \
     [--prefix <prefix_>]
   ```
4. Surface the saved file path to the user. On macOS, offer `open <path>`.

## Prereqs (one-time)

- `ANTHROPIC_API_KEY` exported in the shell (`export ANTHROPIC_API_KEY=sk-ant-...`).
- The venv at `~/.claude/scripts/finance-skills/.venv` with `anthropic` installed (already set up). The wrapper checks for this and prints recovery steps if missing.

## Cost / safety

Each invocation is a real Messages API call plus container time — real money for paying users. Confirm before kicking off multi-sheet jobs.
