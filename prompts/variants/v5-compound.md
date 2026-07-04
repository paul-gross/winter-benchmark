We are doing a batch of item and messaging work as one delivery. Complete all
four changes below together and deliver them as a single, coherent unit.

**1. Users can clear the item list.**

- The API exposes `DELETE /api/items`. It removes every item and returns 204;
  calling it again on an already-empty list still returns 204.
- The operation goes through the persistence layer's repository seam, with no
  SQL outside it.
- The web UI offers a "Clear all" control near the items list; it asks for
  confirmation before clearing, and the list reflects the result without a full
  page reload.

**2. The UI shows whether the worker's broker publishes are getting through.**

- The web UI shows a broker delivery indicator alongside the existing health
  badge.
- While the worker's publishes are being delivered to the broker, the indicator
  reports delivery as flowing.
- When publishes stop getting through — for any reason, including the broker
  being unreachable — the indicator reflects that within 15 seconds, without
  the page being reloaded.
- The status must be derived from evidence of actual delivery, not from
  configuration or assumptions.

**3. The item field "source" is renamed to "origin".**

- The domain model, the database column, the API response JSON, and the web UI
  all use `origin`; no `source` remains anywhere in the system's public
  surfaces.
- The set of allowed values is unchanged and every writer keeps recording the
  correct value.
- Existing data is preserved: a database created before this change must come
  through the rename with the previous source values intact under the new
  column name. Apply the rename to existing databases automatically at service
  startup — do not drop and recreate the table.

**4. The messaging layer's connection management and publishing are
separated.**

- Connection/channel lifecycle management and message publishing are
  implemented by distinct components; the publisher no longer manages raw
  connection state itself.
- The public publisher Protocol (`IHeartbeatPublisher`) is unchanged, and no
  consuming code outside the messaging layer changes.

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
