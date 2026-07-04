#!/usr/bin/env python3
"""Grade a submission: launch its final code freshly and run the hidden checks.

The grader receives a copy of the agent's final code (mono checkout or poly
parent directory), launches the full stack against ephemeral Postgres/RabbitMQ
containers (clean DB — the suite seeds its own data), runs the per-prompt
hidden Playwright suite plus the db/broker/structural/regression/delivery
checks, and emits a single grade-result.json whose `checks` array conforms to
the phase-1 result schema. Never shown to the implementation agent.

Usage:
    uv run grade.py --submission PATH --topology mono|poly --prompt t1-delete-item \
                    --out DIR [--keep]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

import delivery as delivery_mod

HERE = Path(__file__).parent

POLY_REPOS = ["wts-web", "wts-api", "wts-worker", "wts-persistence", "wts-messaging"]

PLAN = {
    "t1-delete-item": {"specs": ["regression.spec.ts", "t1-delete-item.spec.ts"], "field": "label"},
    "t2-worker-liveness": {"specs": ["regression.spec.ts", "t2-worker-liveness.spec.ts"], "field": "label"},
    "t3-rename-label-title": {
        "specs": ["regression.spec.ts", "t3-rename.spec.ts"],
        "field": "title",
        "seed_old_schema": True,
        "db_rename_checks": True,
    },
    "t4-repository-split": {
        "specs": ["regression.spec.ts"],
        "field": "label",
        "structural_t4": True,
        "diff_confined": True,
    },
    "t5-compound": {
        "specs": [
            "regression.spec.ts",
            "t1-delete-item.spec.ts",
            "t2-worker-liveness.spec.ts",
            "t3-rename.spec.ts",
        ],
        "field": "title",
        "seed_old_schema": True,
        "db_rename_checks": True,
        "structural_t4": True,
        "structural_t4_renamed": True,
    },
    # Harness self-test: the pristine fixture must pass exactly this set.
    "baseline": {"specs": ["regression.spec.ts"], "field": "label"},
}

# Playwright test-title prefix → check ids it certifies (one test may certify
# several closely coupled requirements).
SPEC_CHECKS = {
    "reg.items-create-list": ["reg.items-create-list"],
    "reg.ui-lists-items": ["reg.ui-lists-items"],
    "reg.api-health": ["reg.api-health"],
    "t1.api.delete-204-removes": ["t1.api.delete-204-removes"],
    "t1.api.delete-missing-404": ["t1.api.delete-missing-404"],
    "t1.db.only-target-removed": ["t1.db.only-target-removed"],
    "t1.ui.row-delete-no-reload": ["t1.ui.row-delete-no-reload"],
    "t2.ui.worker-liveness-transition": [
        "t2.ui.indicator-present",
        "t2.ui.up-while-running",
        "t2.ui.down-within-15s",
        "t2.evidence.genuine-liveness",
    ],
    "t3.api.title-shape": ["t3.api.title-shape"],
    "t3.broker.payload-title": ["t3.broker.payload-title"],
    "t3.ui.title-visible": ["t3.ui.title-visible"],
}

SEED_ROWS = [
    (9001, "seed-alpha", "api"),
    (9002, "seed-beta", "api"),
    (9003, "seed-heartbeat", "worker"),
]

# Raw-SQL markers for the seam check (t1): added Python lines outside the
# persistence layer must not introduce SQL or SQL-library usage. Encodes only
# the prompt's stated constraint.
SQL_MARKERS = re.compile(
    r"(from\s+sqlalchemy|import\s+sqlalchemy|import\s+psycopg|from\s+psycopg"
    r"|\btext\s*\(|\.execute\s*\(|INSERT\s+INTO|DELETE\s+FROM|UPDATE\s+\w+\s+SET\b)",
    re.IGNORECASE,
)


def log(msg: str) -> None:
    print(f"[grade] {msg}", file=sys.stderr)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def sh(cmd: list[str], cwd: Path | None = None, env: dict | None = None,
       timeout: float | None = None) -> subprocess.CompletedProcess:
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=cwd, env=full_env, capture_output=True,
                          text=True, timeout=timeout)


class Check:
    def __init__(self, id: str, layer: str, required: bool = True):
        self.id, self.layer, self.required = id, layer, required
        self.status = "error"
        self.detail = "not evaluated"

    def record(self, ok: bool, detail: str = "") -> None:
        self.status = "pass" if ok else "fail"
        self.detail = detail

    def as_dict(self) -> dict:
        return {"id": self.id, "layer": self.layer, "required": self.required,
                "status": self.status, "detail": self.detail[:2000]}


class Stack:
    """The submission's running stack + the grading control surface."""

    def __init__(self, submission: Path, topology: str, out: Path):
        self.submission = submission
        self.topology = topology
        self.out = out
        self.token = secrets.token_hex(4)
        self.pg_port = free_port()
        self.amqp_port = free_port()
        self.api_port = free_port()
        self.web_port = free_port()
        self.control_port = free_port()
        self.pg_name = f"bench-grade-pg-{self.token}"
        self.mq_name = f"bench-grade-mq-{self.token}"
        self.procs: dict[str, subprocess.Popen] = {}
        self.logs: dict[str, object] = {}
        self.server: ThreadingHTTPServer | None = None

    # --- layout -----------------------------------------------------------

    def path(self, part: str) -> Path:
        if self.topology == "mono":
            return {
                "api_cwd": self.submission,
                "worker_cwd": self.submission,
                "web": self.submission / "web",
                "persistence": self.submission,
            }[part]
        return {
            "api_cwd": self.submission / "wts-api",
            "worker_cwd": self.submission / "wts-worker",
            "web": self.submission / "wts-web",
            "persistence": self.submission / "wts-persistence",
        }[part]

    def repo_specs(self) -> dict[str, Path]:
        if self.topology == "mono":
            return {"winter-test-service": self.submission}
        return {name: self.submission / name for name in POLY_REPOS}

    # --- infra ------------------------------------------------------------

    def start_infra(self) -> None:
        log(f"starting postgres:{self.pg_port} rabbitmq:{self.amqp_port}")
        sh(["docker", "run", "-d", "--rm", "--name", self.pg_name,
            "-e", "POSTGRES_USER=wts", "-e", "POSTGRES_PASSWORD=wts",
            "-e", "POSTGRES_DB=wts", "-p", f"{self.pg_port}:5432", "postgres:16"])
        sh(["docker", "run", "-d", "--rm", "--name", self.mq_name,
            "-p", f"{self.amqp_port}:5672", "rabbitmq:3-management"])
        self._wait(lambda: sh(["docker", "exec", self.pg_name, "pg_isready", "-U", "wts"]).returncode == 0,
                   60, "postgres readiness")
        self._wait(lambda: sh(["docker", "exec", self.mq_name, "rabbitmq-diagnostics", "-q", "ping"]).returncode == 0,
                   90, "rabbitmq readiness")

    @staticmethod
    def _wait(probe, timeout: float, what: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if probe():
                    return
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1)
        raise TimeoutError(f"timed out waiting for {what}")

    def psql(self, query: str) -> str:
        result = sh(["docker", "exec", self.pg_name, "psql", "-U", "wts", "-d", "wts", "-tAc", query])
        if result.returncode != 0:
            raise RuntimeError(f"psql failed: {result.stderr}")
        return result.stdout.strip()

    def seed_old_schema(self) -> None:
        """Pre-boot seed in the ORIGINAL shape — grades the stated
        migrate-at-startup, data-preserved requirement."""
        ddl = (
            "CREATE TABLE IF NOT EXISTS items ("
            "id BIGSERIAL PRIMARY KEY, label TEXT NOT NULL, source TEXT NOT NULL, "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now());"
        )
        self.psql(ddl)
        for row_id, label, source in SEED_ROWS:
            self.psql(
                f"INSERT INTO items (id, label, source) VALUES ({row_id}, '{label}', '{source}');"
            )
        self.psql("SELECT setval('items_id_seq', 9100);")

    # --- deps + services ----------------------------------------------------

    def install_deps(self) -> None:
        if self.topology == "mono":
            targets = [("uv", self.submission)]
        else:
            targets = [("uv", self.path("persistence")),
                       ("uv", self.submission / "wts-messaging"),
                       ("uv", self.path("api_cwd")),
                       ("uv", self.path("worker_cwd"))]
        for kind, cwd in targets:
            log(f"uv sync: {cwd.name}")
            result = sh(["uv", "sync"], cwd=cwd, timeout=600)
            if result.returncode != 0:
                raise RuntimeError(f"uv sync failed in {cwd}: {result.stderr[-2000:]}")
        log(f"npm install: {self.path('web').name}")
        result = sh(["npm", "install", "--no-audit", "--no-fund"], cwd=self.path("web"), timeout=900)
        if result.returncode != 0:
            raise RuntimeError(f"npm install failed: {result.stderr[-2000:]}")

    def service_env(self) -> dict:
        return {
            "DATABASE_URL": f"postgresql://wts:wts@localhost:{self.pg_port}/wts",
            "RABBITMQ_URL": f"amqp://guest:guest@localhost:{self.amqp_port}/%2f",
            "WTS_API_PORT": str(self.api_port),
            "WTS_WEB_PORT": str(self.web_port),
        }

    def spawn(self, name: str, cmd: list[str], cwd: Path, extra_env: dict | None = None) -> None:
        logfile = open(self.out / f"stack-{name}.log", "w")  # noqa: SIM115 — lives with the process
        self.logs[name] = logfile
        env = {**os.environ, **self.service_env(), **(extra_env or {})}
        env.pop("WINTER_ENV", None)  # never inherit a workspace identity
        self.procs[name] = subprocess.Popen(
            cmd, cwd=cwd, env=env, stdout=logfile, stderr=subprocess.STDOUT,
            start_new_session=True,
        )

    def start_api(self) -> None:
        extra = {"PYTHONPATH": ".:api"} if self.topology == "mono" else None
        self.spawn("api", ["uv", "run", "python", "-m", "app"], self.path("api_cwd"), extra)

    def start_worker(self) -> None:
        self.spawn("worker", ["uv", "run", "python", "-m", "worker.main"], self.path("worker_cwd"))

    def stop_worker(self) -> None:
        proc = self.procs.get("worker")
        if proc and proc.poll() is None:
            # Kill the whole group: `uv run` wraps the real python worker in a
            # child process that must die too, or heartbeats keep flowing.
            try:
                os.killpg(os.getpgid(proc.pid), 15)
                proc.wait(10)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except ProcessLookupError:
                    pass

    def start_web(self) -> None:
        self.spawn("web", ["npm", "run", "dev"], self.path("web"))

    def wait_api_healthy(self, timeout: float = 90) -> bool:
        def probe() -> bool:
            with urlopen(f"http://localhost:{self.api_port}/api/health", timeout=3) as res:
                return json.load(res).get("db") == "ok"
        try:
            self._wait(probe, timeout, "api health")
            return True
        except TimeoutError:
            return False

    def wait_web(self, timeout: float = 90) -> bool:
        def probe() -> bool:
            with urlopen(f"http://localhost:{self.web_port}/", timeout=3) as res:
                return res.status == 200
        try:
            self._wait(probe, timeout, "web dev server")
            return True
        except TimeoutError:
            return False

    def wait_worker_rows(self, timeout: float = 45) -> bool:
        try:
            self._wait(lambda: int(self.psql("SELECT count(*) FROM items WHERE source='worker'") or 0) > 0,
                       timeout, "worker rows")
            return True
        except TimeoutError:
            return False
        except RuntimeError:
            return False

    # --- broker helpers ------------------------------------------------------

    def consume_one(self) -> dict:
        import pika  # deferred: only the grader env has it

        try:
            conn = pika.BlockingConnection(
                pika.URLParameters(f"amqp://guest:guest@localhost:{self.amqp_port}/%2f")
            )
            channel = conn.channel()
            channel.queue_declare(queue="heartbeats", durable=True)
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                method, _props, body = channel.basic_get("heartbeats", auto_ack=True)
                if method:
                    conn.close()
                    return {"found": True, "body": json.loads(body)}
                time.sleep(1)
            conn.close()
            return {"found": False, "body": None}
        except Exception as exc:  # noqa: BLE001
            return {"found": False, "body": None, "error": str(exc)}

    # --- control server -------------------------------------------------------

    def start_control(self) -> None:
        stack = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                url = urlparse(self.path)
                query = parse_qs(url.query)
                try:
                    if url.path == "/worker/stop":
                        stack.stop_worker()
                        payload = {"ok": True}
                    elif url.path == "/worker/start":
                        if not (stack.procs.get("worker") and stack.procs["worker"].poll() is None):
                            stack.start_worker()
                        payload = {"ok": True}
                    elif url.path == "/db/items-count":
                        source = query.get("source", [None])[0]
                        where = f" WHERE source='{source}'" if source else ""
                        payload = {"count": int(stack.psql(f"SELECT count(*) FROM items{where}") or 0)}
                    elif url.path == "/broker/consume-one":
                        payload = stack.consume_one()
                    else:
                        self.send_response(404)
                        self.end_headers()
                        return
                    body = json.dumps(payload).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as exc:  # noqa: BLE001
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(str(exc).encode())

            def log_message(self, *args):  # silence
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", self.control_port), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    # --- teardown ---------------------------------------------------------

    def teardown(self) -> None:
        if self.server:
            self.server.shutdown()
        for proc in self.procs.values():
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), 15)
                except ProcessLookupError:
                    pass
        time.sleep(1)
        for proc in self.procs.values():
            if proc.poll() is None:
                try:
                    os.killpg(os.getpgid(proc.pid), 9)
                except ProcessLookupError:
                    pass
        for logfile in self.logs.values():
            logfile.close()
        for name in (self.pg_name, self.mq_name):
            sh(["docker", "rm", "-f", name])


