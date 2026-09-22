# Remaining Thread plans

Compact navigation, agent-written summary checkpoints, shared Thread surfaces,
live specimens, and message workflows are implemented. Leaf suggests an older
contiguous range when a discussion grows long; the agent reads it and writes the
summary. Readers can unfold the original messages, and the agent can replace an
overlapping summary as the discussion grows. Their contracts live in
[conversation threads](../skills/leaf/references/conversation-threads.md),
[session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md), and
[the package Thread API](../skills/leaf/references/packages.md#widget-local-thread-surfaces).
The [playground](thread-navigation/README.md) retains the design comparisons.

## Notifications and unread state

The canonical workflow already records exact-input delivery, work, response,
condition, and next actor. The Thread collection supplies stable message identities
and attention derived from workflows and outstanding reader Asks. The page activity
reading remains separate, and native requests have their own terminal receipts.
These are the source facts for notification decisions; no second message-status
ontology is needed.

First decide which changes deserve notice: an agent answer, a new reader obligation,
a failed or interrupted response, a page becoming available, or a native request
outcome. A stage change such as Sent to Picked up, a heartbeat, or a tool step does
not by itself demand a notification. Compare successive canonical readings using
stable ids, then let subscribers choose the status line, accessible announcement,
Thread control, or another destination. The application publisher already updates
semantic readings; the bottom status line and live region already show brief notices.
Inspect these before adding a transition bus or new transport.

Unread is a separate fact about what the reader has seen, not a workflow stage or
the same thing as Needs you. The current `viewed` timestamp means a tab had the page
visible; it does not say which Thread or reply was read. Define the read boundary and
lifetime (tab-local or durable) before adding unread counts, First unread, or badges.
Keep notification coalescing and read state out of the canonical message workflow.

## Independent jobs, delegation, and continuation

Develop an ontology for work that outlives the turn or tool that started it: what
identifies a job, who observes it, who resumes the conversation, and which events
establish running, waiting, success, failure, or lost observation. Distinguish a
delegated agent, a background command, and an external dependency such as CI. Test
the model against a coordinator ending while its delegate continues and against a
watcher losing contact. Waiting on CI should mean an observed dependency with a
working resumption path, not a phrase in status text.

Native request buttons retain their one-shot command lifecycle, whose outcome
may precede its receipt. Job observations must preserve that contract: chat
pickup cannot prove the external operation succeeded.

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

## Later: long-thread reading

See how agent-written summary checkpoints work in real long discussions before
adding another fold. If readers still struggle, fold unsummarized history or
individual oversized messages while preserving opening context, the current
exchange, outstanding questions, and actionable controls. Search and direct-message
navigation must reveal hidden matches; new replies and folding must preserve reading
position. Test recovering an earlier argument and answering the current question
without hidden obligations or scroll jumps. Keep read-position and unread-state
decisions with the notification plan above.
