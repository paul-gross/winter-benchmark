#!/usr/bin/env bash
# Scripted 'agent' for the fake host (zero-token harness self-test, poly
# plain): the agent starts at the sibling-clones parent; the t1 reference
# change lands across the three affected repositories on one cohesive feature
# branch name. The mono-pathed reference patch is split by path prefix
# (byte-identical sources make the hunks apply verbatim).
set -euo pipefail

PATCH="$(dirname "${BASH_SOURCE[0]}")/t1-reference.patch"
MSG="feat(items): support deleting items via API and web UI"

(cd wts-persistence \
  && git checkout -q -b feature/delete-item \
  && git apply --include='wts_persistence/*' "$PATCH" \
  && git commit -aq -m "$MSG

Add delete_item to the write repository Protocol and the SQLAlchemy adapter.")

(cd wts-api \
  && git checkout -q -b feature/delete-item \
  && git apply -p2 --include='app/*' "$PATCH" \
  && git commit -aq -m "$MSG

Expose DELETE /api/items/{id} (204; 404 on a missing id) through the item service.")

(cd wts-web \
  && git checkout -q -b feature/delete-item \
  && git apply -p2 --include='src/*' "$PATCH" \
  && git commit -aq -m "$MSG

Per-row Delete control in the items table; the list refreshes in place.")

cat <<'FINAL'
Implemented item deletion end to end across the api, persistence, and web
repositories and verified it against the running services.

| Requirement | Method | Observed result |
|---|---|---|
| DELETE existing item returns 204 and removes it | curl -X DELETE localhost:7503/api/items/3 then GET /api/items | HTTP 204; the row no longer listed |
| DELETE missing id returns 404 | curl -X DELETE localhost:7503/api/items/999999 | HTTP 404 |
| Deletion goes through the repository seam | delete_item added to IWriteItemRepository + adapter in wts-persistence | no SQL outside the persistence layer |
| Per-row delete control, list updates without reload | clicked Delete on a row in the browser | row disappeared in place, no navigation |
| Existing behavior keeps working | added and listed items via UI and API; health badge checked | all green |

Committed on branch feature/delete-item in every repository touched.
FINAL