# ---------------------------------------------------------------------------
# Non-Playwright checks
# ---------------------------------------------------------------------------


def added_python_lines_outside_persistence(stack: Stack) -> list[str]:
    """Added diff lines in Python files outside the persistence layer."""
    lines: list[str] = []
    for name, repo in stack.repo_specs().items():
        result = sh(["git", "-C", str(repo), "diff", "master...HEAD", "--unified=0"])
        if result.returncode != 0:
            continue
        current_file = ""
        for line in result.stdout.splitlines():
            if line.startswith("+++ b/"):
                current_file = line[6:]
            elif line.startswith("+") and not line.startswith("+++"):
                if not current_file.endswith(".py"):
                    continue
                if stack.topology == "mono" and current_file.startswith("wts_persistence/"):
                    continue
                if stack.topology == "poly" and name == "wts-persistence":
                    continue
                lines.append(f"{name}:{current_file}: {line[1:].strip()}")
    return lines


def check_seam(stack: Stack, check: Check) -> None:
    offending = [line for line in added_python_lines_outside_persistence(stack) if SQL_MARKERS.search(line)]
    check.record(not offending, "; ".join(offending[:5]) if offending else "no SQL added outside the persistence layer")


def check_db_rename(stack: Stack, col_renamed: Check, data_preserved: Check) -> None:
    try:
        cols = set(stack.psql(
            "SELECT column_name FROM information_schema.columns WHERE table_name='items'"
        ).splitlines())
        col_renamed.record(
            "title" in cols and "label" not in cols,
            f"items columns: {sorted(cols)}",
        )
        rows = stack.psql(
            "SELECT id, title, source FROM items WHERE id IN (9001, 9002, 9003) ORDER BY id"
        ).splitlines() if "title" in cols else []
        expected = [f"{i}|{v}|{s}" for i, v, s in SEED_ROWS]
        data_preserved.record(
            rows == expected,
            f"seeded rows after startup migration: {rows} (expected {expected})",
        )
    except RuntimeError as exc:
        col_renamed.record(False, str(exc))
        data_preserved.record(False, str(exc))


