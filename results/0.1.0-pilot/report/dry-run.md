# Harness dry-run record — benchmark 0.1.0-pilot

Date: 2026-07-03. Purpose: validate the harness plumbing end to end before any
quota is spent on the pilot proper (pilot.md step 1–3). **No comparative claim
of any kind is drawn from these runs.**

## Runs recorded

| Run | What it validates | Outcome |
|-----|-------------------|---------|
| `mono-plain-t1-delete-item-scripted-fake-r1` | Full loop at zero tokens: reset → scripted agent (reference t1 patch) → capture → grade → blinded judge → classify → emit | `fully_achieved_unattended`; 13/13 checks; result.json validates against the schema |
| `mono-plain-t1-delete-item-haiku-claude-r1` | The Claude Code adapter on a real unattended run (`--model haiku`), per #125's validation criterion and #126's dry-run step | `fully_achieved_unattended`; 13/13 checks; 194s wall, 16.5k output tokens, 64 tool calls (3 failed) captured as unscored efficiency fields |

## Harness validations performed to date (see also pilot.md checklist)

- Generator determinism: byte-for-byte reproduction, 39 source files
  checksum-identical to the mono pin.
- Fixture equivalence in practice: the pristine fixture passes the `baseline`
  grade 6/6 on **both** topologies.
- Grader discrimination: the pristine fixture fails exactly the t1 + delivery
  checks under the t1 grader; the hand-built reference implementation passes
  13/13.
- Winter workspace reconstruction: mono workspace bootstrapped from pinned
  clean state; alpha env provisioned; app up and healthy on the wtsb band;
  worker heartbeats observed in the per-env DB and vhost; clean teardown.
- Judge calibration: good/partial/gamed classify correctly; embedded
  reviewer-directed instruction resisted and reported.
- Blinding: judge packages carry a random blind id; condition/host/model and
  the agent's final message are excluded.

## Additional validations (same day, after the runs above)

- Grader discrimination for every non-compound prompt: the pristine fixture
  fails exactly its own task's checks (+ delivery) under t1, t2, t3, and t4.
- Grader positive paths: hand-built reference implementations pass t1 (13/13),
  t2 (12/12, including the real up→down→up transition), and t4 (11/11,
  composition-based split). t3/t5 positive paths are exercised by the pilot
  itself.
- Sandbox: a full fake-host cell ran inside `--sandbox docker` end to end,
  including the blinded judge authenticating through the mounted credential —
  `fully_achieved_unattended`, result written to the mounted results store.

## Harness defects found and fixed during the dry-run

| Defect | Fix |
|--------|-----|
| Grader worker stop killed only the `uv run` wrapper, not the real worker — t2's transition never fired | kill the process group |
| `innerText` fuses adjacent inline elements ("Worker down"+"status" → "downstatus"), defeating word-boundary vocabulary matching; up-state vocab could false-positive on the health badge's "ok" | space-joined region assembly; up state redefined as "not down while genuinely running", down transition vocabulary-checked both ways against the real process |
| t4 structural probe couldn't import the submission package under `uv run` (script path replaces cwd on sys.path) | `PYTHONPATH=.` for the probe |
| Sandbox: worktree sources break inside the mount; dubious-ownership refusals; `&>` bashism in the POSIX dockerd wait; overlay-on-overlay whiteout extraction | worktree guard + guidance; container-wide `safe.directory`; POSIX redirects; anonymous volume at `/var/lib/docker` |

## Observations for the pilot defect list

1. **Verification-report expectation was initially invisible to the judge.**
   The haiku run skipped the requested per-requirement verification report
   (`capability_matrix_present: false`) yet judged `fully` because evidence
   signals were not in the blinded package. **Fixed during the dry-run**:
   deterministic evidence signals now feed the judge's
   `requirement_completeness` dimension (condition-neutral, informative-only).
   Watch during the pilot whether this weighs appropriately.
2. **Sandbox mounts must be self-contained clones.** Git worktrees as
   `--sources-dir` break inside the sandbox (their `.git` files point outside
   the mount); the runner now rejects them with guidance, and container-side
   `safe.directory` handling was added. Validate one sandboxed cell per
   condition during the pilot.
3. The haiku agent verified via API/DB but never ran the worker
   (`db_worker_rows: 0`, `broker_deliveries: 0` in its runtime) — the evidence
   signals caught this exactly as designed. For t1 the worker is not required;
   for t2/t3/t5 the graders enforce it deterministically.
