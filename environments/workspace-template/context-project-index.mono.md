# Project context — the wts application

This workspace develops **winter-test-service**, a small full-stack application:
a React web UI, a FastAPI JSON API, a Postgres database, a RabbitMQ broker, and
a background worker that records and lists "items."

## Project-level conventions

| Topic | Where to read |
|-------|---------------|
| Application architecture, configuration, API surface | `winter-test-service:/README.md` |
| Commit format, delivery | [contributing.md](./contributing.md) |
| Service orchestration | Both providers are bound via `[capabilities]`. tmux manifest: [config.toml](../../.winter/config/winter-service-tmux/config.toml); docker manifest: [config.toml](../../.winter/config/winter-service-docker/config.toml) + compose file. Conventions in `winter-service-tmux:/index.md` and `winter-service-docker:/index.md`. |

Bring an environment's stack up with `winter service up <env> --wait` (or the
`./up` symlink inside the env); Postgres and RabbitMQ are workspace singletons
started automatically first. Each env gets its own database/role `wts_<env>`
and broker vhost `wts-<env>`, provisioned by `winter provision <env>`.
