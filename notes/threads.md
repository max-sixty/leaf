# Remaining Thread plans

The current contracts live in
[threads](../skills/leaf/references/threads.md),
[session lifetime](../src/leaf/session-lifetime.md), and
[the module Thread API](../skills/leaf/references/module-annotations.md#widget-local-thread-placement).

## Current status

Summary checkpoints condense historical ranges; they do not provide a continuously
current reading of what is decided and what remains open. Try an agent-maintained
line at the Thread's head before adding another fold. Decide whether it extends a
checkpoint or is a separate reading, which events invalidate it, and how a user sees
that it is stale. Use a real long discussion with a reopened question as the control.

## Independent jobs, delegation, and continuation

Develop an ontology for work that outlives the turn or tool that started it: what
identifies a job, who observes it, who resumes the conversation, and which events
establish running, waiting, success, failure, or lost observation. Distinguish a
delegated agent, a background command, and an external dependency such as CI. Test
the model against a coordinator ending while its delegate continues and against a
watcher losing contact. Waiting on CI should mean an observed dependency with a
working resumption path, not a phrase in status text.

## Shared evidence

Use real Leaf widgets and the same seeded histories: sparse and crowded pages,
a long exchange, an oversized message, an unanswered question, queued input during
older work, a healthy external wait, interrupted progress, and an unfinished draft.
Exercise direct gestures and keyboard routes in light/dark themes and wide/narrow
layouts. Keep these independent slices; retire each plan when its contract lands.

## Later: long-thread reading

See how agent-written summary checkpoints work in real long discussions before
adding another fold. If users still struggle, fold unsummarized history or
individual oversized messages while preserving opening context, the current
exchange, outstanding questions, and actionable controls. Search and direct-message
navigation must reveal hidden matches; new replies and folding must preserve reading
position. Test recovering an earlier argument and answering the current question
without hidden obligations or scroll jumps.
