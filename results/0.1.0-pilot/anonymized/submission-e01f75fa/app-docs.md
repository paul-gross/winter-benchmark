# winter-test-service

A small full-stack application — a React web UI, a FastAPI JSON API, a Postgres database, and a background worker — that records and lists "items." Alongside the normal functionality it exposes a handful of diagnostic controls for driving its runtime behavior — crashes, slow boots, and error output — on demand.

Every setting has a sensible default, so the whole stack runs locally with no configuration.

## Architecture

- **web** — a React + Vite single-page UI: lists items, adds items, shows an API/DB health badge, and can trigger a controlled API crash.
- **api** — a FastAPI/uvicorn service: serves item read/create and health, and exposes the diagnostic endpoints.
- **worker** — a background Python loop that writes a heartbeat row to the database on a fixed cadence, and publishes each heartbeat to a RabbitMQ queue.
- **db** — Postgres 16, run as a Docker container.
- **broker** — RabbitMQ. The worker publishes each heartbeat to a `heartbeats` queue. In a winter workspace this is the shared `wws-rabbitmq` singleton, with a per-env vhost provisioned by `winter provision <env>` (see [Per-env RabbitMQ vhost](#per-env-rabbitmq-vhost) below).

The api and worker share one persistence layer (`wts_persistence/`): SQLAlchemy ORM entities and read/write repositories behind Protocol interfaces, with a domain service in the api that owns the item-creation rules. Neither service writes SQL directly. The worker's broker access follows the same shape in `wts_messaging/`: a pika publisher behind a Protocol interface, with pika confined to `wts_messaging/internal/`. Everything runs from source against one `uv`-managed virtualenv.

## Configuration

Everything is an environment variable with a default; override any of them in the shell. Defaults live in the code and in the commands below — there is no config file to edit.

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://wts:wts@localhost:5545/wts` | api + worker database connection |
| `WTS_API_PORT` | `7503` | api listen port (and the web dev-server's `/api` proxy target) |
| `WTS_API_HOST` | `0.0.0.0` | api listen host |
| `WTS_WEB_PORT` | `9000` | web dev-server port |
| `WTS_BOOT_DELAY_SECONDS` | `0` | api: sleep this long before binding (simulate a slow boot) |
| `WTS_WORKER_INTERVAL_SECONDS` | `2` | worker: seconds between heartbeats |
| `WTS_WORKER_CRASH_AFTER` | `0` (never) | worker: exit(1) after this many ticks |
| `RABBITMQ_URL` | derived (see below) | worker: full AMQP URL — overrides the derived per-env URL |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` | `localhost` / `5672` | worker: broker host/port when `RABBITMQ_URL` is unset |

Every default lives in the code (or `vite.config.ts` for the web port) — there is nothing to configure to run locally. The database host/port/credentials are all part of `DATABASE_URL`.

The broker is a **soft** dependency: if it can't be reached, the worker logs a warning and keeps writing DB heartbeats, retrying the publish each tick. So a missing or un-provisioned vhost shows up as recurring warnings rather than a dead worker.

### Per-env RabbitMQ vhost

The worker resolves its AMQP URL in this order:

1. `RABBITMQ_URL` if set — used verbatim.
2. else if `WINTER_ENV` is set (running inside a winter feature env) — `amqp://wts-<env>:wts-<env>@$RABBITMQ_HOST:$RABBITMQ_PORT/wts-<env>`, i.e. the per-env vhost + user provisioned by `winter provision <env>`.
3. else — `amqp://guest:guest@localhost:5672/` (the default `/` vhost, for a plain local run).

In a winter workspace, the vhost/user `wts-<env>` is created in the shared `wws-rabbitmq` broker by a `[[provision.resource]]` handler. Run `winter provision <env>` after `winter ws init <env>`, then start the services. `winter provision <env> resource --destroy` removes the vhost.

## Running locally

```sh
# 1. Install dependencies (Python venv via uv, web deps via npm)
uv sync
( cd web && npm install )

# 2. Start Postgres in Docker — first, in its own terminal
#    (publishes localhost:5545, persists data in the named volume wts-pgdata)
docker run --rm --name wts-db \
  -e POSTGRES_USER=wts -e POSTGRES_PASSWORD=wts -e POSTGRES_DB=wts \
  -p 5545:5432 -v wts-pgdata:/var/lib/postgresql/data postgres:16

# 2b. (optional) Start RabbitMQ for the worker's heartbeat publisher.
#     Without it the worker just logs publish warnings and keeps running.
docker run --rm --name wts-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# 3. Start the api, worker, and web UI — each in its own terminal
PYTHONPATH=.:api uv run python -m app
uv run python -m worker.main
( cd web && npm run dev )

# 4. Open the UI
open http://localhost:9000
```

`PYTHONPATH=.:api` puts the repo root (for the shared `wts_persistence`/`wts_logging` modules) and `api/` (for the `app` package) on `sys.path`; the worker needs only the root, which `python -m` already adds. The api binds `WTS_API_PORT` (`7503`) by default — no port argument needed. To point at your own Postgres instead of the container, set `DATABASE_URL`.

## Database schema

The api creates this table idempotently on startup; both the api and worker write to it:

```sql
CREATE TABLE IF NOT EXISTS items (
  id         BIGSERIAL PRIMARY KEY,
  label      TEXT NOT NULL,
  source     TEXT NOT NULL,           -- 'api' (user-added) or 'worker' (heartbeat)
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## API

- `GET  /api/health` — `{status, db}`, where `db` is `ok` or `down`.
- `GET  /api/items` — recent items, newest first.
- `POST /api/items` — body `{ "label": "..." }`; inserts a `source='api'` row and returns it.
- `POST /api/chaos/crash` — hard-crash the api process (`os._exit(1)`).
- `POST /api/chaos/error-log?n=N` — write N error lines to stderr (default `5`).

Requests are logged to stdout; warnings and errors go to stderr.

## Messaging

The worker publishes each heartbeat as a persistent JSON message (`{env, tick, label}`) to a durable `heartbeats` queue in its resolved vhost (see [Per-env RabbitMQ vhost](#per-env-rabbitmq-vhost)). Inspect it against the shared broker with:

```sh
docker exec wws-rabbitmq rabbitmqctl list_queues -p wts-<env>     # message count
docker exec wws-rabbitmq rabbitmqctl list_vhosts                  # confirm wts-<env> exists
```

## Requirements

- **Docker**
- **[uv](https://docs.astral.sh/uv/)** — Python environment and dependency manager. Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Python 3.12+
- Node 20+
