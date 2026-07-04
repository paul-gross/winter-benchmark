# Winter autonomy benchmark — protocol

Version: see [VERSION](./VERSION). Every change to this protocol, the fixtures, the
prompts, the graders, or the judge bumps the version; results are only comparable
within one version.

This document is the single authoritative contract for the benchmark. Fixtures
(phase 2–3), prompts (phase 4), graders (phase 5), the judge (phase 6), and the
runner (phase 7) implement against it; none of them may redefine anything fixed
here.

## Purpose

Measure how often an agent can satisfy a development request **unattended** — from
a single initial prompt to a delivered, committed change — in a plain checkout, a
Winter workspace, and a Winter workspace with `winter-workflow`, across a monorepo
and a polyrepo topology of the same application. The benchmark evaluates delivery
outcomes, not agent efficiency: the economic question is whether inexpensive agent
execution replaces expensive human attention.

## Condition matrix

Two topologies × three conditions = six cells; five prompts → 30 pilot runs.
Repository count is a fixture detail, never a run multiplier.

| Cell | Topology | Condition | Application layout | Winter workspace | winter-workflow |
|------|----------|-----------|--------------------|------------------|-----------------|
| `mono/plain` | mono | plain | one `winter-test-service` clone | no | no |
| `mono/winter` | mono | winter | matching Winter workspace | yes | no |
| `mono/winter-workflow` | mono | winter-workflow | matching Winter workspace | yes | yes |
| `poly/plain` | poly | plain | five sibling clones under one parent | no | no |
| `poly/winter` | poly | winter | matching Winter workspace | yes | no |
| `poly/winter-workflow` | poly | winter-workflow | matching Winter workspace | yes | yes |

The three conditions per topology differ **only** by Winter/workflow presence.
Application code and the pinned starting revision are identical across all six
cells (see [environments/pins.toml](./environments/pins.toml)).

## Result classes

Every run is classified into exactly one of:

1. `fully_achieved_unattended` — all required executable checks pass, the blinded
   qualitative review finds no material unmet requirement or defect, and no human
   engineering intervention occurred.
2. `partially_achieved_unattended` — useful work landed without engineering
   intervention, but at least one material requirement/check is missing,
   incorrect, or defective.
3. `not_achieved_unattended` — no usable implementation, the task was abandoned,
   or the application was left fundamentally broken.
