# Thread status: proposed canonical model

Status: proposed, not implemented. Based on the
[source inventory](activity-ontology.md). This proposal owns the next design;
the inventory records the current implementation and supporting evidence.

## Consolidate message workflow; derive thread attention

Combine interaction receipts, local send state, and response-stream state into
one shared workflow reading. Derive thread attention from those readings and
the thread's outstanding reader Asks. Keep explicit thread resolution separate.

For message-bound work, the workflow is about an exact input and the work answering it. It is not one
mutable state on the whole conversation, and not every informational message
creates work. A response stream belongs to its response address; it must not
mark a newer input as answered. Proactive work keeps its subject binding even
when there is no input event; it appears on that thread or widget, not beside
a nonexistent message timestamp.

This consolidates classifiers and UI vocabulary, while preserving native
delivery, turn, claim, and response records. A work claim can exist without a
pickup event; the displayed stage selects the strongest applicable evidence,
not a mandatory sequence through every stage.

### Proposed shared reading

| Field             | Meaning                                                                 | Examples                                                          |
| ----------------- | ----------------------------------------------------------------------- | ----------------------------------------------------------------- |
| Identity/bindings | Subject, source input when present, delivery/turn/response references   | Existing ids; no new persisted workflow id                        |
| Stage             | Strongest established progress on this input or response                | Sending, sent, queued, picked up, working, replying, answered     |
| Activity          | Optional typed refinement of current work; retain concurrent activities | Thinking, tool execution; later independent job/delegation        |
| Condition         | A problem or uncertainty, with its evidence and affected operation      | Send failed, turn interrupted, observation stale, response failed |
| Next actor        | Who owes an action, derived from outstanding work and Asks              | Reader, agent, nobody                                             |

These are projection fields, not new tables. The condition qualifies the known
stage instead of erasing it or multiplying every stage into stale/failed variants.
An ended turn retains Picked up history and says Turn ended; Interrupted
requires a known interruption outcome. Successful settlement wins over obsolete execution trouble.
Sending/refusal originate in the browser's unresolved ledger until admission;
the shared presentation contract must support that local overlay.

Thinking and tool execution require typed host evidence plus an explicit
input/subject binding to refine local workflow. A shared turn or event floor
alone does not establish that binding; unbound observations remain overall
page activity. If the subtype is unavailable, show Working. A job that outlives its launching tool will need its own identity,
observer and continuation owner; do not infer it from a status sentence.
Answered requires actual settlement, not merely a completed host turn.

### What the reader sees

Messages get one compact status beside the timestamp. Use the most useful
current label from the shared reading: Sending, Sent, Queued, Picked up,
Working, Thinking, Replying, or a specific interruption/recovery label.
An answered input normally loses its active-work mark; do not add a permanent
Answered badge to every message. The existing reply remains the evidence.
The separately dispatched placement/button refinement remains independent.

Thread attention is an aggregation, not another workflow state machine:

| Reading                                                     | Placement / behavior                                                                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Concrete reader Ask or reader-owned recovery                | Needs you; the reason distinguishes Answer from Inspect/Retry                        |
| Agent owes work with established delivery/work/continuation | Waiting; show the strongest useful workflow detail                                   |
| Agent owes work but progress is uncertain                   | Show the uncertainty; use Needs you only if a concrete reader recovery action exists |
| Nobody owes work                                            | No attention mark; retain explicit open/resolved lifecycle and resolution control    |
| Explicitly resolved                                         | Resolved history; resolution does not manufacture a job cancellation                 |

Reader action takes placement precedence over concurrent agent work; the latter
remains available as secondary detail. Count distinct threads, not messages or
Asks. An unrelated agent update must not silently clear a standing reader Ask;
settlement must follow the Ask's own answer, widget-state, or reaction contract.
Deferred tasks and outcomes still belong in the document.

## Page state describes the overall agent relationship

Keep page/session state separate from message workflow. It answers whether this
page has an owner, whether the carrier is reachable/listening, whether the
agent is currently active, and what the agent says it is doing overall.

Do not label a message Working merely because the page's agent is active.
Do not label the page Picked up as though it were one message. The banner can
compose overall agent state with explicitly scoped thread counts, such as
“Agent active · 2 threads need you”; those counts remain an aggregate, not the
page's execution state. Page and message readings may share raw evidence without
sharing their classification or identity.

No immediate change to claim lifetime, watcher leases, or stop-guard obligation
semantics is implied by removing overlapping display classifications. Keep those
contracts while replacing their reader-facing projection coherently.

## External requests are commands, not chat delivery

These power buttons asking a host to perform an operation. Existing examples
include command-hub host operations and a release rollback request.
Leaf records the request; the package/host supplies its meaning and executes it;
a terminal receipt records success or failure. Leaf is not itself the rollback
executor merely because a button was accepted.

Each request seat permits one pending operation. Success completes it; failure
reopens it. This protects operations whose external effect may precede the
receipt. Chat pickup cannot prove that operation succeeded.

Keep that command lifecycle. It may contribute activity and attention through
its exact request identity, using the same UI treatment where appropriate.
Do not replace success/failure receipts with Sent/Picked up, or treat acceptance
as a completed job. This slice does not change the request protocol.

## Notifications: transitions, with an event bus deferred

Message workflow, thread attention, page availability, and request outcomes can
all produce meaningful transitions. A future notification bus can let the
bottom status line, accessible announcements, badges, and other consumers
subscribe to typed changes.

Keep that bus out of the first implementation. When designed, inspect the
existing publication/subscription machinery before adding a parallel transport.
Domain state remains authoritative; a notification is a report of a transition,
not a second state store. Subscribers own filtering, coalescing, and presentation.
Do not notify on every heartbeat or tool step. Durable unread tracking is also
deferred and requires its own definition of what the reader has seen.

## Implementation slices

**First: shared message workflow and thread attention.** Define the reading from
existing facts, replace independent compact-row/receipt/attention precedence,
and use it consistently in thread rows, message marks and margin entries. Keep
the browser's immediate Sending/refusal overlay and exact response bindings.
Prove a reader Ask concurrent with older agent work, newer input during a reply,
an ended turn, a stale observation, an unrelated reply, and a single turn
covering two subjects without attributing its activity to both.

**Second: overall page-state separation.** Give banner and Leaves tray the same
overall availability/activity reading, composing separately labeled thread
counts. Prove that an active session never upgrades unrelated message work and
that an unavailable carrier does not become an invented job failure.

**Third: richer observed work.** Retain typed thinking/replying/tool signals,
then independently observed jobs and delegated work with continuation. Use the
same message-workflow reading without changing its responsibility semantics.

**Deferred: typed notification subscriptions and unread tracking.** These can
consume the earlier readings once their transitions are stable.

The first two slices form the recommended initial implementation. They share
one source of evidence while giving each UI level a distinct question to answer.
