#!/usr/bin/env python3
"""Aggregate benchmark results: the four-class distribution, sliced per #118.

    report.py --results-root results/<version> [--json out.json]

Reports the fully-achieved-unattended rate and the full class distribution by
experimental condition, topology, prompt type, and ordinary-vs-compound (the
compound task is reported separately so its scope does not obscure ordinary
performance). Efficiency fields are surfaced ONLY as a fairness audit — never
scored. Emits no comparative claim: whether one may be drawn depends on the
run design (the one-run-per-cell pilot may not).
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

CLASSES = [
    "fully_achieved_unattended",
    "partially_achieved_unattended",
    "not_achieved_unattended",
    "human_intervention_required",
]


def load_results(results_root: Path) -> list[dict]:
    return [
        json.loads(p.read_text())
        for p in sorted((results_root / "runs").glob("*/result.json"))
    ]


def distribution(results: list[dict]) -> dict:
    counts = Counter(r["result_class"] for r in results)
    total = len(results)
    return {
        "runs": total,
        "fully_achieved_rate": round(counts[CLASSES[0]] / total, 4) if total else None,
        "distribution": {c: counts.get(c, 0) for c in CLASSES},
    }


def slice_by(results: list[dict], key) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[key(r)].append(r)
    return {name: distribution(rs) for name, rs in sorted(groups.items())}


def fairness_audit(results: list[dict]) -> dict:
    """Efficiency fields by condition — recorded to reveal accidental
    differences (one condition getting more runtime/context), never scored."""
    audit: dict[str, dict] = {}
    by_condition: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_condition[r["cell"]["condition"]].append(r["efficiency"])
    for condition, effs in sorted(by_condition.items()):
        def med(field: str):
            values = [e.get(field) for e in effs if isinstance(e.get(field), (int, float))]
            return round(statistics.median(values), 1) if values else None
        audit[condition] = {
            "median_wall_clock_seconds": med("wall_clock_seconds"),
            "median_tokens_output": med("tokens_output"),
            "median_commands": med("commands_executed"),
            "median_failed_commands": med("failed_commands"),
        }
    return audit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="also write the report as JSON")
    args = parser.parse_args()

    results = load_results(args.results_root)
    report = {
        "results_root": str(args.results_root),
        "runs_recorded": len(results),
        "note": (
            "No comparative claim is drawn from a one-run-per-cell pilot; "
            "comparative claims require the frozen benchmark with a "
            "predeclared repetition count (protocol §Pilot)."
        ),
        "overall": distribution(results),
        "by_condition": slice_by(results, lambda r: r["cell"]["condition"]),
        "by_topology": slice_by(results, lambda r: r["cell"]["topology"]),
        "by_prompt": slice_by(results, lambda r: r["cell"]["prompt"]),
        "ordinary_vs_compound": slice_by(
            results,
            lambda r: "compound" if r["cell"]["prompt"] == "t5-compound" else "ordinary",
        ),
        "per_cell": {
            r["run_id"]: r["result_class"] for r in results
        },
        "efficiency_fairness_audit_not_scored": fairness_audit(results),
    }
    text = json.dumps(report, indent=2)
    if args.json:
        args.json.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
