# Activity and attention: inventory and canonicalization

Status: supporting inventory, grounded in checkout `965369b9`.
The [thread status proposal](thread-status-proposal.md) supersedes the exploratory
recommendations below and owns the current design.
This is the next workflow slice in [the thread plans](threads.md), not an
implemented schema. The shipped boundary is
[session lifetime](../skills/leaf/scripts/leaf/session-lifetime.md).

## Questions the model must answer

1. Which exact reader move has been admitted, queued, picked up, or answered?
2. Who owes the next action, and what action can they take?
3. Is the agent working on this move, an earlier move, or unrelated page work?
4. What is declared work, and what has the host actually observed?
5. Does silence mean an ended turn, lost observation, or continuing external work?
6. Can a reply or job finish without settling the reader's request?
7. What changed that merits notifying this reader, independently of who owes work?
8. Can the banner, message, thread, margin, and agent tools explain the same facts?

Scope: page and thread work, its delivery and observation, and reader attention.
Service reachability, browser transport, durable requests, and transient notices
intersect this scope but retain their own lifecycles. A server being reachable is
not proof that an agent is doing the requested work.

## Findings

Leaf already has a canonical server activity fold. Extend that owner rather than
introducing another status service. The work is to give its inputs and outputs
clear meanings, retain evidence currently reduced to prose, and consolidate
reader-attention policy where it is still assembled for each surface.

The central collision is **waiting**. A declaration of `waiting` invites reader
input without proving it is owed; an interaction phase of `waiting` means pickup
is overdue; the proposed **Waiting** thread group means the reader should allow
work to continue.
Those are three different facts, not alternate spellings of one state.

An aggregate is also lossy by design: a thread can have an outstanding reader
question, an agent answering an earlier message, and a newer message queued.
Choose one group for navigation while retaining all three facts in the reading.

## Existing ontologies and consumers

These are code-observed value sets, not proposed UI categories. Paths below are
relative to the repository; the two prefixes are
`skills/leaf/scripts/leaf/` (Python) and `skills/leaf/assets/runtime/` (browser).

| Domain                 | Existing values / facts                                                                                                                                     | Owner and use                                                                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| Agent declaration      | `working`, `waiting`, `idle`; detail, timestamp, event floor, work seats                                                                                    | `status.json`; input to Python `activity.py`, not current state by itself                                                           |
| Page activity          | `working`, `handling`, `queued`, `picked_up`, `listening`, `stalled`, `away`, `unheld`, `unattended`, `closed`; held/quiet/dropped, counts, next transition | Python `activity.py:133`; browser `banner.js:341` and `live-leaves.js:78`; agent state; stop guard reads obligations/reply evidence |
| Pickup evidence        | `queued`, `opened`; event/session/turn bindings                                                                                                             | Durable pickup events; `codex.py:1163`; distinguishes carrier acceptance from turn entry                                            |
| Interaction phase      | `sent`, `waiting`, `queued`, `picked_up`, `active`; quiet/dropped qualifiers                                                                                | Python `activity.py:95`; `waiting` is aged Sent, `active` is a work claim                                                           |
| Receipt presentation   | `sent`, `waiting`, `queued`, `picked_up`, `picked_up_ended`, `working`, `was_working`                                                                       | Browser `updates.js:65`; message, margin, and compact thread receipts                                                               |
| Conversation attention | `resolved`, `awaits_reader`, `awaits_agent`                                                                                                                 | Derived server conversation policy, not primitive facts; browser `conversation/model.js` consumes it                                |
| Thread filters         | Open, On you, On agent, Resolved                                                                                                                            | Browser `conversation/narrowing.js:1`; derived from resolution and who is owed                                                      |
| Compact thread status  | Resolved, Not answered, Replying, Sending, workflow receipt, stream outcome, On you                                                                         | Browser `conversation/thread-card.js:130`; its own precedence list, with a TODO for shared workflow policy                          |
| Reply stream           | `active` draft; `completed` and provider terminal outcomes; failed/interrupted/disconnected have labels, other outcomes render Partial                      | Python `served_state/conversation.py:120`; browser `conversation/messages.js:145`; provisional text is not a committed answer       |
| Local gesture          | Unresolved send and reconciliation state, including Sending and refusal                                                                                     | Browser pending ledger; `pending/model.js:20`; precedes durable admission                                                           |
| Request seat           | `ready`, `pending`, `completed`; receipt `succeeded` or `failed`                                                                                            | Python `requests.py:15`; browser `request-elements.js:172`; failure reopens the seat                                                |
| Margin presentation    | `idle`, `engaged`, `busy`, `failed`; action/disclosure/status; neutral/positive/negative                                                                    | Browser `margin-entry-model.js:8`; generic interaction and visual treatment, not agent workflow                                     |
| Notice                 | Message, visibility, foreground/background scheduling; polite announcement                                                                                  | Browser `notifications.js:1`; temporary bottom status text, not persisted work                                                      |

