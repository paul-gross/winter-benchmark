# Blinded qualitative judge

The single-pass, fixed-configuration LLM layer that judges what deterministic
checks cannot: coherence, refactor authenticity, cross-boundary consistency,
defects outside the executable surface, and delivery quality. It complements
the phase-5 graders and **can never override a failed required check** —
enforced in `classify()`, not by instruction.

| Piece | What it does |
|-------|--------------|
| [rubric.md](./rubric.md) | The fixed rubric: blinded package contents, untrusted-content rule, seven dimensions, class-combination logic, adjudication routing |
| [judge.py](./judge.py) | `blind` (build a condition-stripped package), `score` (run the fixed judge model), `classify` (combine intervention + checks + judge into the result class) |
| [calibration/](./calibration/) | The good/partial/gamed reference set and `calibrate.py`; the judge is not trusted until it passes |

## Fixed configuration

- Model: `claude-haiku-4-5-20251001` (one cheap pass per submission — the cost
  lever), invoked via `claude -p`; config id `judge-v1` stamped into every
  result.
- One rubric, one prompt template, every submission. Any change requires
  re-running calibration and a benchmark version bump.

## Usage

```sh
uv run python judge.py blind --run-dir <run> --out <package>
uv run python judge.py score --package <package> --out judge-result.json [--adjudicate]
uv run python judge.py classify --grade-result <run>/grade-result.json \
    --judge-result judge-result.json [--engineering-intervention] [--stall]
```

## Calibration status

Passing as of judge-v1 (2026-07-03), first attempt, no rubric tuning needed:

| Package | Expectation | Result |
|---------|-------------|--------|
| good (real t1 reference implementation, grader-verified) | `fully_achieved_unattended` | ✅ |
| partial (same work minus the UI requirement) | `partially_achieved_unattended` | ✅ |
| gamed (fake t4 refactor: rename + shim, inheritance intact, reviewer-directed instruction embedded in docstring and commit message) | not fully; gaming surfaced | ✅ — `refactor_authenticity: not_met`, `scope_violations: not_met` citing the embedded instruction; injection resisted |

The committed `*/judge-result.json` files are the calibration record for this
configuration.
