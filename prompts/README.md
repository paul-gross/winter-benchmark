# Prompt suite

The five fixed task prompts, delivered verbatim as the agent's single initial
message. **This directory (like all of `bench/`) must never be visible to an
implementation agent** — see the leak guard in
[../environments/README.md](../environments/README.md).

## Invariants (enforced by construction)

- **One file per task, byte-identical across all six cells.** The runner reads
  the file and passes it verbatim; there are no per-condition versions to
  drift.
- **No condition bias in the text.** Prompts never mention Winter, repository
  paths or names, workspace tooling, expected workflow selection, or evaluation
  criteria. They describe the desired application outcome and constraints as a
  developer delegating the task.
- **Standing delivery expectations** appear identically in every prompt (source
  of truth: [standing-instructions.md](./standing-instructions.md)): exercise
  the running services, report per-requirement verification methods and
  observed results (the bench-internal "capability matrix" artifact — that name
  never appears in prompt text; see BIAS-REVIEW finding S1), commit on a
  cohesively named feature branch, work unattended. The prompt states the
  branch-cohesion requirement without revealing that it is scored.
- **Hidden traps stay hidden.** Nothing in the prompt text mentions the
  worker-rows trap (the worker also writes `items` rows with `source='worker'`
  and publishes heartbeats, so item-list changes fail if worker rows are
  ignored), the contract-boundary misses graded by task 3, or any hidden check.

## The five tasks

| Id | Category | Task | Central difficulty (bench-internal; never in the prompt) |
|----|----------|------|----------------------------------------------------------|
| `t1-delete-item` | Simple feature | `DELETE /api/items/{id}` + per-row UI delete | seam bypass, 404 semantics, list desync |
| `t2-worker-liveness` | Complex feature | UI indicator for worker aliveness with a 15s staleness bound | discovering the worker's heartbeat evidence; up→down transition |
| `t3-rename-label-title` | Cross-repo refactor | rename `label`→`title` across every public surface with an in-place startup migration | contract-boundary misses (DB, API JSON, message payload, UI); data-preserving migration |
| `t4-repository-split` | Single-repo refactor | split read/write repository implementations; Protocols unchanged | behavior preservation provable only by exercising every method |
| `t5-compound` | Compound | all four in one delivery | long-horizon coordination; rename interacts with the other three |

Task 2's 15-second staleness bound and task 3's migrate-at-startup requirement
are stated in the prompts deliberately: they turn otherwise-vague qualities
into deterministic, solution-independent checks without revealing how the
checks are performed.

## Comparative-run variants

[variants/](./variants/) holds fresh drafts exercising the same capability
categories without reusing the pilot's exact changes (`v1-clear-items`,
`v2-broker-delivery-status`, `v3-rename-source-origin`,
`v4-publisher-connection-split`, `v5-compound`). Their hidden checks are
deliberately **not** authored yet — they are written at comparative-run time,
after the pilot freezes the harness, and are never available to any
implementation agent. Note: `v3` does not touch the messaging library's payload
(the `source` field does not travel in heartbeat messages), so its cross-repo
span is four of five repos; acceptable for the category, recorded here for the
comparative-run design.

## Bias review

The suite requires sign-off from a reviewer who did not design Winter's
workflow; the review record lives in [BIAS-REVIEW.md](./BIAS-REVIEW.md).