### Where the same work is presented

- **Banner:** page activity and queued counts; work detail and observed host step;
  separate connectivity/presentation failures. Its Threads count is unresolved
  conversations, not unread messages (`conversation/thread-list.js:325,400`).
- **Messages:** receipt labels in `conversation/acknowledgments.js:13`;
  local Sending, host failure **Not answered**, and stream outcomes in
  `conversation/messages.js:122`. The separately dispatched layout refinement
  moves these marks; this investigation concerns their meaning.
- **Thread rows and filters:** attention booleans plus their own combined-status
  precedence. This is the clearest remaining place to consolidate policy.
- **Margin and Page Map entries:** `margin-entries.js:200` reuses the workflow
  stage mapper but emphasizes working/picked-up; generic entry state governs
  interaction, severity, and geometry separately.
- **Leaves tray:** `live-leaves.js:78` reads each page's canonical activity.
- **Request widgets:** shared request elements plus package copy in
  `packages/command-hub/widgets/lf-operations.js` and
  `packages/monitoring/widgets/lf-release-actions.js`. Their external-outcome receipts
  must not be renamed as message delivery receipts.
- **Agent state and stop guard:** consume the same activity obligations as the
  browser. Stop also reads reply evidence, cursor, watcher state and raw idle
  declaration; changing obligation semantics affects whether a turn may finish,
  while changing a display label alone need not.
- **Arrival notices and assistive announcements:**
  `state-application.js:40,158` detects increases in total agent message count
  while the panel is closed. `notifications.js` schedules temporary news without
  changing focus. This is not per-message read tracking.

### Producers, storage, and the projection path

| Producer                                               | Stored evidence                                                                                          | Projection / consumer                                                           |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Status CLI (`cli.py:682`, `service.py:366`)            | `status.json`: declaration, event floor, `work[]` seats                                                  | `work.py:21` and `acknowledgments.py:35` bind effective work to subjects/input  |
| Delivery claim (`session.py:83`)                       | `status.json.handling`: exact event, target, generated claim id                                          | Strengthens only the still-outstanding delivered move                           |
| Carrier pickup (`session.py:369`)                      | Append-only `pickup`: event ids, queued/opened, session/turn                                             | Idempotence on event/phase/session/turn; feeds acknowledgments                  |
| Session/service (`service.py:48,202`)                  | Machine-global page claim, opaque Leaf turn, closure, pid/job/activity lifetime; separate service record | `presence.py:176` joins ownership, waiter lease, cursor, and liveness           |
| Codex observer (`codex_adapter.py:240,343`)            | `status.json.stream.activity`, provisional reply and response bindings                                   | Provider session/turn plus event floor; current step is presently detail text   |
| Claude hooks (`hooks.py:40,168`)                       | Turn open/close and release; acknowledged moves become opened pickup                                     | Stop guard consumes canonical obligations and watcher state                     |
| Embedded website host (`worker/server.py:339,463,557`) | Same delivery/claim/stream primitives; terminal unanswered outcomes                                      | Finds work through canonical obligations; commits or records unanswered results |
| Admitted response / revision / request outcome         | Existing event log and document publication                                                              | Settles exact interactions before activity is aggregated                        |

The full-state assembly in `served_state/page.py:22` joins presence from
`presence_with_activity()` and interaction evidence from
`canonical_acknowledgments()` through `canonical_activity()`. Agent-facing
state (`agent_state.py:342,382,534`), neighbor rows, browser state, and stop
guards read this same result. Settled interactions leave the outstanding
reading; there is no durable “done interaction” state to add beside settlement.

Keep these identities distinct:

- Host session, Leaf claim turn, and provider turn.
- Immutable delivery, source reader event, work claim, and interaction id.
- Semantic subject and full widget/unit/facet action coordinate.
- Page owner, posting session, and display name.
- Service lifetime, claim lifetime, and carrier/watcher lifetime.

A delivery may span pages, subjects, and events. Preserve the explicit binding
between delivery and host turn rather than using either identity for both. A
work claim may be proactive with no source reader event, so it cannot always
be represented as a stage of delivery.

### Adjacent transport and failure owners

Event POST retry/refusal feedback belongs to browser `delivery.js:21`.
State reachability (`waiting`, `ready`, `offline`) and read retry belong to
`state-feed.js:1,127`. Layer/server replacement and runtime error reporting
belong to `layer-client.js:75,249`. Pre-module startup has its own persistent
recovery surface in `bootstrap.js:111`. These failures can prevent activity from
being observed, but are not evidence that the agent or an external job failed.

### Reader unread is not implemented by these counters

