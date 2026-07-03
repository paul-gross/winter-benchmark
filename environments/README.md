# Benchmark environments — pinned workspaces and plain baselines

Every cell starts from identical, pinned state. [`build_env.py`](./build_env.py)
reconstructs any of the four environment definitions from clean state with a
single command; [`pins.toml`](./pins.toml) holds every SHA involved.

## The four definitions

| Definition | Command | Agent starts in |
|------------|---------|-----------------|
| Plain mono baseline | `build_env.py --topology mono --condition plain --dest D` | `D/winter-test-service/` (pinned clone) |
| Plain poly baseline | `build_env.py --topology poly --condition plain --dest D` | `D/wts/` (five pinned sibling clones + task-neutral parent README) |
| Mono Winter workspace | `build_env.py --topology mono --condition winter --dest D --bootstrap` | `D/workspace/` |
| Poly Winter workspace | `build_env.py --topology poly --condition winter --dest D --bootstrap` | `D/workspace/` |

`--condition winter-workflow` builds the same workspace with the
`winter-workflow` extension additionally declared — **the only difference**
between the `winter` and `winter-workflow` conditions.

## How reconstruction works

1. **Pinned local origins.** Each needed repository is bare-cloned from a local
   source checkout into `<dest>/.origins/<name>.git` with `master` forced to
   its pinned SHA. Clones never touch the network or a moving branch. Poly
   fixture origins are produced by running the
   [derive-poly generator](../derive-poly/) against the pinned mono commit.
2. **Plain baselines** clone straight from those origins. Setup/test
   instructions are the repos' own READMEs (mono) plus the generated parent
   README (poly) — accurate, task-neutral, and containing the real run
   commands. No Winter workspace context is copied in: discovery and
   preparation are part of what Winter contributes.
3. **Winter workspaces** clone the pinned winter framework revision and commit
   the benchmark workspace configuration on top (`.winter/config.toml`, service
   manifests, `context/project/`). `--bootstrap` then runs:

   ```
   winter ws init                       # clone project repos from the pinned origins
   winter ws init alpha                 # create the feature environment
   winter service up workspace --wait   # start the shared Postgres + RabbitMQ singletons
   winter provision alpha               # install deps; carve out wts_alpha db + wts-alpha vhost
   ```

   The prepared state leaves infrastructure singletons up and **application
   services down** — starting the app is the agent's job in every condition.

## Fairness checks (documented per #121)

- **Identical application state.** All six cells start from the same
  `winter-test-service` commit; the poly fixture is derived from that exact
  commit and checksum-verified byte-identical.
- **Equivalent runtime.** Docker with the same `postgres:16` and
  `rabbitmq:3-management` images is available in every cell (the runner
  pre-pulls both so no condition pays a first-pull network cost). Plain
  baselines start them via the documented `docker run` commands in their
  READMEs; Winter conditions start them via the workspace's service
  orchestration. Neither condition hides essential commands.
- **Real instructions in plain cells.** The mono README and the generated poly
  READMEs contain the genuine, complete run/test commands (they are the same
  documents a human developer would use), reviewed for task-neutrality — no
  task hints, no evaluation hints.
- **No Winter context in plain cells.** Nothing from `context/`, `AGENTS.md`,
  or the extensions is copied into a plain baseline.
- **Hidden-check leak guard.** The workspace's winter pin predates `bench/`,
  and the builder deletes `bench/` defensively before committing the workspace
  configuration, so prompts/graders can never be agent-visible in any cell.

## Requirements

`git`, `python3`, `uv`, `node`/`npm`, `docker`, and — for `--bootstrap` — the
`winter` CLI (`<workspace>/tools/winter-cli/install.sh`, which needs `mise`).
