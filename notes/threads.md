# Remaining Thread plans

Compact navigation, summary checkpoints, shared Thread surfaces, live specimens,
and message workflows are implemented. Their contracts live in
[conversation threads](../skills/leaf/references/conversation-threads.md),
[session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md), and
[the package Thread API](../skills/leaf/references/packages.md#widget-local-thread-surfaces).
The [playground](thread-navigation/README.md) retains the design comparisons.

## Long-thread reading

Fold older history while preserving opening context, the current exchange,
outstanding questions, and actionable controls. Handle individual oversized
messages too. Revealing a search match must expand its hidden context; incoming
replies must preserve reading position. Include a route to the latest exchange.

Decide the lifetime of reader read-position before adding First unread:
browser-session position and a durable unread record are different contracts.
Do not add durable state merely to support local folding.

Test recovering an earlier argument, answering the current question, expanding a
long message, and inspecting new messages without scroll jumps or hidden
obligations. Build on the shipped summary checkpoints and accordion.

## Independent jobs, delegation, and continuation

Give work that outlives its launching tool an identity, observer, and continuation
owner. Waiting on CI must mean an observed dependency with a working resumption
path. Cover success, failure, lost observation, and a coordinator ending while its
delegate continues. Do not infer these facts from status prose or page-wide activity.

Native request buttons retain their one-shot command lifecycle, whose outcome
may precede its receipt. Job observations must preserve that contract: chat
pickup cannot prove the external operation succeeded.

## Notifications and unread state

Design typed transition subscriptions for workflows, reader Asks, page availability,
and native request outcomes. Inspect the existing publication/subscription machinery
before adding a transport. Domain state stays authoritative; subscribers own
filtering, coalescing, and presentation. Avoid notifications for every heartbeat
or tool step. Durable unread tracking separately needs a definition of what a
reader has seen.

## Further Thread placement

A package that needs interactive authored messages inline must ask Leaf to move
its single live instance out of the panel. That needs focus, retained-node, and
presentation-proof contracts. Page-wide Thread placement also needs Leaf-owned
arbitration when multiple widgets request the same Thread; the current API places
only exact datum Threads belonging to the consuming widget.

## Shared evidence

Use real Leaf components and the same seeded histories: sparse and crowded pages,
a long exchange, an oversized message, an unanswered question, queued input during
older work, a healthy external wait, interrupted progress, and an unfinished draft.
Exercise direct gestures and keyboard routes in light/dark themes and wide/narrow
layouts. Keep these independent slices; retire each plan when its contract lands.
