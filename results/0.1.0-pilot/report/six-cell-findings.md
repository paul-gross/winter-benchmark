# Six-cell sonnet run — findings report

Date: 2026-07-04, 14:53–16:23 UTC. Scope: the full six-cell condition matrix
(mono/poly × plain/winter/winter-workflow) on the `t1-delete-item` prompt,
`--model sonnet --host claude`, docker sandbox, sequential per the protocol's
fairness controls. This was the first time the real Claude Code host ran inside
the docker sandbox — the run doubled as the harness shakeout the pilot runbook
anticipates, and it surfaced six harness defects, all fixed during the session.

**No comparative Winter-effectiveness claim is drawn from these runs** (one run
per cell; protocol §Known limitations). The outcome table and efficiency fields
below are recorded observations, not evidence of a condition effect.

## Outcomes — all six cells fully achieved

| Cell | Result | Checks | Wall clock | Output tokens | Cost (API-equiv) | Tool calls (failed) |
|------|--------|--------|-----------:|--------------:|-----------------:|--------------------:|
| mono/plain | fully_achieved_unattended | 13/13 | 171 s | 11.0k | $0.94 | 46 (3) |
| mono/winter | fully_achieved_unattended | 13/13 | 283 s | 7.2k | $1.79 | 62 (3) |
| mono/winter-workflow | fully_achieved_unattended | 13/13 | 1343 s | 34.9k | $7.13 | 186 (4) |
| poly/plain | fully_achieved_unattended | 13/13 | 239 s | 13.4k | $1.12 | 58 (3) |
| poly/winter | fully_achieved_unattended | 13/13 | 283 s | 16.9k | $1.81 | 71 (3) |
| poly/winter-workflow | fully_achieved_unattended | 13/13 | 1111 s | 28.8k | $5.00 | 176 (176 total, 4 failed) |

Every run delivered committed work on a feature branch (branch cohesion 1.0 in
all four multi-repo-relevant cells), passed all 13 hidden deterministic checks,
included a detectable per-requirement verification report, and drew a
`fully_achieved_unattended` proposal from the blinded judge with no material
unmet requirement.

Aggregate JSON: [six-cell.json](./six-cell.json) (includes the 7/03 fake and
haiku dry-run records; 10 runs total, all fully achieved).

## Efficiency observation (recorded, never scored)

At n=1 per cell, one pattern is worth watching in the pilot proper: the
`winter-workflow` condition took roughly 4–7× the wall clock and 3–5× the
tokens of the other conditions for the same graded outcome on this small task.
The workflow runs spent it on multi-agent process (architect/developer/verifier
phases, a 4-axis pre-push review, a retrospective) — visible in their final
messages. Whether that overhead buys higher success on harder prompts
(t2–t5, compound) is exactly what the remaining pilot cells should show.

## Harness defects surfaced and fixed (the main deliverable)

The pilot checklist calls for a defect list for pre-freeze correction. This run
produced six, all fixed and verified in-session:

1. **Sandboxed agent crashed instantly: root + `--dangerously-skip-permissions`.**
   Claude Code refuses that flag as root. The 7/03 sandbox validation missed it
   because the fake host doesn't pass the flag and the judge's `claude -p`
   doesn't either. Fix: `IS_SANDBOX=1` in the sandbox `docker run` env
   (`runner/bench.py`), the documented devcontainer contract. Also seeded a
   minimal `/root/.claude.json` (`hasCompletedOnboarding`) — the credential
   dir mount alone leaves headless claude complaining about missing config.

2. **Winter conditions could not bootstrap: no docker compose v2 in the
   sandbox image.** `winter service up workspace` died with `unknown shorthand
   flag: 'p'`. Fix: `docker-compose-v2` layer in `runner/sandbox/Dockerfile`.

