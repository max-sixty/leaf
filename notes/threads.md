# Threads: workflow and prototype plans

Status: document-outcome guidance, compact navigation, and agent-written summary
checkpoints are implemented. The remaining plans are proposed.
They address long conversations taking over the page, an unwieldy Threads panel,
and uncertainty about who should act next.

## Agreed direction

- Keep **Threads** as the interface name; a message is one contribution.
- Threads hold active discussion. Incorporate decisions, reference material, and
  deferred tasks into the document, then resolve the discussion when appropriate.
  Resolved history remains accessible. Do not create a permanent idle Open or Later
  category to hold material that belongs in the document.
- Keep rows compact: topic, anchor, and a short status label. Do not add a sentence
  explaining the next action to every row. Details belong inside the thread.
- Show attention counts in the banner and fuller filtering in the panel. Use the same
  compact navigation at every thread count, without a threshold-triggered layout switch.
- Expand on explicit selection, with a keyboard route, rather than pointer hover.

## Activity and attention ontology

The [thread status proposal](thread-status-proposal.md) owns the proposed design.
The [activity inventory](activity-ontology.md) records existing producers, storage,
value sets, consumers, and the investigation behind it.
The implementation still follows the shipped session-lifetime and event contracts.

Keep the reader-facing grouping small while retaining exact delivery, work, and
settlement evidence underneath it. The next slice should make banner, thread,
and margin attention agree; independently observed jobs and continuation follow it.

## Live specimens and further Thread surfaces

The package Thread contract lives in
[packages.md](../skills/leaf/references/packages.md#widget-local-thread-surfaces).
A live playground specimen is separate work: host a complete, isolated Leaf page
and event log with readiness, resize, reset, and explicit focus entry and return.
Use the diff-with-Threads case to exercise production package and conversation UI.

A future package that needs interactive authored messages inline must ask Leaf to
move its single live instance out of the panel. That needs focus, retained-node, and
presentation-proof contracts. Page-wide Thread placement also needs Leaf-owned
arbitration when multiple widgets request the same Thread; the current API places
only exact datum Threads belonging to the consuming widget.

## Workflow and attention model

Consolidate delivery receipts, work claims, live reply evidence, and interruption
handling into the projected workflow. Derive attention consistently for the banner,
panel, and margin. Start with states Leaf can establish today; external dependency
evidence is a separate plan below. Do not redesign panel navigation in this change.

Prove queued input while earlier work continues, an unanswered turn ending, a stale
claim, failed delivery, and a reply settling only an older message. Check that each
recovery label offers a meaningful action and that all surfaces agree.

Reconcile the existing TODOs for margin status colour, later replies masking earlier
questions, and delegated work outliving the coordinator. Those are concrete cases for
this model, not reasons to add independent status rules at each surface.

## Compact thread navigation

The selected compact accordion is implemented in the thread panel. A title row opens
one conversation in place; the others retain their message and editor nodes while
collapsed. Message counts share a column, message status follows its relative time in
the author row, and the reply field spans the conversation width. The [playground](thread-navigation/README.md)
retains the spacing study and supplies a seeded conversation fixture.

The runtime owners document disclosure, keyboard, draft, and arrival behavior beside
the code. Existing delivery readings supply compact status labels; the richer workflow
model above remains a separate backend change. Long-history compression below remains
independent of collapsing whole conversations.

## Long-thread reading

Fold older history while preserving opening context, the current exchange, outstanding
questions, and actionable controls. Handle individual oversized messages too. Revealing
a search match must expand its hidden context; incoming replies must preserve reading
position. Include a route to the latest exchange.

Decide the lifetime of reader read-position before adding First unread: browser-session
position and a durable unread record are different contracts. Do not add durable state
merely to support local folding.

Test recovering an earlier argument, answering the current question, expanding a long
message, and inspecting new messages without scroll jumps or hidden obligations.
Develop independently of the workflow model; evaluate within the chosen navigation.
Summary generation is outside this slice.

## Move outcomes into the document — complete

The [Leaf skill](../skills/leaf/SKILL.md) makes the document the current shared
record. [Live revision guidance](../skills/leaf/references/authoring-revisions.md)
owns updating decisions, status, and deferred work; [thread guidance](../skills/leaf/references/conversation-threads.md)
owns linking outcomes to discussion and keeping review open.

## External waits and continuation

Make Waiting on CI an explicit contract: identify the dependency, retain responsibility
for resuming, and establish how continuation happens. Distinguish an observed job with
a functioning resumption mechanism from an agent merely promising to check later.

Prove success resumes work, failure reaches the appropriate owner, and a lost observer
or absent continuation mechanism cannot leave a reassuring Waiting label indefinitely.
Cover delegated work that remains active after its coordinator's turn ends. This builds
on the workflow model and remains independent of compact navigation.

## Summary checkpoints — implemented

The shipped event contract and agent workflow live in
[events](../skills/leaf/scripts/leaf/events.md) and
[conversation threads](../skills/leaf/references/conversation-threads.md#summarize-a-long-discussion).
The core gallery exercises the real summary UI. Browser coverage includes keyboard
disclosure, search and direct-message arrivals, outstanding questions, replacement,
and edits to covered messages. Inline conversations retain the full transcript.

## Sequence and shared evidence

Compact navigation and summary checkpoints are implemented. Long-thread reading remains
independent of the workflow model; pursue external waits after the workflow model.

Use one shared fixture corpus: a sparse page, many mixed-status threads, a long exchange,
an oversized message, an unanswered question, queued input during older work, a healthy
external wait, interrupted progress, and an unfinished draft. Compare candidates using
real Leaf components and the same seeded history. Exercise direct gestures and keyboard
routes in light/dark themes and wide/narrow layouts. Preserve calm document prose and
compact working chrome.

These are separate experiments and implementation slices, not one combined rewrite.
As each lands, move its established contract into the owning code or public reference
and retire the corresponding plan here.
