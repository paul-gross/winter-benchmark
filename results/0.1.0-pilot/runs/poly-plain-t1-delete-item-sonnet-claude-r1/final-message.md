All services and containers are stopped and cleaned up.

## Summary

Implemented item deletion across the three affected repos, all on branch `feature/delete-item`:

- **wts-persistence**: added `delete_item(item_id) -> bool` to `IWriteItemRepository` and to `WriteItemRepository` (SQLAlchemy `delete()` scoped to `internal/item_repository.py`, the only file with SQL).
- **wts-api**: added `ItemService.delete_item`, and route `DELETE /api/items/{item_id}` → 204 on success, 404 if `service.delete_item` returns `False`.
- **wts-web**: added a per-row "Delete" button that calls `DELETE /api/items/{id}` and removes the row from React state on success — no reload.

### Verification (ran the real stack: Postgres in Docker, `uv run python -m app`, `npm run dev`)

- **DELETE removes exactly that item, returns 204**: `curl -X DELETE http://localhost:7503/api/items/1` → `status=204`, empty body. Follow-up `GET /api/items` showed only item `2` remaining. Confirmed directly in Postgres: `psql -c "select id,label from items"` → only row `2 | second` left.
- **Deleting a non-existent id returns 404**: re-deleting id `1` → `status=404 {"detail":"item not found"}`; deleting a never-used id `9999` → same `404`.
- **Repository seam / no SQL outside it**: `delete_item` lives only in `wts_persistence/internal/item_repository.py` (the file already holding all other item SQL); the API only calls through `IWriteItemRepository`/`ItemService`, verified by reading the diff and confirming no new SQL appears in `wts-api`.
- **UI delete without full reload**: drove the running dev server (`localhost:9000`) with Playwright/Chromium — added an item via the UI, clicked its row's Delete button, and confirmed the row disappeared from `tbody` while `page.url()` stayed `http://localhost:9000/` (no navigation/reload occurred).
- **Existing behavior intact**: same Playwright session first confirmed the "API ok / DB ok" health badge rendered, then added an item via the UI form (`ui-added-item` appeared in the table) — both pre-existing flows still work after the change. `npx tsc --noEmit` in `wts-web` passed with no errors.

Commits (same branch name `feature/delete-item` in each repo):
- `wts-persistence` `1acca63` — Add delete_item to the write item repository seam
- `wts-api` `0b572d5` — Add DELETE /api/items/{id} endpoint
- `wts-web` `6dffaa2` — Add per-row delete control to the items list

All local services/containers used for verification have been stopped; working trees are clean.