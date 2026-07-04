In the persistence layer, the write repository implementation currently
inherits from the read implementation, so the read and write concerns are
tangled into one inheritance chain. Separate them.

Requirements:

- Read operations and write operations live in distinct implementations; the
  write implementation no longer inherits from the read implementation.
- The public repository Protocols (`IReadItemRepository`,
  `IWriteItemRepository`) are unchanged, and no consuming code outside the
  persistence layer changes.
- Behavior is fully preserved: every repository operation — health ping,
  listing, schema initialization, adding items — works exactly as before
  against the running application.

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