def check_structural_t4(stack: Stack, checks: dict[str, Check], renamed: bool) -> None:
    cwd = stack.path("persistence")
    cmd = ["uv", "run", "python", str((HERE / "structural" / "structural_t4.py").resolve())]
    if renamed:
        cmd += ["--renamed-field", "title"]
    # PYTHONPATH=.: the probe script lives outside the submission, so the
    # submission's own packages must come from cwd (mono; harmless in poly,
    # where the lib repo installs itself into its venv).
    result = sh(cmd, cwd=cwd, env={"PYTHONPATH": "."}, timeout=120)
    if result.returncode != 0:
        for c in checks.values():
            c.record(False, f"structural probe failed: {result.stderr[-500:]}")
        return
    data = json.loads(result.stdout)
    details = "; ".join(data.get("details", [])) or "ok"
    checks["t4.structural.protocols-frozen"].record(data["protocols_frozen"], details)
    checks["t4.structural.no-inheritance"].record(
        data["no_inheritance"] and data["distinct_read_impl"],
        f"read impls: {data.get('read_impls')}; {details}",
    )


def check_diff_confined(stack: Stack, check: Check) -> None:
    outside: list[str] = []
    for name, repo in stack.repo_specs().items():
        result = sh(["git", "-C", str(repo), "diff", "--name-only", "master...HEAD"])
        for f in result.stdout.splitlines():
            if stack.topology == "mono" and not f.startswith("wts_persistence/"):
                outside.append(f"{name}:{f}")
            if stack.topology == "poly" and name != "wts-persistence" and f:
                outside.append(f"{name}:{f}")
    check.record(not outside, "; ".join(outside[:10]) if outside else "diff confined to the persistence layer")


