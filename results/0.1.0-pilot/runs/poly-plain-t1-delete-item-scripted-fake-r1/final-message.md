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