The agent-reply arrival counter is module-local and resets on document load.
The Threads count is open conversations. `pending/model.js` names unmatched
local attempts `unreadMessages` and `unreadEvents`; those mean not yet reconciled
with server receipts, not unseen by the reader. The comment in
`notifications.js:79` about durable unread state overstates the thread behavior.
Do not use any of these as the foundation of a durable unread ontology.

### Vocabulary collisions to retire

| Existing term                                         | Canonical meaning to retain                                                      |
| ----------------------------------------------------- | -------------------------------------------------------------------------------- |
| `waiting` declaration                                 | Agent handoff / invitation; does not prove a concrete reader obligation          |
| `waiting` interaction                                 | Awaiting pickup beyond the grace period                                          |
| Proposed Waiting group                                | Reader has no immediate action while established work continues                  |
| `active` interaction / Working label                  | Work evidence on the exact subject/input                                         |
| `handling` page kind / Picked up label                | Exact input entered the current turn                                             |
| `quiet`, `stalled`, Was working                       | Observation freshness and its consequence, retaining the reason                  |
| `dropped`, Picked up · turn ended                     | Turn ended or changed without settling input                                     |
| `pending`                                             | Qualify by owner: local send, request seat, or outstanding delivery              |
| `failed`                                              | Qualify the failed operation: send, reply stream, external request, or rendering |
| `unreadMessages`, `unreadEvents` in the pending model | Unreconciled local attempts                                                      |
| receipt                                               | Qualify as delivery evidence or external request outcome                         |
| status                                                | Qualify as declaration, activity reading, or visual presentation                 |

This is a bounded inventory of the production state owners and consuming surface
families, not a count of every string occurrence or every widget instance. The
domains above retain their native identities and map to shared attention plus
adjacent browser/request domains;
none needs one global enum. Job and delegation tracking below remain proposed
extensions, not discoveries in the existing schema.

The older [responsiveness plan](reader-feedback-responsiveness.md) is target
guidance, not evidence of the shipped ontology. Its Active label and pointer
read-before-claim ordering have drifted from the current Working label and
claim-before-read workflow. Reconcile it with the owning contract during the
first cutover rather than copying its lifecycle table into new code.

## Proposed register: preserve native identities

Use the existing records before inventing an Attempt abstraction. The first
cutover should introduce no new identity or storage type. Reduce competing
classifiers and ambiguous names, rather than reducing distinct evidence to one
linear state machine.

| Existing thing                | Identity                                                                                                              | What it must not be confused with                             |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Subject                       | Thread or widget target, with widget/unit/facet coordinate where applicable; contained by a page                      | Delivery, which can span subjects and pages                   |
| Input and response obligation | Source event and exact response address; current agent obligation means an unsettled interaction requiring a response | Reader Ask seat, which has its own awaiting/settlement rules  |
| Delivery                      | Immutable delivery id and its page/event batches                                                                      | Host execution; retain its explicit delivery binding          |
| Execution                     | Host session and provider turn where supplied, joined to Leaf claim turn explicitly                                   | Delivery; a retry does not by itself create a new obligation  |
| Work claim                    | Existing generated claim id and bound subject, with source event when present                                         | Pickup; proactive claims need no preceding reader input       |
| Reply                         | Delivery-bound response address plus provisional or committed message identity                                        | Turn completion; finishing a turn need not answer every input |

Keep **observation** as evidence fields: producer, time, lifetime and identity of
what was observed. Keep **attention** as a derived reading for a subject and
actor. Neither needs a new independently mutable entity. Reader Asks and agent
response obligations may feed one attention reading without pretending they
already have the same identity or settlement contract.

### Combine the presentation; preserve independent facts

An interaction can present Sent, aged Waiting, Queued, Picked up, or Working according to its
strongest evidence. That is a presentation precedence, not a stored attempt
lifecycle. A work claim does not require pickup, pickup can survive a turn
ending, and a delivery can span several subjects. Keep those records and
joins explicit.

Delivery progress uses the stages its carrier actually observes; local sending
and refusal remain in the browser ledger before admission. Execution outcomes
remain attached to their host turn. Durable responses settle exact input. This
avoids both a cross-product enum and independent booleans for every sequential
transport stage.

For richer activity, inspect the host's typed notification at ingestion before
it becomes detail text. Candidate kinds are generic working, thinking, replying,
and tool execution, but settle their exact values against real host signals.
Do not infer thinking from quiet time or tests from a sentence. A job or worker
that outlives its launching tool needs its own observed identity and continuation;
that is a later extension, not a rename of today's working status.

Keep observation freshness as a qualifier, with its reason and next check time.
Avoid thinking-stale and job-stale variants. An ended turn is stronger evidence
than a late heartbeat; neither establishes job failure.

### Store evidence, derive presentation

