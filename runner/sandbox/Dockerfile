# Disposable benchmark sandbox: one cell per container, destroyed after
# capture. Privileged so it runs its OWN docker daemon (the cell's Postgres/
# RabbitMQ and any containers the agent starts live inside the sandbox, never
# on the host) — full host and cross-cell isolation.
#
# Build:  docker build -t winter-bench-sandbox bench/runner/sandbox
# Used by: bench.py run --sandbox docker  (the default)

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Base toolchain: identical for every cell (held-constant machine policy).
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl git rsync jq tmux procps psmisc \
        python3 python3-venv \
        docker.io \
    && rm -rf /var/lib/apt/lists/*

# Node 22 (agents need it for the web app; graders need it for Playwright).
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# uv + mise: the Python/env toolchain winter and the fixtures use.
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && curl -fsSL https://mise.run | env MISE_INSTALL_PATH=/usr/local/bin/mise sh

# Agent hosts. Claude Code first (the validated adapter); codex/opencode can
# be layered in when their adapters are validated.
RUN npm install -g @anthropic-ai/claude-code

# Playwright browser + system deps preinstalled so grading pays no network
# cost inside the sandbox.
RUN npm install -g playwright@1.61.1 && npx playwright install --with-deps chromium

# Compose v2 plugin: the winter conditions' docker orchestrator drives
# `docker compose`, which the bare docker.io package does not ship.
RUN apt-get update && apt-get install -y --no-install-recommends docker-compose-v2 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /work
