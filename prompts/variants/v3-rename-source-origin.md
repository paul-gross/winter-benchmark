Product has renamed the item field "source" to "origin". Rename it across the
entire system, at every point where the field appears or is exposed.

Requirements:

- The domain model, the database column, the API response JSON, and the web UI
  all use `origin`; no `source` remains anywhere in the system's public
  surfaces.
- The set of allowed values is unchanged and every writer keeps recording the
  correct value.
- Existing data is preserved: a database created before this change must come
  through the rename with the previous source values intact under the new
  column name. Apply the rename to existing databases automatically at service
  startup — do not drop and recreate the table.
- The application keeps working end to end after the rename — adding items,
  listing items, the background worker, and the health badge.

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
