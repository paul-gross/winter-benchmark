# Project context — the wts application

This workspace develops the **wts application**, a small full-stack system
split across five repositories:

| Repository | What it is |
|------------|------------|
| `wts-web` | React + Vite single-page UI |
| `wts-api` | FastAPI/uvicorn JSON API |
| `wts-worker` | background heartbeat worker |
| `wts-persistence` | shared persistence/domain library (used by api + worker) |
| `wts-messaging` | shared messaging library (used by worker) |

The api and worker consume the two libraries as uv path dependencies pointing
at sibling checkouts, which is exactly how the worktrees are laid out inside a
feature environment.

## Project-level conventions

| Topic | Where to read |
|-------|---------------|
| Per-repo architecture, configuration, run commands | each repository's `README.md` |
| Commit format, delivery | [contributing.md](./contributing.md) |
| Service orchestration | Both providers are bound via `[capabilities]`. tmux manifest: [config.toml](../../.winter/config/winter-service-tmux/config.toml); docker manifest: [config.toml](../../.winter/config/winter-service-docker/config.toml) + compose file. Conventions in `winter-service-tmux:/index.md` and `winter-service-docker:/index.md`. |

Bring an environment's stack up with `winter service up <env> --wait` (or the
`./up` symlink inside the env); Postgres and RabbitMQ are workspace singletons
started automatically first. Each env gets its own database/role `wts_<env>`
and broker vhost `wts-<env>`, provisioned by `winter provision <env>`.
