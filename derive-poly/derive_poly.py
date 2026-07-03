#!/usr/bin/env python3
"""Derive the five-repository polyrepo fixture from winter-test-service.

The polyrepo is a pure function of the monorepo at a pinned commit plus the
split manifest (manifest.toml). Python/TS source is copied byte-identically —
only packaging metadata (pyproject.toml), READMEs, and .gitignore files are
synthesized — so equivalence between the topologies is a reproducibility
assertion, not a hand-maintained diff.

Usage:
    derive_poly.py --source <path-to-winter-test-service> --out <dir>
                   [--lock] [--git] [--verify-reproducible] [--parent-readme]
                   [--allow-unpinned]

The source tree is extracted with `git archive <pinned_sha>`, so a dirty
working tree never leaks into the fixture. Re-running against the same pinned
commit reproduces the output byte-for-byte (including git commit SHAs when
--git is used, thanks to fixed author/committer dates).

Caveat (documented, not hidden): a poly fixture freshly derived from one mono
commit is artificially clean — no version skew, no release-coordination
friction — so it may understate organic polyrepo difficulty. Acceptable for
v1: the topology effect under measurement is the agent's multi-repo
coordination at task time, which is present regardless of starting cleanliness.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from io import BytesIO
from pathlib import Path

MANIFEST = Path(__file__).parent / "manifest.toml"
GENERATOR_VERSION = "1"

# Fixed identity/date so --git produces identical commit SHAs on every run.
GIT_ENV = {
    "GIT_AUTHOR_NAME": "wts-fixture",
    "GIT_AUTHOR_EMAIL": "fixture@bench.invalid",
    "GIT_COMMITTER_NAME": "wts-fixture",
    "GIT_COMMITTER_EMAIL": "fixture@bench.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
}

PY_GITIGNORE = """\
# Python
.venv/
__pycache__/
*.pyc

# Local env overrides
.env
"""

NODE_GITIGNORE = """\
node_modules/
dist/

