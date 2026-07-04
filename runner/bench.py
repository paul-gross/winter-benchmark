#!/usr/bin/env python3
"""bench — run one benchmark cell end to end: reset → launch → capture → grade → emit.

    bench.py run --topology mono|poly --condition plain|winter|winter-workflow \
                 --prompt <id> --model <id> --host claude|codex|opencode|fake

One invocation = one cell. Results are durable per run (checkpoint/resume: an
existing result.json skips the cell unless --force), so a batch can stop at a
weekly quota and resume after reset.

Isolation: --sandbox docker runs the whole cell inside a disposable privileged
container (its own docker daemon, network policy, and credential mounts — see
sandbox/); --sandbox none executes on the host and exists for harness
development only. Real benchmark runs use the sandbox; `none` refuses
concurrent winter cells (fixed wtsb namespace) by design.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
BENCH = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BENCH / "judge"))

import capture  # noqa: E402
from hosts import HOSTS, HostRequest  # noqa: E402
from judge import classify as judge_classify  # noqa: E402

PROMPTS = [
    "t1-delete-item",
    "t2-worker-liveness",
    "t3-rename-label-title",
    "t4-repository-split",
    "t5-compound",
]


def log(msg: str) -> None:
    print(f"[bench] {msg}", file=sys.stderr)


def sh(cmd: list[str], cwd: Path | None = None, timeout: float | None = None,
       check: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        raise SystemExit(f"command failed ({' '.join(map(str, cmd))}):\n{result.stdout}{result.stderr}")
    return result


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def prepull_images() -> None:
    """Fairness: no cell pays a first-pull network cost."""
    for image in ("postgres:16", "rabbitmq:3-management"):
        sh(["docker", "pull", "-q", image], timeout=600)


def reset_cell(cell_dir: Path, topology: str, condition: str, sources_dir: Path) -> dict:
    if cell_dir.exists():
        shutil.rmtree(cell_dir)
    cell_dir.mkdir(parents=True)
    cmd = [
        sys.executable, str(BENCH / "environments" / "build_env.py"),
        "--topology", topology, "--condition", condition,
        "--dest", str(cell_dir), "--sources-dir", str(sources_dir),
    ]
    if condition != "plain":
        cmd.append("--bootstrap")
    log(f"reset: {' '.join(cmd[1:])}")
    result = sh(cmd, timeout=3600)
    if result.returncode != 0:
        raise SystemExit(f"reset failed:\n{result.stdout[-2000:]}{result.stderr[-2000:]}")
    return json.loads((cell_dir / "env-manifest.json").read_text())


def cleanup_cell(cell_dir: Path, condition: str, keep: bool) -> None:
    """Disposability: return the host to a clean state after capture."""
    workspace = cell_dir / "workspace"
    if condition != "plain" and workspace.exists():
        for scope in ("alpha", "workspace"):
            sh(["winter", "service", "down", scope], cwd=workspace, timeout=300)
        sh(["docker", "volume", "rm", "wtsb-workspace_postgres-data"])
    else:
        sh(["docker", "rm", "-f", "wts-db", "wts-rabbitmq"])
    # Any process the agent left running inside the cell tree.
    sh(["pkill", "-f", str(cell_dir)])
    if not keep:
        shutil.rmtree(cell_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Grade + judge
# ---------------------------------------------------------------------------


def run_graders(submission: Path, topology: str, prompt: str, run_dir: Path) -> dict:
    result = sh(
        ["uv", "run", "python", "grade.py",
         "--submission", str(submission), "--topology", topology,
         "--prompt", prompt, "--out", str(run_dir)],
        cwd=BENCH / "graders", timeout=3600,
    )
    grade_file = run_dir / "grade-result.json"
    if not grade_file.exists():
        raise SystemExit(f"grader crashed:\n{result.stdout[-2000:]}{result.stderr[-2000:]}")
    return json.loads(grade_file.read_text())


def run_judge(run_dir: Path, anonymized_dir: Path) -> dict | None:
    blind = sh(
        [sys.executable, str(BENCH / "judge" / "judge.py"), "blind",
         "--run-dir", str(run_dir), "--out", str(anonymized_dir / "tmp-package")],
        timeout=120,
    )
    if blind.returncode != 0:
        log(f"blinding failed: {blind.stderr[-500:]}")
        return None
    blind_id = blind.stdout.strip()
    package = anonymized_dir / blind_id
    if package.exists():
        shutil.rmtree(package)
    (anonymized_dir / "tmp-package").rename(package)

    score = sh(
        [sys.executable, str(BENCH / "judge" / "judge.py"), "score",
         "--package", str(package), "--out", str(run_dir / "judge-result.json")],
        timeout=1200,
    )
    if score.returncode != 0:
        log(f"judge failed: {score.stderr[-500:]}")
        return None
    return json.loads((run_dir / "judge-result.json").read_text())


def app_docs(repos: dict[str, Path], topology: str) -> str:
    if topology == "mono":
        repo = next(iter(repos.values()))
        result = sh(["git", "-C", str(repo), "show", "master:README.md"])
        return result.stdout
    sys.path.insert(0, str(BENCH / "derive-poly"))
    from derive_poly import PARENT_README  # noqa: PLC0415
    return PARENT_README


# ---------------------------------------------------------------------------
# The cell
# ---------------------------------------------------------------------------


def run_cell(args: argparse.Namespace) -> Path:
    run_id = (
        f"{args.topology}-{args.condition}-{args.prompt}-{args.model}"
        f"-{args.host}-r{args.repetition}"
    )
    version = (BENCH / "VERSION").read_text().strip()
    results_root = args.results_root or BENCH / "results" / version
    run_dir = results_root / "runs" / run_id
    anonymized = results_root / "anonymized"
    anonymized.mkdir(parents=True, exist_ok=True)

    if (run_dir / "result.json").exists() and not args.force:
        log(f"{run_id}: result exists — skipping (checkpoint/resume; --force to redo)")
        return run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.sandbox == "docker":
        return run_in_sandbox(args, run_id, run_dir)

    if args.condition != "plain" and args.sandbox == "none":
        log("WARNING: --sandbox none is for harness development only; winter cells "
            "use the fixed wtsb namespace — never run two concurrently on one host")

    work_root = Path(args.work_root or tempfile.mkdtemp(prefix=f"bench-{run_id}-"))
    cell_dir = work_root / "cell"
    prompt_text = (BENCH / "prompts" / f"{args.prompt}.md").read_text()
    started_at = datetime.now(timezone.utc)

    # 1. RESET ---------------------------------------------------------------
    prepull_images()
    manifest = reset_cell(cell_dir, args.topology, args.condition, args.sources_dir)
    agent_root = Path(manifest["agent_root"]).resolve()

    try:
        # 2. LAUNCH — unattended; nothing follows the initial prompt ----------
        adapter = HOSTS[args.host]()
        log(f"launch: host={args.host} model={args.model} cwd={agent_root}")
        host_result = adapter.run(HostRequest(
            workdir=agent_root,
            prompt=prompt_text,
            model=args.model,
            max_seconds=args.max_run_minutes * 60,
            out_dir=run_dir,
        ))

        # 3. CAPTURE — before any teardown ------------------------------------
        log("capture: diffs, delivery, db, broker, capability matrix")
        repos = capture.repo_paths(cell_dir, args.topology, args.condition)
        capture.capture_diffs(repos, run_dir)
        sys.path.insert(0, str(BENCH / "graders"))
        import delivery as delivery_mod  # noqa: PLC0415
        import evidence as evidence_mod  # noqa: PLC0415
        delivery = delivery_mod.collect(repos, args.topology)
        (run_dir / "delivery.json").write_text(json.dumps(delivery, indent=2) + "\n")
        db_stats = capture.capture_db(run_dir, args.condition)
        broker_stats = capture.capture_broker(run_dir, args.condition)
        capture.extract_capability_matrix(host_result.final_message, run_dir)
        (run_dir / "prompt.md").write_text(prompt_text)
        (run_dir / "app-docs.md").write_text(app_docs(repos, args.topology))

        matrix_present, matrix_coverage = evidence_mod.matrix_coverage(
            host_result.final_message, prompt_text
        )
        transcript_text = (
            host_result.transcript_path.read_text(errors="replace")
            if host_result.transcript_path and host_result.transcript_path.exists()
            else ""
        )
        evidence = {
            "app_launched": bool(evidence_mod.LAUNCH_MARKERS.search(transcript_text)),
            "db_user_rows": db_stats["user_rows"],
            "db_worker_rows": db_stats["worker_rows"],
            "broker_deliveries": broker_stats["deliveries"],
            "capability_matrix_present": matrix_present,
            "capability_matrix_coverage": matrix_coverage,
        }
        # Judge input (condition-neutral, deterministic) — see judge.py blind.
        (run_dir / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")

        # Stall refinement: a "completed" run that asks a question and delivered
        # nothing was actually awaiting input.
        stall_signal = host_result.stall_signal
        if (stall_signal == "completed" and not delivery["committed"]
                and host_result.final_message.rstrip().endswith("?")):
            stall_signal = "awaiting_input"
        stall = {"detected": stall_signal != "completed", "signal": stall_signal if stall_signal != "completed" else "none"}

        # 4. GRADE — against a freshly launched copy of the final code --------
        log("grade: hidden suite against a fresh copy")
        submission = capture.snapshot_submission(repos, work_root / "submission", args.topology)
        grade = run_graders(submission, args.topology, args.prompt, run_dir)

        # 5. JUDGE + classify --------------------------------------------------
        judge_result = None
        if not args.skip_judge and not stall["detected"]:
            log("judge: blinded qualitative pass")
            judge_result = run_judge(run_dir, anonymized)
        result_class = judge_classify(
            engineering_intervention=args.engineering_intervention,
            stall_detected=stall["detected"],
            required_failed=grade.get("required_failed", []),
            judge=judge_result,
            delivered_anything=bool((grade.get("delivery") or {}).get("diff_non_empty")),
        )

        # 6. EMIT ---------------------------------------------------------------
        result = {
            "schema_version": 1,
            "benchmark_version": version,
            "run_id": run_id,
            "created_at": started_at.isoformat(),
            "cell": {
                "topology": args.topology,
                "condition": args.condition,
                "prompt": args.prompt,
                "model": args.model,
                "host": args.host,
                "host_version": host_result.host_version,
                "repetition": args.repetition,
            },
            "pins": {"mono_sha": manifest["pins"]["winter-test-service"]},
            "result_class": result_class,
            "intervention": {
                "engineering_intervention": args.engineering_intervention,
                "events": [],
            },
            "stall": stall,
            "checks": grade["checks"],
            "evidence": evidence,
            "delivery": {
                "committed": delivery["committed"],
                "branch_cohesion": delivery["branch_cohesion"],
                "repos": delivery["repos"],
            },
            "judge": judge_result,
            "efficiency": host_result.efficiency,
            "artifacts": {
                "transcript": "transcript.jsonl",
                "final_message": "final-message.md",
                "capability_matrix": "capability-matrix.md",
                "delivery": "delivery.json",
                "diff": "diff/",
                "db_snapshot": "db/",
                "broker_stats": "broker/stats.json",
            },
        }
        (run_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        log(f"{run_id}: {result_class}")
        print(json.dumps({"run_id": run_id, "result_class": result_class,
                          "required_failed": grade.get("required_failed", []),
                          "run_dir": str(run_dir)}, indent=2))
    finally:
        cleanup_cell(cell_dir, args.condition, args.keep_cell)
        if not args.keep_cell and args.work_root is None:
            shutil.rmtree(work_root, ignore_errors=True)
    return run_dir


# ---------------------------------------------------------------------------
# Docker sandbox delegation
# ---------------------------------------------------------------------------


def run_in_sandbox(args: argparse.Namespace, run_id: str, run_dir: Path) -> Path:
    """Delegate the whole cell into a disposable privileged container with its
    own docker daemon. The bench tree mounts read-only; only the results dir
    and the cell workdir are writable; host credentials mount read-only."""
    image = "winter-bench-sandbox"
    if sh(["docker", "image", "inspect", image]).returncode != 0:
        log(f"building sandbox image {image}")
        sh(["docker", "build", "-t", image, str(HERE / "sandbox")], timeout=1800, check=True)
    workspace_src = args.sources_dir.resolve()
    # Worktree checkouts have a `.git` FILE pointing outside the mount; the
    # sandbox needs self-contained clones (e.g. the workspace's projects/ dir).
    for child in workspace_src.iterdir():
        if (child / ".git").is_file():
            raise SystemExit(
                f"--sources-dir {workspace_src} contains git worktrees ({child.name}); "
                "the docker sandbox needs real clones — pass the workspace's "
                "projects/ directory instead"
            )
    creds = Path.home() / ".claude"
    version = (BENCH / "VERSION").read_text().strip()
    results_root = (args.results_root or BENCH / "results" / version).resolve()
    cmd = [
        "docker", "run", "--rm", "--privileged",
        "--name", f"bench-{run_id}",
        # Anonymous volume: the inner docker daemon needs a real filesystem
        # (overlay-on-overlay cannot extract whiteouts); removed with --rm.
        "-v", "/var/lib/docker",
        "-v", f"{BENCH.resolve()}:/bench-src:ro",   # harness code: read-only
        "-v", f"{workspace_src}:/sources:ro",       # pinned sources: read-only
        "-v", f"{results_root}:/results",           # the only writable host mount
        "-v", f"{creds}:/root/.claude",             # subscription credential (held constant)
        *(
            ["-e", f"BENCH_FAKE_SCRIPT={os.environ['BENCH_FAKE_SCRIPT']}"]
            if args.host == "fake" and os.environ.get("BENCH_FAKE_SCRIPT")
            else []
        ),
        image,
        "bash", "-lc",
        " && ".join([
            "dockerd >/var/log/dockerd.log 2>&1 & timeout 90 sh -c 'until docker info >/dev/null 2>&1; do sleep 1; done'",
            "git config --global --add safe.directory '*'",  # host mounts owned by another uid
            "git config --global user.name bench && git config --global user.email bench@bench.invalid",
            "mkdir -p /work && cp -r /bench-src /work/bench",  # graders need a writable tree
            " ".join([
                "python3 /work/bench/runner/bench.py run",
                f"--topology {args.topology} --condition {args.condition}",
                f"--prompt {args.prompt} --model {args.model} --host {args.host}",
                f"--repetition {args.repetition}",
                f"--max-run-minutes {args.max_run_minutes}",
                "--sandbox none --sources-dir /sources",
                "--results-root /results --work-root /work/cell-root --force",
                *(["--skip-judge"] if args.skip_judge else []),
                *(["--keep-cell"] if args.keep_cell else []),
            ]),
        ]),
    ]
    log("sandbox: delegating cell into container (unvalidated path — verify before pilot)")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise SystemExit(f"sandboxed cell failed with exit {result.returncode}")
    return run_dir


def run_batch(args: argparse.Namespace) -> None:
    """Thin driver over the 30-cell matrix. Sequential by design (one sandbox
    at a time keeps the fairness controls simple); checkpoint/resume comes for
    free because completed cells skip. Stop any time; re-run to continue."""
    cells = [
        (topology, condition, prompt)
        for prompt in PROMPTS
        for topology in ("mono", "poly")
        for condition in ("plain", "winter", "winter-workflow")
    ]
    done = failed = 0
    for topology, condition, prompt in cells:
        cell_args = argparse.Namespace(**vars(args))
        cell_args.topology, cell_args.condition, cell_args.prompt = topology, condition, prompt
        try:
            run_cell(cell_args)
            done += 1
        except SystemExit as exc:
            failed += 1
            log(f"CELL FAILED ({topology}/{condition}/{prompt}): {exc}")
            if args.stop_on_failure:
                raise
    log(f"batch: {done} cells done/skipped, {failed} failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="run one cell")
    p.add_argument("--topology", choices=["mono", "poly"], required=True)
    p.add_argument("--condition", choices=["plain", "winter", "winter-workflow"], required=True)
    p.add_argument("--prompt", choices=PROMPTS, required=True)
    p.add_argument("--model", required=True, help="model parameter (haiku for dry-runs, sonnet for real runs)")
    p.add_argument("--host", choices=list(HOSTS), required=True)
    p.add_argument("--repetition", type=int, default=1)
    p.add_argument("--sandbox", choices=["docker", "none"], default="docker")
    p.add_argument("--max-run-minutes", type=int, default=90,
                   help="generous boundary used only to break a stuck run")
    p.add_argument("--sources-dir", type=Path, default=BENCH.parents[1],
                   help="directory containing the pinned source checkouts (see environments/)")
    p.add_argument("--results-root", type=Path, default=None)
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--force", action="store_true", help="re-run an already-recorded cell")
    p.add_argument("--keep-cell", action="store_true", help="keep the cell dir (debugging)")
    p.add_argument("--skip-judge", action="store_true", help="plumbing tests only")
    p.add_argument("--engineering-intervention", action="store_true",
                   help="mark that a human engineering intervention occurred (disqualifies)")
    p.set_defaults(func=run_cell)

    b = sub.add_parser("batch", help="drive all 30 pilot cells (resumable)")
    b.add_argument("--model", required=True)
    b.add_argument("--host", choices=list(HOSTS), default="claude")
    b.add_argument("--repetition", type=int, default=1)
    b.add_argument("--sandbox", choices=["docker", "none"], default="docker")
    b.add_argument("--max-run-minutes", type=int, default=90)
    b.add_argument("--sources-dir", type=Path, default=BENCH.parents[1])
    b.add_argument("--results-root", type=Path, default=None)
    b.add_argument("--work-root", type=Path, default=None)
    b.add_argument("--force", action="store_true")
    b.add_argument("--keep-cell", action="store_true")
    b.add_argument("--skip-judge", action="store_true")
    b.add_argument("--engineering-intervention", action="store_true", help=argparse.SUPPRESS)
    b.add_argument("--stop-on-failure", action="store_true")
    b.set_defaults(func=run_batch)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
