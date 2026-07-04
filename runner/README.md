# Runner — one command, one cell

`bench.py run` executes a single benchmark cell end to end and emits one
schema-conformant result record:

```sh
python3 bench/runner/bench.py run \
  --topology mono|poly --condition plain|winter|winter-workflow \
  --prompt t1-delete-item --model haiku|sonnet --host claude|codex|opencode|fake
```

## The five steps

1. **Reset** — rebuild the cell's pinned environment from clean state
   (`environments/build_env.py`; winter conditions bootstrap the workspace and
   provision the alpha env; poly fixtures regenerate from the pinned mono
   commit). Both service images are pre-pulled so no condition pays a network
   cost.
2. **Launch** — the selected host adapter runs the unattended agent with the
   held-constant controls (prompt verbatim, model, unattended permission
   posture, max-run boundary, default 90 min). After the initial prompt,
   nothing: the intervention policy is enforced by there being no channel.
3. **Capture** — before any teardown: per-repo branch/commits/messages, the
   full final-state diff (committed + uncommitted), DB snapshot and broker
   stats from the agent's own runtime, the final message, the extracted
   capability matrix, and the raw transcript.
4. **Grade** — the phase-5 hidden suite runs against a *freshly launched copy*
   of the final code (clone + working-tree overlay, so history-based
   structural checks and uncommitted state both grade correctly), then the
   phase-6 blinded judge, then result-class assignment (a failed required
   check can never be upgraded).
5. **Emit** — one `result.json` per run under
   `bench/results/<version>/runs/<run-id>/`, including the recorded-but-never-
   scored efficiency fields. An existing result skips the cell
   (checkpoint/resume across weekly quota windows); `--force` re-runs.

## Stall detection (mechanical `human_intervention_required`)

Per adapter: `boundary` (max-run wall-clock hit — the process is killed),
`crashed` (host exited non-zero / error result), and `awaiting_input`
(completed without a committed delivery while the final message ends in a
question). The firing signal is recorded in `stall.signal` and any stall
classifies the run `human_intervention_required`.

## Host adapters ([hosts/](./hosts/))

All adapters accept the same inputs (workdir, prompt, model, boundary) and
return the same outputs (stall signal, final message, transcript, efficiency
fields) — the host-agnostic control surface from the protocol. Branch/commit
capture is done by the runner with git, so it cannot vary by host.

| Host | Status |
|------|--------|
| `claude` | **Implemented + validated** — headless `claude -p --output-format stream-json --dangerously-skip-permissions`; token/cost/turn counts parsed from the stream |
| `codex` | Stub behind the contract; refuses to run until its invocation is validated (`hosts/codex.py`) |
| `opencode` | Stub behind the contract; same guard (`hosts/opencode.py`) |
| `fake` | Scripted zero-token agent for harness self-tests (`BENCH_FAKE_SCRIPT`); not an experimental condition |

The `winter-workflow` condition is only fully meaningful on Claude Code
(protocol §Known limitations); cross-host results for it are host-scoped.

## Isolation

`--sandbox docker` (default) delegates the whole cell into a disposable
privileged container built from [sandbox/Dockerfile](./sandbox/Dockerfile):
its own docker daemon (the cell's Postgres/RabbitMQ and anything the agent
starts live inside), the bench tree and pinned sources mounted read-only, the
results directory as the only writable host mount, and the host credential
directory mounted read-only (held constant across cells). Destroyed after
capture. **Status: validated 2026-07-03** — a full fake-host cell ran inside
the sandbox end to end (reset → agent → capture → grade → blinded judge via the
mounted credential → `fully_achieved_unattended`). Two requirements baked in
from that validation: `--sources-dir` must contain real clones (git worktrees
are rejected — their `.git` files point outside the mount), and the inner
docker daemon gets an anonymous volume at `/var/lib/docker` because
overlay-on-overlay cannot extract image whiteouts.

`--sandbox none` runs on the host for harness development only. It performs
best-effort cleanup (winter service teardown, fixture containers, processes in
the cell tree) and must never run two winter cells concurrently (fixed `wtsb`
namespace).

## Self-test (zero tokens)

```sh
BENCH_FAKE_SCRIPT=$PWD/bench/runner/selftest/t1-mono-agent.sh \
python3 bench/runner/bench.py run --topology mono --condition plain \
  --prompt t1-delete-item --model scripted --host fake --sandbox none \
  --results-root /tmp/bench-selftest
```

Expected: `fully_achieved_unattended`, 13/13 checks, result.json validating
against `schema/run-result.schema.json` (verified 2026-07-03).