3. **All seven runtime checks silently "not evaluated": the hidden Playwright
   suite had no `node_modules` inside the sandbox.** The read-only bench mount
   carries none, so `npx playwright test` failed and `run_playwright` returned
   empty outcomes — checks defaulted to `error/not evaluated` and the grade
   emitted anyway. Fix: `npm ci` for `graders/` in the sandbox preamble
   (`runner/bench.py`). Follow-up worth considering: treat "playwright produced
   no report" as a grader crash rather than a silent all-fail.

4. **Verification-report detection only recognized markdown tables.** The
   prompt mandates content ("state the method … and the observed result"), not
   table formatting. Agents that reported verification as bullets scored
   `capability_matrix_present=false`; because blinding excludes the final
   message, the judge could not see otherwise and downgraded the run to
   partial. Fix: bullet rows matching method words now count
   (`graders/evidence.py`, `runner/capture.py`). Both affected completed runs
   were re-blinded and re-judged; both flipped to fully-achieved on unchanged
   deterministic grades.

5. **Poly fixture shipped no committed `uv.lock`; the delivery gate read the
   agent's first `uv sync` as a dirty tree.** The mono fixture commits
   `uv.lock`; the derived Python repos didn't, so running the app to verify —
   which the prompt requires — generated untracked lockfiles and failed
   `del.committed-feature-branch` (a required check) in the poly topology
   only. A clean topology-bias bug. Reproduced locally (`uv sync` in a fresh
   derived `wts-worker` → `?? uv.lock`). Fix: `--lock` in
   `environments/build_env.py`'s derive invocation, matching mono.
   Diagnosability follow-up: `delivery.json` should record the porcelain
   output so "dirty" is attributable post-teardown.

6. **The structural seam check scanned test code.** An agent that added a real
   test suite (SQLAlchemy-based cleanup in `tests/conftest.py`) failed
   `t1.structural.seam` — implementation-shape bias against better-than-asked
   submissions. The requirement constrains the deletion feature path, not test
   fixtures. Fix: test files (`tests/`, `conftest.py`, `test_*`) excluded
   (`graders/grade.py`). The affected run's seam verdict was recomputed from
   its captured diffs (the check is purely diff-based, so the recomputation is
   exact) and it re-judged to fully-achieved.

Minor notes, not fixed: the credential mount is documented read-only but
mounted read-write (`bench.py` omits `:ro`; claude needs to write under
`~/.claude`, so the doc is what's wrong); sandbox cells write results as root,
so host-side post-processing needs a chown.

## Result provenance

All six records at `runs/<cell>-t1-delete-item-sonnet-claude-r1/` were
produced by agents running in the fixed sandbox environment. Scoring
provenance differs for two of them:

- **mono/winter-workflow, poly/winter-workflow** — deterministic grade from
  the original run (13/13 after defect-6 recomputation for poly); capability
  matrix, evidence, blinded package, and judge regenerated post-hoc with the
  fixed extraction. The agent-facing environment was unaffected.
- **mono/plain, poly/plain, mono/winter, poly/winter** — fully clean end-to-end
  runs on the fixed harness (the two plain cells re-ran under `--force` after
  their first attempts were invalidated by defects 3 and 5).

Discarded records: the first sonnet mono/plain attempt (defect-1 crash, then a
defect-3 misgrade) is quarantined outside the results store; two winter-cell
attempts were killed mid-run before their agents did significant work (defects
2 and 5, plus one stale-code start) and left no result records.

## Recommended next steps

1. Commit the six fixes (currently uncommitted in `winter-benchmark`), file
   the defect issues per the pilot checklist, and bump `VERSION` — results are
   only comparable within one version, and graders changed mid-batch.
2. Re-run judge calibration (`judge/calibration/calibrate.py`) after the
   evidence-format change.
3. Continue the pilot across t2–t5 (24 remaining cells) on the frozen version;
   watch the seam/matrix checks for further shape bias, per checklist.
4. Only after the full pilot: predeclare the repetition count and run the
   comparative batch.
