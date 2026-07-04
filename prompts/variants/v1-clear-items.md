Users want a way to start over with an empty item list.

Requirements:

- The API exposes `DELETE /api/items`. It removes every item and returns 204;
  calling it again on an already-empty list still returns 204.
- The operation goes through the persistence layer's repository seam, with no
  SQL outside it.
- The web UI offers a "Clear all" control near the items list; it asks for
  confirmation before clearing, and the list reflects the result without a full
  page reload.
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
