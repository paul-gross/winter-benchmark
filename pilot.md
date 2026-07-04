# The 30-cell validation pilot — runbook

The pilot validates the **harness**, not Winter: one run per prompt/topology/
condition cell (5 × 6 = 30). No comparative Winter-effectiveness claim may be
drawn from it (protocol §Known limitations); comparative claims come from the
later frozen run with a predeclared repetition count.

## Sequence (cost-controlled)

1. **Zero-token self-test** — the fake-host loop must classify
   `fully_achieved_unattended`:
   ```sh
   BENCH_FAKE_SCRIPT=$PWD/runner/selftest/t1-mono-agent.sh \
   python3 runner/bench.py run --topology mono --condition plain \
     --prompt t1-delete-item --model scripted --host fake --sandbox none \
     --results-root /tmp/bench-selftest
   ```
2. **Sandbox validation** — build the image and verify one fake-host cell
   inside it before spending any quota:
   ```sh
   docker build -t winter-bench-sandbox runner/sandbox
   ```
3. **Haiku harness dry-run** — shake out reset/capture/judge plumbing on the
   cheap model before real-model quota (a subset is enough; all 30 for full
   confidence):
   ```sh
   python3 runner/bench.py batch --model haiku --host claude
   ```
4. **The pilot proper** — the model under test:
   ```sh
   python3 runner/bench.py batch --model sonnet --host claude
   ```
   Pacing: with roughly 10–15 sonnet-class unattended runs per weekly window
   (protocol §Cost policy), the 30 cells span 2–3 windows. Completed cells are
   durable and skipped on re-invocation — stop at quota, re-run the same
   command after reset.
5. **Report:**
   ```sh
   python3 runner/report.py --results-root results/$(cat VERSION) \
     --json results/$(cat VERSION)/report/pilot.json
   ```

## Pilot checklist (from #118/#126)

| Item | How it is validated | Status |
|------|---------------------|--------|
| Fixture equivalence | `derive-poly --verify-reproducible` byte-identity; pristine fixture passes `--prompt baseline` on both topologies | ✅ pre-validated (2026-07-03: 39 files checksum-identical; baseline 6/6 mono and poly) |
| Prompt discrimination without condition bias | independent bias review (prompts/BIAS-REVIEW.md); pristine fixture *fails* each task's own checks | ✅ pre-validated for t1; confirm t2–t5 during the pilot |
| Hidden checks grade requirements, not trivia | grader-verified reference implementation passes t1 13/13; review per-cell failures during the pilot for implementation-shape bias | ◻ pilot |
| Intervention policy operational | no input channel exists after launch; stall detection flags `awaiting_input`/`boundary`/`crashed` | ◻ pilot |
| Blind judging consistent | calibration set (good/partial/gamed) classifies correctly — re-run `judge/calibration/calibrate.py` before and after the pilot | ✅ passing (judge-v1) |
| Runner resets and captures every condition | fake-host full loop green; haiku dry-run per condition; artifact manifest complete in each run dir | ◻ pilot (mono/plain validated 2026-07-03) |
| Sandbox isolation | one fake-host cell inside `--sandbox docker` | ✅ validated (2026-07-03: full cell incl. judge auth inside the sandbox) |

## Outputs

- Per-run records under `results/<version>/runs/` (never overwritten;
  `--force` is explicit).
- The four-class distribution by condition, topology, prompt type, and
  ordinary-vs-compound — `report.py` (compound reported separately).
- Efficiency fields surfaced only in the fairness audit section.
- **A defect list** for pre-freeze correction: file issues for every harness
  defect the pilot surfaces, fix, bump `VERSION`, and only then freeze
  and predeclare the comparative repetition count.
