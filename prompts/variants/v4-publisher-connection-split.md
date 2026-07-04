In the messaging layer, the AMQP publisher currently owns its broker connection
lifecycle inline — connecting, reconnecting, and channel management are tangled
into the same class that does the publishing. Separate them.

Requirements:

- Connection/channel lifecycle management and message publishing are
  implemented by distinct components; the publisher no longer manages raw
  connection state itself.
- The public publisher Protocol (`IHeartbeatPublisher`) is unchanged, and no
  consuming code outside the messaging layer changes.
- Behavior is fully preserved against the running application: publishes flow
  when the broker is up, a broker outage still surfaces as the same publish
  error to callers with recovery on the next attempt, and `ping`/`close` work
  exactly as before.

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
