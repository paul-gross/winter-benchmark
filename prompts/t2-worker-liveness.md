The application runs a background worker alongside the API, but operators
cannot tell from the UI whether that worker is actually alive right now.

Requirements:

- The web UI shows a worker status indicator alongside the existing health
  badge.
- While the worker process is running, the indicator reports it as up.
- When the worker stops — for any reason — the indicator reports it as down or
  stale within 15 seconds, without the page being reloaded.
- The status must be derived from evidence that the worker is genuinely alive,
  not from configuration or assumptions.
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
