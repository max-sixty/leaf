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

The table is a presentation policy, not the stored ontology. Preserve detailed facts
so the interface can aggregate them differently without reconstructing lost information.
The proposed data model below replaces the earlier single workflow enum per obligation.

Keep thread resolution and reader read-position separate. Raw delivery and lifetime
evidence remains underneath the projection; UI consumers do not independently combine
it. Never infer Replying or Waiting on CI from ordinary prose or silence.

For a thread containing both reader and agent obligations, Needs you takes placement
precedence while the opened thread retains the agent's activity. Count distinct threads
in thread filters; do not confuse that count with the number of Asks. A reply does not
automatically create another reader obligation or resolve its discussion. An unresolved
thread awaiting nobody needs an appropriate completion flow, not automatic closure
based solely on the absence of an obligation.

### Proposed data model

Separate an outstanding obligation from the attempts and activities that serve it.
These are conceptual records to map onto existing events and claims, not new stores
beside them. Field names and event types remain provisional.

| Record | Identity and relationships | Facts it carries |
| --- | --- | --- |
| Thread | Existing thread identity | Messages, anchor, explicit resolution |
| Obligation | Source event or Ask identity; thread; responsible actor | Requested answer, decision, review, or action; explicit settlement |
| Attempt | Attempt identity; exact obligations; session and turn where applicable | Delivery and execution lifecycle; outcome; retry relationship |
| Activity | Activity identity; attempt; parent activity where applicable | Kind, lifecycle, observation source and time; external identity and continuation when needed |

An obligation can survive a failed attempt. A successful job can leave the obligation
unsettled until the agent incorporates its result. Several activities can coexist:
the agent can reason while two jobs run, and a new message can be queued while an
earlier one is being answered. Bind work to exact obligations; session activity alone
does not prove that every thread is progressing.

**Attempt lifecycle:** `sent`, `queued`, `picked_up`, `running`, then
`succeeded`, `failed`, `cancelled`, or `interrupted`. Keep transition evidence rather
than only overwriting the latest state. Sending and local send failure belong to the
browser's unresolved gesture until admission succeeds; they are not accepted log events.
Use only stages the carrier actually observes, without inventing intermediate receipts.

**Activity kind:**

| Kind | Meaning | Required evidence |
| --- | --- | --- |
| `thinking` | The model is actively generating reasoning | A typed host signal; never inferred from silence |
| `replying` | The model is producing a reader reply | A response stream bound to its destination |
| `tool_call` | A tool invocation is executing | Invocation identity and start/end observations |
| `job` | Work has an independently observable lifetime | Job identity and a way to observe its lifecycle |
| `delegation` | Another agent owns an execution step | Worker/task identity and a way to observe it |
| `working` | Work is established, but its subtype is unavailable | A current work claim or host observation |

Each activity has a small lifecycle: `pending`, `running`, `succeeded`, `failed`,
or `cancelled`. Losing observation does not manufacture a terminal outcome.
Long-running is a duration characteristic, not another kind: a synchronous tool can
take a long time, while a short background job still has its own lifetime. A tool
that launches a job completes separately from the job it launched.

**Dependencies and continuation:** link an attempt to the activity or external
condition that must complete before its next step. Record who resumes it and the
registered mechanism that will notify or wake that owner. Waiting is derived from
those outstanding dependencies, not stored as another kind of activity. A job may
still be running after its agent turn ends; its observer and continuation determine
whether that is healthy waiting or needs inspection.

**Observation:** retain the producer, observed time, and source-specific lease or
next expected check where one exists. Derive freshness at read time. Distinguish
"job failed" from "we no longer know whether the job is running." Model activity,
job observation, and the continuation mechanism have separate lifetimes. An old
progress timestamp alone does not establish failure or a reader obligation.

### Storage and projection

Use the existing append-only page log for admitted durable transitions and exact
relationships: delivery/pickup, settlement, and proposed job/dependency registrations
and terminal outcomes. Retain existing actor and source identities so retries and
duplicate notifications cannot create duplicate work or settle a newer obligation.
Admission validates references and allowed transitions once.

Keep current high-frequency activity observations in the existing status/host lifetime
mechanism: typing deltas and heartbeats need not become durable page events. A restart
can recover registered work and terminal facts; current liveness must be re-established.
External systems remain authoritative for their jobs; Leaf records attributed
observations rather than claiming to own their execution state. Do not introduce a
persisted thread-status table or a second current-state file.

Extend the canonical server activity projection to join these facts. It returns the
detailed attempts, concurrent activities, dependencies, and uncertainty as well as the
small reader-facing grouping and label. All browser surfaces consume that projection.
Uncertainty qualifies the retained activity rather than multiplying every lifecycle
state into variants such as `thinking_stale` and `job_running_stale`.

For example, an obligation can have a running job and no active model turn. With a live
job observer and a registered continuation it presents as **Waiting · Running tests**.
If that continuation disappears, retain the job's observed state and surface the
recovery need. When the job succeeds, the obligation remains outstanding while the
resumed agent thinks, replies, or updates the document. Only its settlement closes it.

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

The selected compact accordion is implemented in the thread panel. A title row opens
one conversation in place; the others retain their message and editor nodes while
collapsed. Message counts share a column, author/time headers precede messages, and
the reply field spans the conversation width. Delivery receipts follow their message. The [playground](thread-navigation/README.md)
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
