Committed to branch `feature/delete-items`. Here's the summary of the change and verification.

## Changes

- **Persistence seam** (`wts_persistence/`): added `delete_item(item_id) -> bool` to the `IWriteItemRepository` Protocol and implemented it in `WriteItemRepository` using a SQLAlchemy `delete()` statement scoped to `internal/item_repository.py` (the only file allowed to touch SQLAlchemy) — returns whether a row was actually removed via `rowcount`.
- **Service layer** (`api/app/services/item_service.py`): `ItemService.delete_item(id)` delegates to the repository, following the same pattern as `add_item`.
- **API route** (`api/app/main.py`): `DELETE /api/items/{item_id}` returns 204 on success, 404 when `delete_item` reports nothing was removed.
- **Web UI** (`web/src/App.tsx`): every item row now has a "Delete" button; on success it removes the row from React state directly (no refetch/reload required), with per-row pending/disabled state and an error message on failure.

## Verification (ran the real stack, not just reading code)

- Started Postgres in Docker, `uv sync`, `npm install`, ran the API (`PYTHONPATH=.:api uv run python -m app`) and the Vite dev server.
- **DELETE existing → 204, removes exactly that item**: `POST /api/items` created id `1`; `curl -X DELETE /api/items/1` → `204`; `GET /api/items` → `[]`; confirmed directly in Postgres via `psql -c "select id,label from items"` → `0 rows` — the row is truly gone, not just filtered in the response.
- **DELETE missing id → 404**: `curl -X DELETE /api/items/9999` → `404`.
- **Layering / no SQL outside the repo seam**: verified by inspection that `delete()` is only used inside `wts_persistence/internal/item_repository.py`, reached through `ItemService` → `IWriteItemRepository`, matching `add_item`'s existing shape.
- **UI: delete control per row, no full reload**: drove the running app with a real headless Chromium (Playwright) against `http://localhost:9000` — added an item via the UI, confirmed it appeared, clicked its "Delete" button, and confirmed the row detached from the DOM (`ROW_COUNT_BEFORE_DELETE: 1` → `ROW_COUNT_AFTER_DELETE: 0`) without any navigation/reload, then re-confirmed via `psql` that the row was gone from the DB.
- **Existing behavior intact**: same Playwright run first asserted the health badge showed "API ok / DB ok", then exercised "Add item" (label appeared in the table) before deleting — all working alongside the new delete path.
- Cleaned up afterward: killed the API/vite processes and stopped/removed the `wts-db` container.