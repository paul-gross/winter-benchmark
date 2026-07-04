The background worker publishes events to a message broker, but operators
cannot tell from the UI whether those publishes are actually getting through.

Requirements:

- The web UI shows a broker delivery indicator alongside the existing health
  badge.
- While the worker's publishes are being delivered to the broker, the indicator
  reports delivery as flowing.
- When publishes stop getting through — for any reason, including the broker
  being unreachable — the indicator reflects that within 15 seconds, without
  the page being reloaded.
- The status must be derived from evidence of actual delivery, not from
  configuration or assumptions.
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