The append-only log owns durable facts: admitted input, delivery/pickup,
explicit settlement, and request outcomes. Status and host lifetime records
own renewable declarations and current observations. Browser sending, drafts,
scroll position, and disclosure keep their existing mechanical owners.

First derive one shared thread attention/presentation reading from existing
conversation and workflow facts. Thread groups and compact status select from
it; banner and margin use the same ownership reasons where they refer to those
threads. Extend to other subjects only where a consuming surface needs it.
Local unsent gestures overlay their own immediate delivery state until the
server accepts them. Formatting and notification scheduling remain browser work.

Do not persist the derived navigation group. Do not infer a reader obligation
from `status waiting`, unread content, an unresolved thread, or a quiet model.
An unresolved discussion with nothing owed remains explicit history awaiting a
completion decision; it is not automatically resolved or assigned to the reader.

## Merge docket

These eight confusable pairs drive the proposal; each has an explicit verdict.

| Pair                                                            | Verdict           | Consequence                                                           |
| --------------------------------------------------------------- | ----------------- | --------------------------------------------------------------------- |
| Delivery receipt / request receipt                              | Disjoint          | Delivery proves routing; a request receipt proves an external outcome |
| Work declaration / observed host activity                       | Orthogonal facets | Preserve intent and observation together, with attribution            |
| Queued / picked up                                              | Phases            | Delivery progress for exact inputs, not independent status dimensions |
| Working / thinking                                              | Genus–species     | Thinking is a proved subtype; working is the honest generic reading   |
| Thread unresolved / obligation outstanding                      | Orthogonal facets | Explicit closure and answer ownership remain separate                 |
| Unread / needs reader action                                    | Orthogonal facets | Information arrival cannot manufacture work                           |
| Observation lost / execution failed                             | Disjoint          | Retain uncertainty instead of inventing a terminal outcome            |
| Waiting declaration / waiting for pickup / reader Waiting group | Disjoint          | Rename internal meanings; aggregate only in the presentation policy   |

## Scenarios that constrain the cutover

| Situation                                                | Required reading                                                                                                                            |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| New input while an older answer is underway              | Older work retains its input binding; newer input independently remains sent/waiting or becomes queued                                      |
| Agent asks a question, then posts another update         | Proposed: retain a still-outstanding Ask across unrelated updates; reconcile current last-turn, widget-state, and reaction settlement rules |
| Agent commits a reply explicitly bound by responds       | That exact input settles; unrelated or newer input remains outstanding                                                                      |
| Turn ends with unanswered input                          | Preserve pickup history and expose the ended turn; do not report current work                                                               |
| Host becomes quiet during an unobserved tool             | Observation is uncertain; no invented failure or healthy job claim                                                                          |
| Observed job runs after the model stops                  | Show job state and continuation separately; supported only after job integration                                                            |
| Job succeeds while agent must interpret its result       | Job completes; the obligation remains open                                                                                                  |
| Reply arrives while the reader is elsewhere              | Announce arrival without moving focus; any new read-position record needs an explicit lifetime                                              |
| Page has no live agent and no outstanding work           | Availability information, not a manufactured recovery obligation                                                                            |
| Thread contains a reader question and ongoing agent work | A concrete reader obligation places it in On you; retain concurrent work as secondary evidence                                              |

## Implementation sequence

First, settle a single mapping of the existing readings and their ownership.
Add scenario fixtures at the canonical projection boundary and carry the same
cases through banner, thread, and margin rendering. Preserve current delivery
and exact-settlement guarantees during this cutover.

Next, carry typed host activity through the existing observation route, retaining
its source and binding. Render a generic fallback when a host supplies less
evidence. This enables thinking versus tool work without inventing job tracking.

Then introduce independently observed jobs and delegated work, with an explicit
resumption owner and mechanism. This is a separate lifecycle contract, not a new
label applied to existing prose. Success, failure, and lost observation all need
a continuation path.

Finally, derive reader notifications from meaningful transitions: new answer,
new reader obligation, or progress needing inspection. Keep explicit gesture
feedback immediate and avoid announcing every heartbeat or tool step. Unread tracking would be a
separate product decision; it is not an existing input to this first slice.

## Open boundaries to settle with implementation

- Whether an explicit execution-attempt identity adds anything beyond native
  delivery and turn identities. Start without it; prove a missing join before
  adding one.
- Which host signals prove thinking versus tool execution, and which retain a
  useful activity identity. Current host text alone cannot carry this contract.
- When uncertain progress should ask the reader to intervene versus stay
  inspectable. Tie recovery to an available action and responsible actor.
- Whether to add read-position tracking at all, what reader action establishes
  it, and how long it lives. Panel-open or a displayed notice alone does not
  prove consumption. This is a separate reading-continuity decision.

This pass maps code and contracts. It does not claim runtime reproductions or
latency measurements, and does not implement the proposed schema.
