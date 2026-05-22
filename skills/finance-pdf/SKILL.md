---
name: finance-pdf
description: Generate formal PDF financial documents (formal reports, technical documentation, process documentation) via the Anthropic-hosted `pdf` skill. Use when the user wants a polished `.pdf` deliverable — not just text in chat. Requires ANTHROPIC_API_KEY.
---

# finance-pdf

Wraps the Anthropic-hosted `pdf` skill. The skill assembles a formatted PDF in the API container, then this wrapper downloads it locally.

## Use this when

- "Compile this analysis into a formal PDF report..."
- "Generate a process documentation PDF for..."
- "Create a PDF deliverable from this draft..."

Skip if the user is still iterating on content — keep it as markdown until they're happy, then convert.

## How to invoke

1. Pin output directory (default `./outputs/`).
2. Write a complete prompt to a file — sections, headings, tables, any specific formatting requirements.
3. Run:
   ```bash
   ~/.claude/scripts/finance-skills/run_skill.sh \
     --skill pdf \
     --prompt-file <prompt-path> \
     --output-dir <out-dir> \
     [--prefix <prefix_>]
   ```
4. Report the saved `.pdf` path back to the user.

## Prereqs

Same as `finance-xlsx` — `ANTHROPIC_API_KEY` exported, venv populated at `~/.claude/scripts/finance-skills/.venv`.

## Cost

Real API + container call per invocation.
