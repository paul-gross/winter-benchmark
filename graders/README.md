# Graders — hidden deterministic checks

The zero-token grading layer: every mechanically observable requirement is
graded here, never by the LLM judge. **Never visible to an implementation
agent** (leak guard: `../environments/README.md`).

| Piece | What it does |
|-------|--------------|
| [grading-map.md](./grading-map.md) | The requirement-to-grader map for all five prompts — which check grades which requirement, required vs judge-input, and the qualitative remainder |
| [grade.py](./grade.py) | Orchestrator: launches the submission's final code freshly (ephemeral Postgres + RabbitMQ containers, clean DB), runs the per-prompt Playwright suite + db/broker/structural checks, emits `grade-result.json` |
| [tests/](./tests/) | The hidden Playwright suite — UI (browser), API (request), broker-payload and regression layers; one spec file per concern, composed per prompt |
| [structural/structural_t4.py](./structural/structural_t4.py) | Repository-split shape checks, run inside the submission's own venv |
| [delivery.py](./delivery.py) | Delivery gate (commit on a non-default branch, clean tree, non-empty diff) + branch-name cohesion |
| [evidence.py](./evidence.py) | "Did they run it?" signals: transcript launch scan, capability-matrix detection, runtime DB/broker figures |

## Running

```sh
cd graders
uv sync && npm install && npx playwright install chromium   # once

uv run python grade.py --submission <final-code> --topology mono|poly \
  --prompt t1-delete-item|t2-worker-liveness|t3-rename-label-title|t4-repository-split|t5-compound \
  --out <run-dir>
```

`--prompt baseline` is the harness self-test: the **pristine** fixture must
pass it on both topologies (verified — 6/6 mono and poly), and must fail each
task's own checks (verified for t1: exactly the t1 + delivery checks fail on
the pristine tree). Run it after any grader change.

## Design rules

- **Solution-independent.** Checks grade observable requirements (status
  codes, DB state, message payloads, UI behavior), not implementation shape —
  except the structural checks tied to constraints the prompts explicitly
  state. UI checks use generous, vocabulary-based locators (any per-row
  delete-ish control; any worker-labeled status region) so an unconventional
  but correct UI still passes.
- **The grader controls the environment.** Fresh containers and a clean DB per
  grade; the suite seeds its own data. For t3/t5 the DB is seeded with the
  *old* schema before first boot, so the migrate-at-startup requirement is
  graded exactly as stated.
- **The grader controls the worker process.** t2's up→down transition is
  driven by actually stopping the worker, so a hardcoded or config-based
  indicator cannot pass.
- **checks[] conforms to the phase-1 result schema**; `grade.py` never exits
  non-zero for a graded failure (only for a grader crash).
