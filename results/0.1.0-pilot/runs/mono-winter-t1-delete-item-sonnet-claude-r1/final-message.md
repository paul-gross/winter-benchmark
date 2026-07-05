Committed on branch `alpha` (single repo touched: `winter-test-service`, commit `ed5206e`). Services remain running at API `:6031` / web `:6030` for any further inspection.

## Summary

**Implementation** (following the existing repository-pattern layering, no SQL outside `wts_persistence/internal/item_repository.py`):
- `wts_persistence/repositories/item_repository.py` — added `delete_item(item_id) -> bool` to the `IWriteItemRepository` Protocol seam.
- `wts_persistence/internal/item_repository.py` — implemented it in `WriteItemRepository` via `session.get`/`session.delete`, returning `False` if the row doesn't exist, wrapping `SQLAlchemyError` like the other methods.
- `api/app/services/item_service.py` — added `ItemNotFoundError` and `ItemService.delete_item`, mirroring the existing `ItemValidationError` pattern.
- `api/app/main.py` — added `DELETE /api/items/{item_id}` (204 on success), catching `ItemNotFoundError` → 404.
- `web/src/App.tsx` — added a "Delete" button per row; on success it removes the row from React state (no reload); on failure it shows an inline error.
- `README.md` — documented the new endpoint.

**Verification against the running app** (alpha env, API on :6031, web on :6030, Postgres/RabbitMQ via docker):

| Requirement | Method | Result |
|---|---|---|
| `DELETE /api/items/{id}` returns 204 and removes exactly that item | `curl -X POST .../api/items` to create id 28, confirmed present in `GET /api/items`, then `curl -X DELETE .../api/items/28` | `204`; item 28 absent from subsequent `GET /api/items` |
| Deleting a non-existent id returns 404 | Re-deleted id 28 (`404`), and deleted id `999999999` (`404`) | Both returned `404` |
| Goes through the repository seam, no SQL outside it | Code inspection: only `wts_persistence/internal/item_repository.py` issues SQLAlchemy calls; service/API layers depend only on the `IWriteItemRepository` Protocol | Confirmed by diff |
| Deletion actually removes the DB row | `docker exec wtsb-postgres psql ... SELECT COUNT(*) FROM items WHERE id=<new_id>` before/after a create+delete round-trip | Count went 65→66 on add, row count for that id was `0` after delete |
| Every row offers a delete control; list updates without full reload | Playwright/Chromium driving the real web UI at `localhost:6030`: added an item via the UI, clicked its row's "Delete" button, waited for the row to detach from the DOM, and set a JS marker beforehand to prove the page context survived (no reload) | Row appeared then disappeared; `NO_FULL_RELOAD_MARKER_SURVIVED: true`; zero console errors |
| Existing behavior (add, list, health badge) still works | Same Playwright run: waited for health badge "API ok / DB ok", added an item via the form, saw it listed; plus direct `curl GET /api/health` → `{"status":"ok","db":"ok"}` and `GET /api/items` returning the worker's ongoing heartbeat rows | All passed |