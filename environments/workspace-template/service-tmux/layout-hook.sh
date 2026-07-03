#!/usr/bin/env bash
# Layout hook for the benchmark workspace tmux session — pane geometry ONLY.
# Window 0: 0.0=api, 0.1=web, 0.2=worker (creation-order indices matching
# config.toml targets). The orchestrator starts services after this exits.

set -euo pipefail

: "${WINTER_TMUX_SESSION:?WINTER_TMUX_SESSION not set}"
: "${WINTER_TMUX_WORKTREE_DIR:?WINTER_TMUX_WORKTREE_DIR not set}"

tmux split-window -h -t "${WINTER_TMUX_SESSION}:0.0" \
  -c "${WINTER_TMUX_WORKTREE_DIR}"                    # pane 0.1 (web)
tmux split-window -v -t "${WINTER_TMUX_SESSION}:0.0" \
  -c "${WINTER_TMUX_WORKTREE_DIR}"                    # pane 0.2 (worker)
tmux select-layout -t "${WINTER_TMUX_SESSION}:0" tiled
