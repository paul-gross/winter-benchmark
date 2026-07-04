#!/usr/bin/env bash
# Scripted 'agent' for the fake host (zero-token harness self-test, winter
# mono): the agent starts at the workspace root; the work lands in the alpha
# feature environment's worktree, committed on the env's feature branch —
# exactly the workspace's documented convention.
set -euo pipefail

cd alpha/winter-test-service
git apply "$(dirname "${BASH_SOURCE[0]}")/t1-reference.patch"
git commit -aq -m "feat(items): support deleting items via API and web UI

Add delete_item through the write repository seam, expose
DELETE /api/items/{id} (204, 404 on missing), and offer a per-row
Delete control in the items table that refreshes the list in place."

cat <<'MSG'
Implemented item deletion end to end in the alpha feature environment and
verified it against the running services.

| Requirement | Method | Observed result |
|---|---|---|
| DELETE existing item returns 204 and removes it | curl -X DELETE localhost:6031/api/items/3 then GET /api/items | HTTP 204; the row no longer listed |
| DELETE missing id returns 404 | curl -X DELETE localhost:6031/api/items/999999 | HTTP 404 |
| Deletion goes through the repository seam | delete_item added to IWriteItemRepository + SQLAlchemy adapter; route calls the service | no SQL outside the persistence layer |
| Per-row delete control, list updates without reload | clicked Delete on a row in the browser | row disappeared in place, no navigation |
| Existing behavior keeps working | added and listed items via UI and API; health badge checked | all green |

Committed on the alpha feature branch.
MSG
