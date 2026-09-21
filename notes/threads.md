# Threads: workflow and prototype plans

Status: the document-outcome guidance is complete; the remaining plans are proposed.
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

## Proposed ontology

The grouping answers **what the reader needs to do**. The label explains why.

| Reader's next action | Group | Example label |
| --- | --- | --- |
| Answer, decide, or review | Needs you | Answer / Review |
| Inspect or recover interrupted progress | Needs you | No recent activity / Delivery failed |
| Let established progress continue | Waiting | Queued / Working / Replying |
| Wait for an identified dependency | Waiting | Waiting on CI |
| Nothing remains in the discussion | Resolved | Resolved |

No recent activity is evidence that progress is uncertain, not proof of failure. Offer
inspection before retry. A healthy long-running job must not become Needs you merely
because its coordinating agent is quiet. A failure that the agent can recover from
without reader involvement should not manufacture a reader obligation.

A thread contains obligations and their history. An obligation is an outstanding answer
or action; satisfying one may leave another. Activity describes progress toward that
obligation. The agent may be answering an earlier message while a newer one is queued,
so one mutable status on the whole thread is insufficient.

For implementation, combine delivery, execution, and progress validity into one
projected workflow state per obligation, rather than three freely combinable enums.
Candidate states are sending, sent, queued, picked up, working, replying, waiting on a
dependency, and interrupted. Carry only relevant payloads: a dependency and continuation
owner for waiting, or a reason and last established progress for interruption. This is a
design to test against the current evidence, not a finalized schema.

Keep thread resolution and reader read-position separate. Raw delivery and lifetime
evidence remains underneath the projection; UI consumers do not independently combine
it. Never infer Replying or Waiting on CI from ordinary prose or silence.

For a thread containing both reader and agent obligations, Needs you takes placement
precedence while the opened thread retains the agent's activity. Count distinct threads
in thread filters; do not confuse that count with the number of Asks. A reply does not
automatically create another reader obligation or resolve its discussion. An unresolved
thread awaiting nobody needs an appropriate completion flow, not automatic closure
based solely on the absence of an obligation.

### Existing foundations

The [event contract](../skills/leaf/scripts/leaf/events.md) owns thread resolution,
explicit response settlement, and reader questions. The
[session-lifetime contract](../skills/leaf/scripts/leaf/session-lifetime.md) owns pickup,
work claims, and the canonical activity reading.

Today, Sent means Leaf accepted the move; Queued means the host accepted delivery;
Picked up identifies the agent turn it entered; Working requires current work evidence.
Existing interruption readings include Was working and Picked up · turn ended. A live
reply is provisional until committed. Page/session availability is not itself progress
on every thread. Preserve these evidence distinctions while simplifying their projection.

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

Prototype two operable treatments using the actual thread components:

- **Expand in place:** selection expands one row and collapses the previous selection.
- **Focused conversation:** selection opens the conversation in place of the list;
  Back restores the list and its position.

Both preserve drafts, selection, focus, and reading positions; expose search and its
active filters; support keyboard traversal and movement between a thread and its anchor;
and retain agent activity beside the message it belongs to. Compare page-side behaviour
for short discussions with opening a long discussion in the panel.

Test finding a thread needing an answer, visiting its anchor, replying, switching to
another thread, and returning to an unfinished draft. Use both sparse and crowded pages.
Focused conversation is the starting preference, not a settled choice. This work can
start with existing status readings and adopt the workflow model when ready.

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
on the workflow model and must not delay the navigation prototype.

## Summary checkpoints

Compare folded history with a short checkpoint describing decisions and remaining
questions. Identify covered messages, link claims to originals, and keep later messages
visibly outside that coverage. Summaries cannot settle obligations or resolve threads.

Start with clearly labelled seeded summaries to test comprehension; add generation only
if the comparison establishes value. Test recovering original reasoning, recognizing
what changed after the checkpoint, and answering the current question correctly.
This follows long-thread reading and does not block folding without summaries.

## Sequence and shared evidence

Start the workflow model and compact navigation independently. Add long-thread
reading to the chosen navigation; pursue external waits after the workflow model
and summaries after folding.

Use one shared fixture corpus: a sparse page, many mixed-status threads, a long exchange,
an oversized message, an unanswered question, queued input during older work, a healthy
external wait, interrupted progress, and an unfinished draft. Compare candidates using
real Leaf components and the same seeded history. Exercise direct gestures and keyboard
routes in light/dark themes and wide/narrow layouts. Preserve calm document prose and
compact working chrome.

These are separate experiments and implementation slices, not one combined rewrite.
As each lands, move its established contract into the owning code or public reference
and retire the corresponding plan here.