# Local env overrides
.env
"""


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> str:
    import os

    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    result = subprocess.run(
        cmd, cwd=cwd, env=full_env, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise SystemExit(
            f"command failed ({' '.join(cmd)}):\n{result.stdout}{result.stderr}"
        )
    return result.stdout


def extract_pinned_tree(source: Path, sha: str, dest: Path) -> None:
    """Extract exactly the pinned commit's tree, ignoring working-tree state."""
    archive = subprocess.run(
        ["git", "-C", str(source), "archive", sha],
        capture_output=True,
    )
    if archive.returncode != 0:
        raise SystemExit(
            f"git archive {sha} failed in {source}: "
            f"{archive.stderr.decode()}\n"
            "Is the source checkout missing the pinned commit? Try `git fetch`."
        )
    with tarfile.open(fileobj=BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------


def synth_pyproject(repo: dict) -> str:
    deps = ",\n".join(f'    "{d}"' for d in repo["dependencies"])
    lines = [
        "[project]",
        f'name = "{repo["name"]}"',
        'version = "0.1.0"',
        f'description = "{repo["description"]}"',
        'requires-python = ">=3.12"',
        "dependencies = [",
        deps + ",",
        "]",
        "",
    ]
    if repo["kind"] == "python-lib":
        lines += [
            "[build-system]",
            'requires = ["hatchling"]',
            'build-backend = "hatchling.build"',
            "",
            "[tool.hatch.build.targets.wheel]",
            f'packages = ["{repo["package"]}"]',
            "",
        ]
    else:  # python-app: run from source, uv manages the venv only
        lines += [
            "# An application, not a library: run from source via `uv run`.",
            "[tool.uv]",
            "package = false",
            "",
        ]
    sources = repo.get("sources", {})
    if sources:
        lines += ["[tool.uv.sources]"]
        for name, path in sorted(sources.items()):
            lines += [f'{name} = {{ path = "{path}" }}']
        lines += [""]
    return "\n".join(lines)


def synth_readme(repo: dict) -> str:
    name = repo["name"]
    sources = repo.get("sources", {})
    sibling_note = ""
    if sources:
        siblings = ", ".join(f"`{p}`" for p in sorted(sources.values()))
        sibling_note = (
            f"\nThis application depends on sibling checkouts ({siblings}) via uv"
            " path dependencies — clone the wts repositories side by side under"
            " one parent directory.\n"
        )

    if name == "wts-persistence":
        return f"""# {name}

{repo["description"]}: the `Item` domain model, the read/write repository
Protocol seams, and the SQLAlchemy adapters behind them. The api and worker
applications consume this library so they share one schema and one I/O boundary
instead of each hand-rolling SQL.

## Layout

- `wts_persistence/domain/` — the domain model and errors; no storage detail.
- `wts_persistence/repositories/` — the `IReadItemRepository` / `IWriteItemRepository` Protocol seams consumers depend on.
- `wts_persistence/internal/` — the SQLAlchemy engine, ORM entities, and repository adapters. Do not import from outside this package.

## Development

```sh
uv sync          # create the venv and install dependencies
```

Consumed by the sibling `wts-api` and `wts-worker` repositories as a uv path
dependency (`../wts-persistence`).
"""

    if name == "wts-messaging":
        return f"""# {name}

{repo["description"]}: the `IHeartbeatPublisher` Protocol seam and the pika AMQP
adapter behind it. The worker application consumes this library; pika is
confined to `wts_messaging/internal/`.

## Layout

- `wts_messaging/domain/` — messaging errors; no pika detail.
- `wts_messaging/publishers/` — the `IHeartbeatPublisher` Protocol seam consumers depend on.
- `wts_messaging/internal/` — the pika connection/publisher adapters. Do not import from outside this package.

## Development

```sh
uv sync          # create the venv and install dependencies
```

Consumed by the sibling `wts-worker` repository as a uv path dependency
(`../wts-messaging`).
"""

    if name == "wts-api":
        return f"""# {name}

{repo["description"]}: serves item read/create and health, and exposes
diagnostic (chaos) endpoints. Shares the persistence layer with the worker via
the sibling `wts-persistence` library.
{sibling_note}
## Configuration

Everything is an environment variable with a default; there is no config file.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://wts:wts@localhost:5545/wts` | database connection |
| `WTS_API_PORT` | `7503` | listen port |
| `WTS_API_HOST` | `0.0.0.0` | listen host |
| `WTS_BOOT_DELAY_SECONDS` | `0` | sleep this long before binding (simulate a slow boot) |

## Running

```sh
uv sync
uv run python -m app
```

The api creates the `items` table idempotently on startup:

```sql
CREATE TABLE IF NOT EXISTS items (
  id         BIGSERIAL PRIMARY KEY,
  label      TEXT NOT NULL,
  source     TEXT NOT NULL,           -- 'api' (user-added) or 'worker' (heartbeat)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## API

- `GET  /api/health` — `{{status, db}}`, where `db` is `ok` or `down`.
- `GET  /api/items` — recent items, newest first.
- `POST /api/items` — body `{{ "label": "..." }}`; inserts a `source='api'` row and returns it.
- `POST /api/chaos/crash` — hard-crash the api process (`os._exit(1)`).
- `POST /api/chaos/error-log?n=N` — write N error lines to stderr (default `5`).

Requests are logged to stdout; warnings and errors go to stderr.
"""

    if name == "wts-worker":
        return f"""# {name}

{repo["description"]}: a background loop that writes a heartbeat row to the
database on a fixed cadence and publishes each heartbeat to a RabbitMQ
`heartbeats` queue. Shares the persistence layer with the api via the sibling
`wts-persistence` library and the broker access via `wts-messaging`.
{sibling_note}
## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://wts:wts@localhost:5545/wts` | database connection |
| `WTS_WORKER_INTERVAL_SECONDS` | `2` | seconds between heartbeats |
| `WTS_WORKER_CRASH_AFTER` | `0` (never) | exit(1) after this many ticks |
| `RABBITMQ_URL` | derived | full AMQP URL — overrides the derived URL |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` | `localhost` / `5672` | broker host/port when `RABBITMQ_URL` is unset |

The broker is a **soft** dependency: if it can't be reached, the worker logs a
warning and keeps writing DB heartbeats, retrying the publish each tick.

## Running

```sh
uv sync
uv run python -m worker.main
```

## Messaging

Each heartbeat is published as a persistent JSON message (`{{env, tick, label}}`)
to a durable `heartbeats` queue in the resolved vhost.
"""

    if name == "wts-web":
        return f"""# {name}

{repo["description"]}: lists items, adds items, shows an API/DB health badge,
and can trigger a controlled API crash. Talks to the sibling api service via a
dev-server `/api` proxy.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `WTS_WEB_PORT` | `9000` | dev-server port |
| `WTS_API_PORT` | `7503` | the `/api` proxy target's port |

## Running

```sh
npm install
npm run dev
```

Open http://localhost:9000. Type-check and build with `npm run build`.
"""

    raise SystemExit(f"no README template for {name}")


PARENT_README = """\
# wts — polyrepo application

A small full-stack application — a React web UI, a FastAPI JSON API, a Postgres
database, and a background worker — that records and lists "items," split
across five repositories cloned side by side:

| Repository | What it is |
|------------|------------|
| `wts-web` | React + Vite single-page UI |
| `wts-api` | FastAPI/uvicorn JSON API |
| `wts-worker` | background heartbeat worker |
| `wts-persistence` | shared persistence/domain library (used by api + worker) |
| `wts-messaging` | shared messaging library (used by worker) |

The api and worker consume the two libraries as uv path dependencies
(`../wts-persistence`, `../wts-messaging`), so keep the five checkouts as
siblings under this directory.

## Running the stack locally

```sh
# 1. Start Postgres in Docker — first, in its own terminal
#    (publishes localhost:5545, persists data in the named volume wts-pgdata)
docker run --rm --name wts-db \\
  -e POSTGRES_USER=wts -e POSTGRES_PASSWORD=wts -e POSTGRES_DB=wts \\
  -p 5545:5432 -v wts-pgdata:/var/lib/postgresql/data postgres:16

# 1b. (optional) Start RabbitMQ for the worker's heartbeat publisher.
#     Without it the worker just logs publish warnings and keeps running.
docker run --rm --name wts-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# 2. Install dependencies and start each service — each in its own terminal
( cd wts-api && uv sync && uv run python -m app )
( cd wts-worker && uv sync && uv run python -m worker.main )
( cd wts-web && npm install && npm run dev )

# 3. Open the UI
open http://localhost:9000
```

Every setting is an environment variable with a sensible default — see each
repository's README for its configuration table and details.

## Requirements

- **Docker**
- **[uv](https://docs.astral.sh/uv/)** — Python environment and dependency manager. Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Python 3.12+
- Node 20+
"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def copy_tree(src: Path, dest: Path) -> list[Path]:
    """Copy src into dest, returning the copied files (relative to dest)."""
    copied: list[Path] = []
    if src.is_file():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        return [dest]
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            copied.append(target)
    return copied


def generate(source_tree: Path, out: Path, manifest: dict) -> dict:
    """Emit the five repos; return {repo_name: [copied source files]}."""
    out.mkdir(parents=True, exist_ok=True)
    copied_by_repo: dict[str, list[Path]] = {}
    for repo in manifest["repo"]:
        repo_dir = out / repo["name"]
        if repo_dir.exists():
            shutil.rmtree(repo_dir)
        repo_dir.mkdir(parents=True)
        copied: list[Path] = []
        for src_rel, dest_rel in repo["copy"]:
            copied += copy_tree(source_tree / src_rel, repo_dir / dest_rel)
        if repo.get("vendor_logging"):
            copied += copy_tree(source_tree / "wts_logging.py", repo_dir / "wts_logging.py")
        if repo["kind"] in ("python-lib", "python-app"):
            (repo_dir / "pyproject.toml").write_text(synth_pyproject(repo))
            (repo_dir / ".gitignore").write_text(PY_GITIGNORE)
        else:
            (repo_dir / ".gitignore").write_text(NODE_GITIGNORE)
        (repo_dir / "README.md").write_text(synth_readme(repo))
        copied_by_repo[repo["name"]] = copied
    return copied_by_repo


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source_identical(
    source_tree: Path, out: Path, manifest: dict, copied_by_repo: dict
) -> int:
    """Assert every copied file is byte-identical to its monorepo original."""
    count = 0
    for repo in manifest["repo"]:
        repo_dir = out / repo["name"]
        mappings = [(s, d) for s, d in repo["copy"]]
        if repo.get("vendor_logging"):
            mappings.append(("wts_logging.py", "wts_logging.py"))
        for src_rel, dest_rel in mappings:
            src_root = source_tree / src_rel
            dest_root = repo_dir / dest_rel
            files = [src_root] if src_root.is_file() else sorted(
                p for p in src_root.rglob("*") if p.is_file()
            )
            for src_file in files:
                rel = (
                    Path("")
                    if src_file == src_root
                    else src_file.relative_to(src_root)
                )
                dest_file = dest_root / rel if str(rel) else dest_root
                if sha256_file(src_file) != sha256_file(dest_file):
                    raise SystemExit(
                        f"NOT byte-identical: {dest_file} != mono {src_file}"
                    )
                count += 1
    return count


def write_fixture_metadata(out: Path, manifest: dict, source_identical: int) -> str:
    """Write checksums.txt + fixture-set.json; return the aggregate checksum."""
    lines = []
    agg = hashlib.sha256()
    for path in sorted(out.rglob("*")):
        if path.is_dir() or ".git/" in f"{path.relative_to(out)}/" or path.name in (
            "checksums.txt",
            "fixture-set.json",
        ):
            continue
        rel = path.relative_to(out)
        digest = sha256_file(path)
        lines.append(f"{digest}  {rel}")
        agg.update(f"{digest}  {rel}\n".encode())
    (out / "checksums.txt").write_text("\n".join(lines) + "\n")
    aggregate = agg.hexdigest()
    (out / "fixture-set.json").write_text(
        json.dumps(
            {
                "source_repo": manifest["source"]["repo"],
                "source_sha": manifest["source"]["pinned_sha"],
                "generator_version": GENERATOR_VERSION,
                "repos": [r["name"] for r in manifest["repo"]],
                "files": len(lines),
                "source_identical_files_verified": source_identical,
                "aggregate_sha256": aggregate,
            },
            indent=2,
        )
        + "\n"
    )
    return aggregate


def git_init_repos(out: Path, manifest: dict) -> None:
    sha = manifest["source"]["pinned_sha"]
    for repo in manifest["repo"]:
        repo_dir = out / repo["name"]
        run(["git", "init", "-q", "-b", "master"], cwd=repo_dir)
        run(["git", "add", "-A"], cwd=repo_dir)
        run(
            [
                "git",
                "-c", "commit.gpgsign=false",
                "commit", "-q",
                "-m", f"fixture: derived from winter-test-service@{sha}",
            ],
            cwd=repo_dir,
            env=GIT_ENV,
        )


def lock_repos(out: Path, manifest: dict) -> None:
    for repo in manifest["repo"]:
        if repo["kind"] in ("python-lib", "python-app"):
            print(f"  uv lock: {repo['name']}", file=sys.stderr)
            run(["uv", "lock"], cwd=out / repo["name"])


def tree_digest(root: Path) -> str:
    """Aggregate content digest of a tree (excluding .git)."""
    agg = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_dir() or ".git" in rel.parts:
            continue
        agg.update(f"{rel}\n".encode())
        agg.update(sha256_file(path).encode())
    return agg.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to a winter-test-service git checkout containing the pinned commit",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output parent directory")
    parser.add_argument(
        "--sha",
        default=None,
        help="Override the pinned commit (records drift from the manifest; use for testing only)",
    )
    parser.add_argument("--lock", action="store_true", help="Resolve a uv.lock per Python repo")
    parser.add_argument("--git", action="store_true", help="git-init each repo with a deterministic fixture commit")
    parser.add_argument(
        "--parent-readme",
        action="store_true",
        help="Also write the parent-directory README used by the plain-poly baseline",
    )
    parser.add_argument(
        "--verify-reproducible",
        action="store_true",
        help="Generate a second copy into a temp dir and assert byte-for-byte identity",
    )
    args = parser.parse_args()

    manifest = tomllib.loads(MANIFEST.read_text())
    if args.sha:
        manifest["source"]["pinned_sha"] = args.sha
    sha = manifest["source"]["pinned_sha"]

    with tempfile.TemporaryDirectory(prefix="derive-poly-src-") as tmp:
        source_tree = Path(tmp)
        extract_pinned_tree(args.source, sha, source_tree)

        copied = generate(source_tree, args.out, manifest)
        verified = verify_source_identical(source_tree, args.out, manifest, copied)
        if args.lock:
            lock_repos(args.out, manifest)
        aggregate = write_fixture_metadata(args.out, manifest, verified)
        if args.parent_readme:
            (args.out / "README.md").write_text(PARENT_README)
        if args.git:
            git_init_repos(args.out, manifest)

        if args.verify_reproducible:
            with tempfile.TemporaryDirectory(prefix="derive-poly-verify-") as tmp2:
                out2 = Path(tmp2) / "poly"
                copied2 = generate(source_tree, out2, manifest)
                verify_source_identical(source_tree, out2, manifest, copied2)
                if args.lock:
                    lock_repos(out2, manifest)
                write_fixture_metadata(out2, manifest, verified)
                if args.parent_readme:
                    (out2 / "README.md").write_text(PARENT_README)
                d1, d2 = tree_digest(args.out), tree_digest(out2)
                if d1 != d2:
                    raise SystemExit(
                        f"NOT reproducible: {d1} != {d2} — the generator has a "
                        "nondeterministic step"
                    )
                print(f"reproducible: {d1}", file=sys.stderr)

    print(
        json.dumps(
            {
                "out": str(args.out),
                "source_sha": sha,
                "source_identical_files_verified": verified,
                "aggregate_sha256": aggregate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
