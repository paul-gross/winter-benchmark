We are doing a batch of item-related work as one delivery. Complete all four
changes below together and deliver them as a single, coherent unit.

**1. Users can delete items.**

- The API exposes `DELETE /api/items/{id}`. Deleting an existing item returns
  204 and removes exactly that item; deleting an id that does not exist returns
  404.
- Deletion follows the same layering as the existing item operations: it goes
  through the persistence layer's repository seam, with no SQL outside it.
- In the web UI, every row in the items list offers a delete control, and the
  list reflects a deletion without a full page reload.

**2. The UI shows whether the background worker is alive.**

- The web UI shows a worker status indicator alongside the existing health
  badge.
- While the worker process is running, the indicator reports it as up.
- When the worker stops — for any reason — the indicator reports it as down or
  stale within 15 seconds, without the page being reloaded.
- The status must be derived from evidence that the worker is genuinely alive,
  not from configuration or assumptions.

**3. The item field "label" is renamed to "title".**

- The domain model, the database column, the API request and response JSON, any
  published message payloads, and the web UI all use `title`; no `label`
  remains anywhere in the system's public surfaces.
- Existing data is preserved: a database created before this change must come
  through the rename with the previous label values intact under the new column
  name. Apply the rename to existing databases automatically at service
  startup — do not drop and recreate the table.

**4. The persistence layer's read and write repository implementations are
separated.**

- Read operations and write operations live in distinct implementations; the
  write implementation no longer inherits from the read implementation.
- The public repository Protocols (`IReadItemRepository`,
  `IWriteItemRepository`) are unchanged, and no consuming code outside the
  persistence layer changes.

Across the whole delivery, existing behavior keeps working end to end: adding
items, listing items, the background worker, and the health badge.

Delivery expectations:

- Run the application and exercise your change against the running services;
  do not rely on reading code alone.
- When you are done, report how you verified each requirement: for every
  requirement above, state the method you used (command, request, query, or UI
  step) and the observed result that proves it.
- Commit the completed work on a feature branch. If your change spans more than
  one repository, use one consistent branch name across every repository you
  touch.
- Work unattended: make reasonable decisions yourself rather than asking
  questions, and see the task through to a committed, verified result.
