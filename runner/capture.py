"""Per-run artifact capture (protocol §Per-run artifact manifest).

Everything here is best-effort observation of the agent's runtime environment,
snapshotted BEFORE teardown so the "did they run it" evidence survives. Grading
correctness never depends on these — the graders relaunch the final code
themselves.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

POLY_REPOS = ["wts-web", "wts-api", "wts-worker", "wts-persistence", "wts-messaging"]


def sh(cmd: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def repo_paths(cell_dir: Path, topology: str, condition: str) -> dict[str, Path]:
    """Where the agent's repositories live inside a built cell."""
    if condition == "plain":
        if topology == "mono":
            return {"winter-test-service": cell_dir / "winter-test-service"}
        return {name: cell_dir / "wts" / name for name in POLY_REPOS}
    env_dir = cell_dir / "workspace" / "alpha"
    if topology == "mono":
        return {"winter-test-service": env_dir / "winter-test-service"}
    return {name: env_dir / name for name in POLY_REPOS}


def capture_diffs(repos: dict[str, Path], out_dir: Path) -> None:
    """Final-state diff per repo: master vs the working tree (committed +
    uncommitted), so the judge sees exactly what the run left behind."""
    diff_dir = out_dir / "diff"
    diff_dir.mkdir(parents=True, exist_ok=True)
    for name, repo in repos.items():
        result = sh(["git", "-C", str(repo), "diff", "master"])
        (diff_dir / f"{name}.patch").write_text(result.stdout)


def _container_exists(name: str) -> bool:
    result = sh(["docker", "inspect", name])
    return result.returncode == 0


def capture_db(out_dir: Path, condition: str) -> dict:
    """Snapshot the agent's runtime items table (rows + schema)."""
    db_dir = out_dir / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    candidates = (
        [("wtsb-postgres", "wts_alpha", "wts")]
        if condition != "plain"
        else [("wts-db", "wts", "wts"), ("wtsb-postgres", "wts_alpha", "wts")]
    )
    for container, db, user in candidates:
        if not _container_exists(container):
            continue
        rows = sh(["docker", "exec", container, "psql", "-U", user, "-d", db, "-tAc",
                   "COPY (SELECT * FROM items ORDER BY id) TO STDOUT WITH CSV HEADER"])
        if rows.returncode != 0:
            continue
        (db_dir / "items.csv").write_text(rows.stdout)
        schema = sh(["docker", "exec", container, "pg_dump", "-U", user, "-d", db,
                     "--schema-only", "-t", "items"])
        (db_dir / "schema.sql").write_text(schema.stdout)
        counts = {}
        for source in ("api", "worker"):
            got = sh(["docker", "exec", container, "psql", "-U", user, "-d", db, "-tAc",
                      f"SELECT count(*) FROM items WHERE source='{source}'"])
            counts[source] = int(got.stdout.strip() or 0) if got.returncode == 0 else 0
        return {"found": True, "container": container, "db": db,
                "user_rows": counts["api"], "worker_rows": counts["worker"]}
    return {"found": False, "user_rows": 0, "worker_rows": 0}


def capture_broker(out_dir: Path, condition: str) -> dict:
    """Snapshot the agent's runtime broker state (queue depths per vhost)."""
    broker_dir = out_dir / "broker"
    broker_dir.mkdir(parents=True, exist_ok=True)
    candidates = (
        [("wtsb-rabbitmq", "wts-alpha")]
        if condition != "plain"
        else [("wts-rabbitmq", "/"), ("wtsb-rabbitmq", "wts-alpha")]
    )
    for container, vhost in candidates:
        if not _container_exists(container):
            continue
        result = sh(["docker", "exec", container, "rabbitmqctl", "list_queues",
                     "-p", vhost, "name", "messages", "--quiet"], timeout=120)
        if result.returncode != 0:
            continue
        queues = {}
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) == 2 and not line.startswith("name"):
                queues[parts[0]] = int(parts[1])
        stats = {"found": True, "container": container, "vhost": vhost,
                 "queues": queues, "deliveries": sum(queues.values())}
        (broker_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
        return stats
    stats = {"found": False, "queues": {}, "deliveries": 0}
    (broker_dir / "stats.json").write_text(json.dumps(stats, indent=2) + "\n")
    return stats


def extract_capability_matrix(final_message: str, out_dir: Path) -> None:
    """Pull markdown tables out of the final message as the capability-matrix
    artifact (detection/coverage scoring lives in graders/evidence.py)."""
    tables = re.findall(r"(?:^\|.*\|\s*$\n?)+", final_message, re.MULTILINE)
    (out_dir / "capability-matrix.md").write_text("\n\n".join(tables) if tables else "")


def snapshot_submission(repos: dict[str, Path], dest: Path, topology: str) -> Path:
    """A freshly-launchable copy of the agent's final code: clone (history +
    branch) then overlay the working tree, so uncommitted state is graded too
    while diff-based structural checks keep real git history."""
    dest.mkdir(parents=True, exist_ok=True)
    for name, repo in repos.items():
        target = dest / (name if topology == "poly" else "")
        target = dest / name if topology == "poly" else dest / "winter-test-service"
        sh(["git", "clone", "--no-hardlinks", "--quiet", str(repo), str(target)], timeout=300)
        # Graded diffs compare against master; make sure it exists locally.
        if sh(["git", "-C", str(target), "rev-parse", "--verify", "refs/heads/master"]).returncode != 0:
            sh(["git", "-C", str(target), "branch", "master", "origin/master"])
        sh([
            "rsync", "-a", "--delete",
            "--exclude", ".git", "--exclude", ".venv", "--exclude", "node_modules",
            "--exclude", "__pycache__", "--exclude", ".winter",
            f"{repo}/", f"{target}/",
        ], timeout=600)
    return dest if topology == "poly" else dest / "winter-test-service"
