#!/usr/bin/env python3
"""Delivery gate + branch-cohesion capture (protocol §Delivery contract).

Deterministic: at least one commit on a non-default feature branch in every
touched repository, with a clean tree (uncommitted work is undelivered work).
Branch-name cohesion — poly: fraction of touched repos on the modal feature
branch name; mono: trivially 1.0 — is recorded for the judge, never gated.

Usage:
    delivery.py --topology mono --repo winter-test-service=/path/to/checkout
    delivery.py --topology poly --repo wts-api=/p/wts-api --repo wts-web=... ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path

DEFAULT_BRANCH = "master"


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {result.stderr}")
    return result.stdout.strip()


def inspect_repo(name: str, repo: Path) -> dict:
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    dirty = bool(git(repo, "status", "--porcelain"))
    merge_base = git(repo, "merge-base", DEFAULT_BRANCH, "HEAD")
    ahead_shas = [
        s for s in git(repo, "rev-list", f"{merge_base}..HEAD").splitlines() if s
    ]
    commits = [
        {"sha": sha, "message": git(repo, "log", "-1", "--format=%B", sha).strip()}
        for sha in ahead_shas
    ]
    diff = git(repo, "diff", f"{merge_base}...HEAD")
    diff_stat = git(repo, "diff", "--shortstat", f"{merge_base}...HEAD")
    touched = bool(ahead_shas) or dirty
    return {
        "repo": name,
        "touched": touched,
        "branch": branch,
        "default_branch": DEFAULT_BRANCH,
        "dirty": dirty,
        "commits": commits,
        "diff_stat": diff_stat,
        "diff_bytes": len(diff.encode()),
    }


def assess(repos: list[dict], topology: str) -> dict:
    touched = [r for r in repos if r["touched"]]
    committed = bool(touched) and all(
        r["commits"] and r["branch"] != DEFAULT_BRANCH and not r["dirty"]
        for r in touched
    )
    if not touched:
        cohesion = None
    elif topology == "mono":
        cohesion = 1.0 if committed else None
    else:
        names = [r["branch"] for r in touched if r["branch"] != DEFAULT_BRANCH]
        if not names:
            cohesion = None
        else:
            modal = Counter(names).most_common(1)[0][1]
            cohesion = round(modal / len(touched), 4)
    diff_non_empty = sum(r["diff_bytes"] for r in repos) > 0 or any(
        r["dirty"] for r in repos
    )
    for r in repos:
        r.pop("diff_bytes", None)
        r.pop("dirty", None)
    return {
        "committed": committed,
        "branch_cohesion": cohesion,
        "diff_non_empty": diff_non_empty,
        "repos": repos,
    }


def collect(repo_specs: dict[str, Path], topology: str) -> dict:
    return assess(
        [inspect_repo(name, path) for name, path in sorted(repo_specs.items())],
        topology,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", choices=["mono", "poly"], required=True)
    parser.add_argument(
        "--repo",
        action="append",
        required=True,
        metavar="NAME=PATH",
        help="Repository to inspect (repeatable)",
    )
    args = parser.parse_args()
    specs = {}
    for spec in args.repo:
        name, _, path = spec.partition("=")
        specs[name] = Path(path)
    print(json.dumps(collect(specs, args.topology), indent=2))


if __name__ == "__main__":
    main()