def check_web_build(stack: Stack, check: Check) -> None:
    result = sh(["npm", "run", "build"], cwd=stack.path("web"), timeout=600)
    tail = (result.stdout + result.stderr)[-800:]
    check.record(result.returncode == 0, tail)


def run_playwright(stack: Stack, specs: list[str], field: str, report: Path) -> dict[str, tuple[bool, str]]:
    env = {
        **os.environ,
        "API_URL": f"http://localhost:{stack.api_port}",
        "WEB_URL": f"http://localhost:{stack.web_port}",
        "CONTROL_URL": f"http://localhost:{stack.control_port}",
        "ITEM_FIELD": field,
        "GRADE_REPORT": str(report),
    }
    result = subprocess.run(
        ["npx", "playwright", "test", *[f"tests/{s}" for s in specs]],
        cwd=HERE, env=env, capture_output=True, text=True, timeout=1800,
    )
    outcomes: dict[str, tuple[bool, str]] = {}
    if not report.exists():
        log(f"playwright produced no report: {result.stderr[-1000:]}")
        return outcomes
    data = json.loads(report.read_text())

    def walk(suite):
        for child in suite.get("suites", []):
            walk(child)
        for spec in suite.get("specs", []):
            title = spec["title"].split(" — ")[0].strip()
            ok = spec.get("ok", False)
            detail = ""
            for t in spec.get("tests", []):
                for r in t.get("results", []):
                    if r.get("error"):
                        detail = r["error"].get("message", "")[:500]
            outcomes[title] = (ok, detail)

    for suite in data.get("suites", []):
        walk(suite)
    return outcomes


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_checks(prompt: str) -> dict[str, Check]:
    plan = PLAN[prompt]
    checks: dict[str, Check] = {
        "reg.api-boots-health-ok": Check("reg.api-boots-health-ok", "regression"),
        "reg.worker-writes-rows": Check("reg.worker-writes-rows", "regression"),
        "reg.web-typecheck-build": Check("reg.web-typecheck-build", "regression"),
        "del.committed-feature-branch": Check("del.committed-feature-branch", "delivery"),
        "del.diff-non-empty": Check("del.diff-non-empty", "delivery"),
    }
    for spec in plan["specs"]:
        for title, ids in SPEC_CHECKS.items():
            if title.split(".")[0] in ("reg",) and spec != "regression.spec.ts":
                continue
            prefix = {"regression.spec.ts": "reg.", "t1-delete-item.spec.ts": "t1.",
                      "t2-worker-liveness.spec.ts": "t2.", "t3-rename.spec.ts": "t3."}[spec]
            if title.startswith(prefix):
                for check_id in ids:
                    layer = check_id.split(".")[1] if check_id.count(".") >= 2 else "regression"
                    layer = {"api": "api", "ui": "ui", "db": "db", "broker": "broker",
                             "evidence": "db"}.get(layer, "regression")
                    checks[check_id] = Check(check_id, layer)
    if prompt == "t1-delete-item" or prompt == "t5-compound":
        checks["t1.structural.seam"] = Check("t1.structural.seam", "structural")
    if plan.get("db_rename_checks"):
        checks["t3.db.column-renamed"] = Check("t3.db.column-renamed", "db")
        checks["t3.db.data-preserved"] = Check("t3.db.data-preserved", "db")
    if plan.get("structural_t4"):
        checks["t4.structural.protocols-frozen"] = Check("t4.structural.protocols-frozen", "structural")
        checks["t4.structural.no-inheritance"] = Check("t4.structural.no-inheritance", "structural")
        if plan.get("diff_confined"):
            checks["t4.structural.diff-confined"] = Check("t4.structural.diff-confined", "structural")
    if prompt == "baseline":
        # Harness self-test grades a pristine tree: no delivery expected.
        checks.pop("del.committed-feature-branch")
        checks.pop("del.diff-non-empty")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--topology", choices=["mono", "poly"], required=True)
    parser.add_argument("--prompt", choices=list(PLAN), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--keep", action="store_true", help="Leave the stack running (debugging)")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    plan = PLAN[args.prompt]
    checks = build_checks(args.prompt)
    stack = Stack(args.submission.resolve(), args.topology, args.out)
    delivery_report = None

    try:
        # Delivery + structural checks need no running stack.
        if "del.committed-feature-branch" in checks:
            delivery_report = delivery_mod.collect(stack.repo_specs(), args.topology)
            checks["del.committed-feature-branch"].record(
                delivery_report["committed"],
                f"cohesion={delivery_report['branch_cohesion']}",
            )
            checks["del.diff-non-empty"].record(delivery_report["diff_non_empty"], "")
        if "t1.structural.seam" in checks:
            check_seam(stack, checks["t1.structural.seam"])
        if "t4.structural.diff-confined" in checks:
            check_diff_confined(stack, checks["t4.structural.diff-confined"])

        stack.start_infra()
        if plan.get("seed_old_schema"):
            stack.seed_old_schema()
        stack.install_deps()

        if plan.get("structural_t4"):
            check_structural_t4(
                stack,
                {k: v for k, v in checks.items() if k.startswith("t4.structural.") and k != "t4.structural.diff-confined"},
                renamed=plan.get("structural_t4_renamed", False),
            )

        check_web_build(stack, checks["reg.web-typecheck-build"])

        stack.start_api()
        api_ok = stack.wait_api_healthy()
        checks["reg.api-boots-health-ok"].record(api_ok, "" if api_ok else "api did not become healthy in 90s")

        if plan.get("db_rename_checks"):
            check_db_rename(stack, checks["t3.db.column-renamed"], checks["t3.db.data-preserved"])

        if api_ok:
            stack.start_worker()
            worker_ok = stack.wait_worker_rows()
            checks["reg.worker-writes-rows"].record(worker_ok, "" if worker_ok else "no worker rows within 45s")
            stack.start_web()
            web_ok = stack.wait_web()
            stack.start_control()
            if web_ok:
                report = args.out / "playwright-report.json"
                outcomes = run_playwright(stack, plan["specs"], plan["field"], report)
                for title, ids in SPEC_CHECKS.items():
                    if title in outcomes:
                        ok, detail = outcomes[title]
                        for check_id in ids:
                            if check_id in checks:
                                checks[check_id].record(ok, detail)
            else:
                for c in checks.values():
                    if c.layer == "ui" and c.status == "error":
                        c.detail = "web dev server did not start"
        else:
            for c in checks.values():
                if c.status == "error":
                    c.detail = "stack failed to launch (api unhealthy)"
    finally:
        if not args.keep:
            stack.teardown()

    result = {
        "prompt": args.prompt,
        "topology": args.topology,
        "checks": [c.as_dict() for c in checks.values()],
        "delivery": delivery_report,
        "required_failed": [c.id for c in checks.values() if c.required and c.status != "pass"],
    }
    (args.out / "grade-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"required_failed": result["required_failed"],
                      "total_checks": len(checks)}, indent=2))


if __name__ == "__main__":
    main()
