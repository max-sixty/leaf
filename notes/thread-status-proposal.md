# Thread status: implementation and remaining work

The message-workflow consolidation is implemented locally after the shared
Thread collection landed in PR 914. It awaits landing; validation and rendered
comparisons are in the [shared playground](thread-navigation/playground.html).

Interaction receipts, browser sending/failure state, and response progress now
produce one message-workflow reading. Thread attention combines that reading
with outstanding reader Asks. Overall page activity and typed host observations
from #21 and #22 remain separate.

The owning contracts are [session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md)
for evidence and projection, and [the Thread API](../skills/leaf/references/packages.md#widget-local-thread-surfaces)
for package consumers. The [source inventory](activity-ontology.md) records the
pre-consolidation investigation, not the current API.

## Remaining work

### Independent jobs and delegation

Give work that outlives its launching tool an identity, observer, and continuation
owner. Waiting on CI must mean an observed dependency with a working resumption
path. Cover success, failure, lost observation, and a coordinator ending while its
delegate continues. Do not infer these facts from status prose or page-wide activity.

### Notifications and unread state

Design typed transition subscriptions for workflow, reader Asks, page availability,
and native request outcomes. Inspect the existing publication/subscription machinery
before adding a transport. Domain state stays authoritative; subscribers own
filtering, coalescing, and presentation. Avoid notifications for every heartbeat
or tool step. Durable unread tracking separately needs a definition of what a
reader has seen.

### Native external requests

Request buttons already have a durable one-shot command lifecycle: acceptance
hands work to the host, success completes the seat, and failure reopens it.
Chat delivery cannot prove the external operation succeeded. Preserve this
lifecycle when adding job observations or notifications; the current consolidation
does not change the request protocol.
