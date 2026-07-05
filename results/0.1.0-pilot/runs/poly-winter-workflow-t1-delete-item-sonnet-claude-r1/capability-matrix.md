
- **wts-persistence** (`4f5ee51`): `ItemNotFoundError`, `IWriteItemRepository.delete_item`, `WriteItemRepository.delete_item` (SQL confined to `internal/`), plus a new pytest suite.
- **wts-api** (`f09921a`): `ItemService.delete_item`, `DELETE /api/items/{item_id}` route (204/404), plus a new pytest suite.
- **wts-web** (`c381fa5`): per-row delete button + `handleDelete` using local React state filtering (no reload).