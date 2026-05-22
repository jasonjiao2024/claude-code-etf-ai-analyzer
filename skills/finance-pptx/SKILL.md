---
name: finance-pptx
description: Generate financial PowerPoint decks (executive summaries, investment committee presentations, quarterly metrics, multi-slide reports with charts and corporate formatting) via the Anthropic-hosted `pptx` skill. Use when the user wants a real `.pptx` file — not just a bulleted outline in chat. Requires ANTHROPIC_API_KEY.
---

# finance-pptx

Wraps the Anthropic-hosted `pptx` skill. The skill renders the deck in the API container (slides, charts, formatting), then this wrapper downloads the result.

## Use this when

- "Build an investment committee deck on..."
- "Generate a Q1 metrics presentation with charts..."
- "Create an executive financial summary deck..."

Skip if the user only wants slide-by-slide bullet points — write those in chat directly.

## How to invoke

1. Pin output directory (default `./outputs/`).
2. Write a complete prompt to a file — slide-by-slide structure, title, key bullets, what each chart should show, target audience.
3. Run:
   ```bash
   ~/.claude/scripts/finance-skills/run_skill.sh \
     --skill pptx \
     --prompt-file <prompt-path> \
     --output-dir <out-dir> \
     [--prefix <prefix_>]
   ```
4. Surface the saved `.pptx` path. Offer `open <path>` on macOS.

## Prereqs

Same as `finance-xlsx` — `ANTHROPIC_API_KEY` exported, venv populated at `~/.claude/scripts/finance-skills/.venv`.

## Cost

Real API + container call per invocation. Confirm before generating large decks.