4. `human_intervention_required` — the run needed clarification, correction,
   troubleshooting, or any other engineering judgment after the initial prompt
   (including a mechanically detected stall — see the runner's stall detection).

A failed **required** executable check can never be overruled by the LLM judge.
The judge complements deterministic correctness; it does not replace it.

## Intervention policy

Defined before any run; applied identically to every condition and every host.

**Not engineering intervention** (does not disqualify):

- A consistently automated platform approval for an action the benchmark already
  authorizes (e.g. the unattended permission posture granting a tool call). The
  same approval policy applies to every condition.
- Infrastructure recovery when the benchmark runner itself fails **before the
  agent can act** (e.g. the sandbox failed to start; the run is discarded and
  restarted from clean state, not resumed).

**Engineering intervention** (classifies the run `human_intervention_required`):

- Clarifying requirements after the initial prompt.
- Diagnosing application behavior for the agent.
- Suggesting a file, approach, or fix.
- Correcting an implementation.
- Explaining a failed test.
- Resolving a repository problem for the agent.
- Expanding the agent's authority after the run begins.

After the initial prompt the runner provides **nothing**: no clarifications,
corrections, hints, diagnostic help, or rescue actions. A run that cannot proceed
without human guidance is not an unattended success, even if a rescued final
implementation would have passed every check.

## Delivery contract

Delivery is **required** (this refines #118's "commits optional" stance):

- Every run must end with at least one commit on a **non-default feature branch**
  in every repository it changed. An uncommitted or default-branch-only change
  fails the delivery gate (a required deterministic check).
- The runner captures, per repository touched: final branch name, commit SHA(s),
  and commit message(s).
- **Branch-name cohesion** is a graded factor computed deterministically:
  - *Polyrepo:* the fraction of touched repositories whose feature branch name
    equals the modal (most common) feature branch name across touched
    repositories. 1.0 = every touched repo shares one branch name. A single
    touched repo scores 1.0 trivially.
  - *Monorepo:* cohesion is trivially 1.0; only branch-name quality is judged.
  - Cohesion and commit-message quality feed the **qualitative judge**
    (delivery-quality dimension), not the deterministic gate.

## Held-constant controls

Fixed for every run in a comparative batch:

| Control | Value policy |
|---------|--------------|
| Model | **Parameter** — `haiku` for harness dry-runs, `sonnet` for real runs; exact model id recorded per run |
| Agent host | **Parameter** — `claude` (Claude Code) first; `codex`, `opencode` later; exact host version recorded per run |
| Reasoning configuration | Host default; never varied within a batch |
| Tool permissions | Unattended posture (all tool calls auto-approved inside the sandbox); identical in every cell |
| Initial prompt | Byte-identical per task across all six cells |
| Starting revision | Pinned SHAs in `environments/pins.toml` |
| Machine resources | One sandbox spec (CPU/memory) for every cell |
| Network policy | Identical egress for every cell (package installs allowed) |
| Token/context limits | Host defaults; never varied within a batch |
| Max-run boundary | Generous wall-clock cap (default **90 minutes**) used only to break an indefinitely stuck run — hitting it without a delivered commit classifies the run `human_intervention_required` with `boundary` as the stall signal |

Everything except `model` and `host` is fixed per comparative batch. `model` and
`host` are cell coordinates recorded in every result.

## Per-run artifact manifest

Captured for judging before any teardown, stored under the results store:

| Artifact | File(s) |
|----------|---------|
| Per-repo branch + commit metadata | `delivery.json` (branch, SHA(s), messages, per-repo) |
| Full diff vs the pinned start | `diff/<repo>.patch` |
| DB snapshot (post-run, pre-teardown) | `db/items.csv` + `db/schema.sql` |
| Broker stats (queue depth, delivery counts) | `broker/stats.json` |
| Agent's final message | `final-message.md` |
| Agent-authored capability matrix | extracted into `capability-matrix.md` (from the final message) |
| Raw transcript | `transcript.jsonl` (retained for diagnosis; **never scored for process**) |
| Efficiency fields | inside `result.json` (recorded, not scored) |

## Result schema

One JSON object per run, conforming to
[`schema/run-result.schema.json`](./schema/run-result.schema.json). It contains
the cell coordinates (topology, condition, prompt, model, host), the result
class, per-check pass/fail, judge dimension scores, delivery/branch metadata,
and the recorded-but-unscored efficiency fields (wall-clock, tokens, cost,
command counts) kept only to audit condition fairness.

## Results store

```
results/<benchmark-version>/
├── runs/<run-id>/            # one directory per run
│   ├── result.json           # the schema-conformant record
│   ├── delivery.json         # per-repo branch/commit capture
│   ├── diff/<repo>.patch
│   ├── db/items.csv, db/schema.sql
│   ├── broker/stats.json
│   ├── final-message.md
│   ├── capability-matrix.md
│   └── transcript.jsonl
├── anonymized/<blind-id>.json  # blinded packages as given to the judge
└── report/                     # aggregate pilot / comparative reports
```

`<run-id>` is `<topology>-<condition>-<prompt>-<model>-<host>-r<N>` (`r<N>` is
the repetition index). Blind ids are random and the mapping is kept in
`anonymized/mapping.json`, which the judge never sees.

## Cost policy

- Implementation agents run through **subscription-billed hosts** (Claude Code on
  a Max plan, Codex/OpenCode on their subscriptions), converting dollar cost into
  weekly-quota cost.
- Deterministic checks cost **zero tokens**; as much grading as possible lives
  there rather than in the judge.
- The qualitative judge is a **single cheap-model pass** per submission (one fixed
  Haiku-class configuration).
- Budget: assume roughly **10–15 sonnet-class unattended runs per week** fit a Max
  subscription alongside normal use; the 30-cell pilot therefore spans 2–3 weekly
  windows. The runner supports checkpoint/resume: each completed cell is durable
  in the results store, and `bench run` skips cells whose result already exists
  (unless `--force`), so a batch can stop at quota and resume after reset.

## Auth & credentials

Held constant, never a per-condition variable:

- **Claude Code** — a logged-in subscription credential (`~/.claude`) mounted
  read-only into the sandbox; the same credential for every cell.
- **Codex / OpenCode** — their equivalent config/credential directories, mounted
  the same way, documented in the host adapter when those adapters are validated.
- **Judge** — runs outside the sandbox via the same Claude Code subscription
  (`claude -p`), one fixed model/config for every submission.

The credential mount is part of the sandbox spec and identical in every cell of a
batch. No cell receives extra authority via credentials.

## Host-agnostic control surface

Every host adapter accepts exactly these inputs and returns exactly these
outputs (the runner's `HostAdapter` contract, phase 7):

Inputs: workspace/checkout path, prompt text, model id, permission posture,
max-run boundary.

Outputs: exit status, final message, transcript path, efficiency fields
(wall-clock, tokens, cost where available, command counts), and a stall signal
(`completed` | `awaiting_input` | `boundary` | `crashed`).

Per-repo branch/commit capture is performed by the runner (git inspection), not
the adapter, so it cannot vary by host.

## Known limitations

- **`winter-workflow` is not host-portable.** It ships Claude Code skills and
  role-pure subagents; Codex and OpenCode have no equivalent construct. The
  `winter-workflow` condition is only fully meaningful on Claude Code; on other
  hosts it degrades toward plain-Winter or is undefined. Cross-host results for
  that condition are host-scoped and must never be pooled across hosts.
- **The three-condition design estimates the incremental product path
  `plain → Winter → Winter + workflow`.** It does not isolate whether
  `winter-workflow` behaves differently outside Winter (out of scope per #118).
  State this limitation rather than attributing differences to fully independent
  causal components.
- **The derived polyrepo is artificially clean.** Freshly derived from one mono
  commit, it has no version skew or release-coordination friction, so it may
  understate organic polyrepo difficulty. Acceptable for v1: the topology effect
  under measurement is the agent's multi-repo coordination at task time, which is
  present regardless of starting cleanliness (see
  [derive-poly/README.md](./derive-poly/README.md)).
- **The pilot makes no comparative claim.** One run per cell only validates the
  harness. Comparative claims require the frozen benchmark plus a predeclared
  repetition count (chosen after the pilot, before the comparative run).
- **No operations scoring in v1.** Service startup/recovery, log usage, orphan
  processes, and OS hygiene are not scored; efficiency fields are retained only
  to audit condition fairness.
