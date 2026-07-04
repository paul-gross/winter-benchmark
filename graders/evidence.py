#!/usr/bin/env python3
"""'Did they run it?' evidence capture (informative signals, never the arbiter).

Combines a transcript scan, capability-matrix detection in the agent's final
message, and the runtime DB/broker figures the runner snapshots from the
agent's environment before teardown. A convincing capability matrix can never
outweigh a failed hidden check.

Usage:
    evidence.py --transcript T --final-message M --prompt-file P \
                [--db-user-rows N] [--db-worker-rows N] [--broker-deliveries N]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# Service-launch markers: any of these in the transcript indicates the agent
# actually started/exercised the stack (uvicorn/./up/docker/vite/curl/etc.).
LAUNCH_MARKERS = re.compile(
    r"(uvicorn|python -m app|python -m worker|npm run dev|vite\b|\./up\b"
    r"|winter service up|docker (run|compose|exec)|curl |httpx|playwright"
    r"|localhost:\d+/api/)",
    re.IGNORECASE,
)

# A capability matrix row: a markdown table row, or a checklist row that pairs
# a requirement with a verification method.
TABLE_ROW = re.compile(r"^\s*\|.+\|.+\|", re.MULTILINE)
METHOD_WORDS = re.compile(
    r"(curl|GET|POST|DELETE|http|psql|SELECT|query|clicked?|browser|UI|page"
    r"|request|command|observed|verified)",
    re.IGNORECASE,
)


def requirement_bullets(prompt_text: str) -> list[str]:
    """The prompt's requirement bullets (between 'Requirements'-ish start and
    the delivery-expectations block)."""
    body = prompt_text.split("Delivery expectations:")[0]
    return [
        m.group(1).strip()
        for m in re.finditer(r"^- (.+(?:\n  .+)*)", body, re.MULTILINE)
    ]


def keyword_set(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{4,}", text)}


def matrix_coverage(final_message: str, prompt_text: str) -> tuple[bool, float | None]:
    rows = [r for r in TABLE_ROW.findall(final_message) if METHOD_WORDS.search(r)]
    present = len(rows) >= 2  # more than a header line
    if not present:
        return False, None
    requirements = requirement_bullets(prompt_text)
    if not requirements:
        return present, None
    matrix_words = keyword_set("\n".join(rows))
    covered = sum(
        1
        for req in requirements
        if len(keyword_set(req) & matrix_words) >= 2
    )
    return present, round(covered / len(requirements), 4)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--final-message", type=Path, required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--db-user-rows", type=int, default=0)
    parser.add_argument("--db-worker-rows", type=int, default=0)
    parser.add_argument("--broker-deliveries", type=int, default=0)
    args = parser.parse_args()

    transcript = args.transcript.read_text(errors="replace") if args.transcript.exists() else ""
    final_message = (
        args.final_message.read_text(errors="replace") if args.final_message.exists() else ""
    )
    present, coverage = matrix_coverage(final_message, args.prompt_file.read_text())

    print(
        json.dumps(
            {
                "app_launched": bool(LAUNCH_MARKERS.search(transcript)),
                "db_user_rows": args.db_user_rows,
                "db_worker_rows": args.db_worker_rows,
                "broker_deliveries": args.broker_deliveries,
                "capability_matrix_present": present,
                "capability_matrix_coverage": coverage,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
