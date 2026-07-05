# wts — polyrepo application

A small full-stack application — a React web UI, a FastAPI JSON API, a Postgres
database, and a background worker — that records and lists "items," split
across five repositories cloned side by side:

| Repository | What it is |
|------------|------------|
| `wts-web` | React + Vite single-page UI |
| `wts-api` | FastAPI/uvicorn JSON API |
| `wts-worker` | background heartbeat worker |
| `wts-persistence` | shared persistence/domain library (used by api + worker) |
| `wts-messaging` | shared messaging library (used by worker) |

The api and worker consume the two libraries as uv path dependencies
(`../wts-persistence`, `../wts-messaging`), so keep the five checkouts as
siblings under this directory.

## Running the stack locally

```sh
# 1. Start Postgres in Docker — first, in its own terminal
#    (publishes localhost:5545, persists data in the named volume wts-pgdata)
docker run --rm --name wts-db \
  -e POSTGRES_USER=wts -e POSTGRES_PASSWORD=wts -e POSTGRES_DB=wts \
  -p 5545:5432 -v wts-pgdata:/var/lib/postgresql/data postgres:16

# 1b. (optional) Start RabbitMQ for the worker's heartbeat publisher.
#     Without it the worker just logs publish warnings and keeps running.
docker run --rm --name wts-rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# 2. Install dependencies and start each service — each in its own terminal
( cd wts-api && uv sync && uv run python -m app )
( cd wts-worker && uv sync && uv run python -m worker.main )
( cd wts-web && npm install && npm run dev )

# 3. Open the UI
open http://localhost:9000
```

Every setting is an environment variable with a sensible default — see each
repository's README for its configuration table and details.

## Requirements

- **Docker**
- **[uv](https://docs.astral.sh/uv/)** — Python environment and dependency manager. Install: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
- Python 3.12+
- Node 20+
