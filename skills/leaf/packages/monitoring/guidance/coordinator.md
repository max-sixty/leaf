# Release page coordinator

The page's summary, checks, and log describe the observed release. Keep them current
from the deployment system rather than interpreting the log in the browser.

A `rollback` request from `lf-release-actions` is a one-shot instruction to the host.
Before acting, verify that the authored `candidate` is still receiving traffic and that
the authored `stable` release is still the intended rollback target. Use the request id
as the operation's idempotency key: on recovery, inspect the deployment system for that
request or its result before sending another rollback. A button press means requested,
not completed.

After the deployment system accepts or refuses the operation, record exactly one result:

```bash
leaf receipt "$PAGE" <request-id> succeeded --text "Rollback to checkout-v1 completed"
# or
leaf receipt "$PAGE" <request-id> failed --text "checkout-v1 is no longer eligible"
```

Refresh the release observations and save a new authored revision when the result changes
the release state. Do not acknowledge the event batch until the request has reached the
durable deployment executor.
