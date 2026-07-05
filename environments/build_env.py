#!/usr/bin/env python3
"""Build one benchmark cell's starting environment from pinned clean state.

Produces one of the four environment definitions (paul-gross/winter#121):

    --topology mono --condition plain            plain monorepo baseline
    --topology poly --condition plain            plain polyrepo baseline
    --topology mono --condition winter[-workflow]  mono Winter workspace
    --topology poly --condition winter[-workflow]  poly Winter workspace

Everything is keyed to the SHAs in pins.toml. The builder first materializes
local pinned "origin" bare repos under <dest>/.origins (so clones never depend
on the network or on moving upstream branches), then constructs the cell:

- plain: pinned clone(s) with accurate task-neutral READMEs — no Winter context.
- winter: a workspace clone of the pinned winter framework revision with the
  benchmark workspace configuration committed on top; `--bootstrap` then runs
  `winter ws init` / `winter ws init alpha` / `winter service up workspace`
  / `winter provision alpha` to reach the prepared state.

The `winter` and `winter-workflow` conditions differ ONLY by the
winter-workflow extension block in .winter/config.toml.

Leak guard: the benchmark harness (prompts, hidden graders) lives in the
separate winter-benchmark repo and is never among the pinned sources, so it
cannot appear in any cell; the builder additionally deletes a stray bench/
tree before committing the workspace configuration as a belt-and-braces guard.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "derive-poly"))
from derive_poly import PARENT_README  # noqa: E402

PINS = tomllib.loads((HERE / "pins.toml").read_text())["pins"]
TEMPLATES = HERE / "workspace-template"

POLY_REPOS = ["wts-web", "wts-api", "wts-worker", "wts-persistence", "wts-messaging"]

WORKFLOW_BLOCK = """\
[[standalone_repository]]
name = "winter-workflow"
url = "{origin_dir}/winter-workflow.git"
path = ".winter/ext/workflow"
"""

# Task-neutral git identity applied to every agent-visible repo in every
# condition, so committing works identically everywhere.
GIT_IDENTITY = ("Dev", "dev@bench.invalid")


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise SystemExit(f"command failed ({' '.join(cmd)}):\n{result.stdout}{result.stderr}")
    return result


def set_identity(repo: Path) -> None:
    name, email = GIT_IDENTITY
    run(["git", "config", "user.name", name], cwd=repo)
    run(["git", "config", "user.email", email], cwd=repo)


def make_origin(source: Path, name: str, sha: str, origins: Path) -> Path:
    """Bare-clone `source` and pin master to `sha`."""
    bare = origins / f"{name}.git"
    if bare.exists():
        shutil.rmtree(bare)
    run(["git", "clone", "--bare", "--quiet", "--no-hardlinks", str(source), str(bare)])
    probe = run(["git", "-C", str(bare), "cat-file", "-e", f"{sha}^{{commit}}"], check=False)
    if probe.returncode != 0:
        raise SystemExit(
            f"{source} does not contain pinned commit {sha} for {name} — fetch it first"
        )
    run(["git", "-C", str(bare), "update-ref", "refs/heads/master", sha])
    run(["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/master"])
    return bare


def make_poly_origins(mono_source: Path, origins: Path) -> None:
    """Derive the poly fixture set and bare-clone each repo as a pinned origin."""
    poly_src = origins / "poly-src"
    if poly_src.exists():
        shutil.rmtree(poly_src)
    run(
        [
            sys.executable,
            str(HERE.parent / "derive-poly" / "derive_poly.py"),
            "--source", str(mono_source),
            "--out", str(poly_src),
            "--git",
            # Committed lockfiles, like the mono fixture's uv.lock: without
            # them the agent's first `uv sync` litters every Python repo with
            # an untracked uv.lock and the delivery gate reads it as dirty.
            "--lock",
        ]
    )
    for name in POLY_REPOS:
        bare = origins / f"{name}.git"
        if bare.exists():
            shutil.rmtree(bare)
        run(["git", "clone", "--bare", "--quiet", "--no-hardlinks", str(poly_src / name), str(bare)])
        run(["git", "-C", str(bare), "symbolic-ref", "HEAD", "refs/heads/master"])


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def build_plain_mono(dest: Path, origins: Path) -> Path:
    checkout = dest / "winter-test-service"
    run(["git", "clone", "--quiet", str(origins / "winter-test-service.git"), str(checkout)])
    set_identity(checkout)
    return checkout


def build_plain_poly(dest: Path, origins: Path) -> Path:
    parent = dest / "wts"
    parent.mkdir(parents=True, exist_ok=True)
    for name in POLY_REPOS:
        run(["git", "clone", "--quiet", str(origins / f"{name}.git"), str(parent / name)])
        set_identity(parent / name)
    (parent / "README.md").write_text(PARENT_README)
    return parent


def build_winter(dest: Path, origins: Path, topology: str, workflow: bool) -> Path:
    ws = dest / "workspace"
    run(["git", "clone", "--quiet", str(origins / "winter.git"), str(ws)])
    set_identity(ws)

    # Leak guard: the benchmark harness lives in the separate winter-benchmark
    # repo, so no winter pin can carry it here — but delete a stray bench/
    # tree defensively so hidden graders can never be agent-visible.
    if (ws / "bench").exists():
        shutil.rmtree(ws / "bench")

    config = (TEMPLATES / f"config.{topology}.toml").read_text()
    config = config.replace("{{ORIGIN_DIR}}", str(origins.resolve()))
    config = config.replace(
        "# {{WORKFLOW_EXTENSION}}",
        WORKFLOW_BLOCK.format(origin_dir=origins.resolve()) if workflow else "",
    )
    (ws / ".winter").mkdir(exist_ok=True)
    (ws / ".winter" / "config.toml").write_text(config)

    tmux_dir = ws / ".winter" / "config" / "winter-service-tmux"
    tmux_dir.mkdir(parents=True, exist_ok=True)
    (tmux_dir / "config.toml").write_text(
        (TEMPLATES / "service-tmux" / f"config.{topology}.toml").read_text()
    )
    hook = tmux_dir / "layout-hook.sh"
    hook.write_text((TEMPLATES / "service-tmux" / "layout-hook.sh").read_text())
    hook.chmod(0o755)

    docker_dir = ws / ".winter" / "config" / "winter-service-docker"
    docker_dir.mkdir(parents=True, exist_ok=True)
    (docker_dir / "config.toml").write_text(
        (TEMPLATES / "service-docker" / "config.toml").read_text()
    )
    (docker_dir / "workspace-compose.yaml").write_text(
        (TEMPLATES / "service-docker" / "workspace-compose.yaml").read_text()
    )

    project_dir = ws / "context" / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "index.md").write_text(
        (TEMPLATES / f"context-project-index.{topology}.md").read_text()
    )
    (project_dir / "contributing.md").write_text((TEMPLATES / "contributing.md").read_text())

    # AGENTS.md references @AGENTS.local.md; provide the (gitignored) user-local body.
    (ws / "AGENTS.local.md").write_text("# Local Settings\n\n(none)\n")

    run(["git", "add", "-A"], cwd=ws)
    run(
        [
            "git", "-c", "commit.gpgsign=false", "commit", "--quiet",
            "-m", "chore(workspace): benchmark workspace configuration",
        ],
        cwd=ws,
    )
    return ws


def bootstrap_winter(ws: Path) -> None:
    """Bring the workspace to the prepared state: repos cloned, env created,
    infra singletons up, per-env db/vhost provisioned. App services stay down —
    starting them is the agent's job."""
    if shutil.which("winter") is None:
        # Sandbox path: install the CLI from the workspace's own pinned source.
        installer = ws / "tools" / "winter-cli" / "install.sh"
        print(f"  bootstrap: installing winter via {installer}", file=sys.stderr)
        if subprocess.run(["bash", str(installer)], cwd=ws).returncode != 0 or shutil.which("winter") is None:
            raise SystemExit(
                "`winter` is not installed and self-install failed — run "
                f"{installer} manually (requires mise + uv)"
            )
    if shutil.which("mise"):
        run(["mise", "trust", "--quiet", str(ws / "tools" / "winter-cli")], check=False)
    for step in (
        ["winter", "ws", "init"],
        ["winter", "ws", "init", "alpha"],
        ["winter", "service", "up", "workspace", "--wait"],
        ["winter", "provision", "alpha"],
    ):
        print(f"  bootstrap: {' '.join(step)}", file=sys.stderr)
        result = subprocess.run(step, cwd=ws)
        if result.returncode != 0:
            raise SystemExit(f"bootstrap step failed: {' '.join(step)}")
    # Same task-neutral committer identity as the plain baselines. Repo config
    # is shared across a repo's worktrees, so setting it on each project clone
    # covers the feature-env worktrees too.
    projects = ws / "projects"
    if projects.exists():
        for repo in projects.iterdir():
            if (repo / ".git").exists():
                set_identity(repo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topology", choices=["mono", "poly"], required=True)
    parser.add_argument(
        "--condition", choices=["plain", "winter", "winter-workflow"], required=True
    )
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=HERE.parents[1],
        help="Directory containing local checkouts named winter, winter-test-service, "
        "winter-service-tmux, winter-service-docker, winter-workflow (each must "
        "contain its pinned commit). Default: the parent of the winter-benchmark "
        "checkout this script lives in.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="For winter conditions: run winter ws init / env init / service up "
        "workspace / provision to reach the prepared state",
    )
    args = parser.parse_args()

    dest: Path = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    origins = dest / ".origins"
    origins.mkdir(exist_ok=True)
    sources = args.sources_dir

    mono_source = sources / "winter-test-service"
    make_origin(mono_source, "winter-test-service", PINS["winter-test-service"], origins)
    if args.topology == "poly":
        make_poly_origins(mono_source, origins)

    if args.condition == "plain":
        root = (
            build_plain_mono(dest, origins)
            if args.topology == "mono"
            else build_plain_poly(dest, origins)
        )
    else:
        make_origin(sources / "winter", "winter", PINS["winter"], origins)
        for ext in ("winter-service-tmux", "winter-service-docker"):
            make_origin(sources / ext, ext, PINS[ext], origins)
        if args.condition == "winter-workflow":
            make_origin(sources / "winter-workflow", "winter-workflow", PINS["winter-workflow"], origins)
        root = build_winter(
            dest, origins, args.topology, workflow=args.condition == "winter-workflow"
        )
        if args.bootstrap:
            bootstrap_winter(root)

    manifest = {
        "topology": args.topology,
        "condition": args.condition,
        "agent_root": str(root),
        "pins": PINS,
    }
    (dest / "env-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
