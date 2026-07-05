We need users to be able to remove items they no longer want.

Requirements:

- The API exposes `DELETE /api/items/{id}`. Deleting an existing item returns
  204 and removes exactly that item; deleting an id that does not exist returns
  404.
- Deletion follows the same layering as the existing item operations: it goes
  through the persistence layer's repository seam, with no SQL outside it.
- In the web UI, every row in the items list offers a delete control, and the
  list reflects a deletion without a full page reload.
- Existing behavior — adding items, listing items, the health badge — keeps
  working.

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
