# Winter autonomy benchmark

An outcome-oriented benchmark measuring how often an agent satisfies a
development request **unattended** — from one initial prompt to a delivered,
committed change — across two application topologies (monorepo, polyrepo) and
three conditions (plain checkout, Winter workspace, Winter workspace +
`winter-workflow`).

The single authoritative contract is [protocol.md](./protocol.md). Everything
else implements it.

| Piece | Where | What it does |
|-------|-------|--------------|
| Protocol | [protocol.md](./protocol.md) | Condition matrix, result classes, intervention policy, delivery contract, controls, artifact manifest, cost/auth policy |
| Result schema | [schema/run-result.schema.json](./schema/run-result.schema.json) | Machine-readable per-run record |
| Polyrepo generator | [derive-poly/](./derive-poly/) | Deterministically derives the five-repo polyrepo fixture from `winter-test-service` |
| Environments | [environments/](./environments/) | Pinned, reproducible workspaces and plain baselines for all six cells |
| Prompts | [prompts/](./prompts/) | The five fixed task prompts + comparative-run variants |
| Graders | [graders/](./graders/) | Hidden deterministic checks: Playwright suite, evidence capture, delivery gate |
| Judge | [judge/](./judge/) | Blinded qualitative review + result-class assignment |
| Runner | [runner/](./runner/) | `bench run` — reset → launch → capture → grade → emit, with pluggable agent hosts |
| Results | `results/<version>/` | Per-run records, diffs, anonymized packages, reports |

## Quick start

```sh
# Derive the polyrepo fixture from the pinned mono commit
uv run bench/derive-poly/derive_poly.py --out /tmp/poly-fixtures

# Run a single cell (see runner/README.md for the sandbox prerequisites)
uv run bench/runner/bench.py run \
  --topology mono --condition plain --prompt t1-delete-item \
  --model haiku --host claude
```

**The `graders/` and `prompts/variants/` trees must never be visible to an
implementation agent.** The runner guarantees this by construction (the sandbox
only mounts the cell's environment); keep it true for any manual run too.
