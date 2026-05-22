#!/usr/bin/env python3
"""Run an Anthropic-hosted skill (xlsx, pptx, pdf) and download its output files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from anthropic import Anthropic  # noqa: E402
from file_utils import download_all_files, print_download_summary  # noqa: E402

VALID_SKILLS = ("xlsx", "pptx", "pdf")
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
BETAS = [
    "code-execution-2025-08-25",
    "files-api-2025-04-14",
    "skills-2025-10-02",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skill", required=True, choices=VALID_SKILLS)
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--prompt", help="Prompt text passed inline")
    src.add_argument("--prompt-file", help="Path to file containing the prompt")
    p.add_argument("--output-dir", default="./outputs")
    p.add_argument("--prefix", default="")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--max-tokens", type=int, default=4096)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY is not set in the environment.", file=sys.stderr)
        return 2

    prompt = (
        Path(args.prompt_file).expanduser().read_text()
        if args.prompt_file
        else args.prompt
    )

    client = Anthropic()
    skills = [{"type": "anthropic", "skill_id": args.skill, "version": "latest"}]

    print(
        f"[finance-skills] skill={args.skill} model={args.model} "
        f"max_tokens={args.max_tokens}",
        file=sys.stderr,
    )

    response = client.beta.messages.create(
        model=args.model,
        max_tokens=args.max_tokens,
        container={"skills": skills},
        tools=[{"type": "code_execution_20250825", "name": "code_execution"}],
        messages=[{"role": "user", "content": prompt}],
        betas=BETAS,
    )

    for block in response.content:
        if getattr(block, "type", None) == "text":
            print(block.text)

    print(
        f"\n[tokens] in={response.usage.input_tokens} "
        f"out={response.usage.output_tokens}",
        file=sys.stderr,
    )

    out_dir = str(Path(args.output_dir).expanduser().resolve())
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    results = download_all_files(
        client, response, output_dir=out_dir, prefix=args.prefix
    )
    print_download_summary(results)

    saved = [r["output_path"] for r in results if r["success"]]
    print("\n--- RESULT_JSON ---")
    print(
        json.dumps(
            {
                "skill": args.skill,
                "model": args.model,
                "output_files": saved,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "stop_reason": response.stop_reason,
            },
            indent=2,
        )
    )

    return 0 if saved else 1


if __name__ == "__main__":
    sys.exit(main())
