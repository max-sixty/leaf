# Responsive reader feedback

Status: target contract. The lifecycle exists in parts, but the complete ordering and
latency objectives are not yet implemented or measured. Move each stable rule into its
owning runtime, protocol reference, skill, or test as it lands, then delete this note.

## Goal

Reader input should produce useful visible feedback before Leaf or its agent begins the
work that input caused. The reader should never have to infer from silence whether a
gesture was recorded, reached the agent, or is being acted on.

Responsiveness is first an ordering guarantee and then a latency goal:

1. Paint the result of the reader's gesture.
2. Show the strongest delivery or ownership fact Leaf can prove.
3. Begin the substantive work.
4. Keep the visible state current until a durable result settles the input.

Implementation reasoning, source reads, edits, tests, and delegation must not delay the
first UI update. For a queued pointer, reading the immutable delivery is address
resolution rather than substantive work; the work claim is the next operation.

## Terms

- **Local result** is the optimistic comment, choice, request, or other semantic result
  painted from the browser's unresolved gesture ledger.
- **Delivery receipt** is Leaf's durable evidence that input was sent, queued, or opened
  in an agent turn.
- **Work claim** is the agent's current declaration of what it is doing, optionally
  attached to one thread or widget.
- **Substantive work** is any read, edit, test, delegated task, or external operation
  performed to answer the input. Transport reads needed to learn the page and subject
  are not substantive work.
- **Settlement** is the durable reply, revision, request receipt, resolution, or declared
  action that answers the exact reader input.

## Lifecycle

Each stage strengthens the previous reading. Later work may not make an earlier stage
disappear unless stronger evidence replaces it.

| Stage | Writer and evidence | Reader-visible result | Ordering requirement |
| --- | --- | --- | --- |
| Gesture | Browser pending ledger | The semantic result appears immediately | Same rendering turn as the gesture, before the POST completes |
| Admission | Leaf event door | The accepted subject says **Sent**; refusal restores authoritative state and explains the failure | Before any delivery attempt |
| Queue acceptance | Carrier `pickup` event | The subject says **Queued**; the banner includes the queued count | On acceptance, independent of whether the task is loaded |
| Turn entry | Direct delivery or App Server observer records `opened` | The subject says **Picked up** and page activity says the agent is handling it | As part of opening the turn, without waiting for model output |
| Work selection | Agent work claim | The selected subject says **Active**; the banner says what the agent is doing and retains any queued count | The agent's first operation for an actionable delivery, after address resolution and before substantive work |
| Progress | Agent status or observed host activity | The banner replaces the work detail when the operation materially changes; queued and active receipts remain visible | Publish the new phase before starting it |
| Result | Append-only event, revision, or terminal request receipt | The page or thread shows the durable outcome; the triggering obligation leaves the outstanding count | Before claiming completion or asking the reader for another move |
| Handoff | Agent waiting declaration | The banner names the concrete answer wanted from the reader, or invites comments when there is no specific ask | Only after every obligation taken by the turn is settled |

The transport owns **Queued** and **Picked up** because it can prove them without model
judgment. The agent owns **Active** and the work detail because selecting the work and
describing it require context. A provisional chat message is not needed merely to show
activity; the receipt and banner provide that feedback without adding noise to the
durable conversation.

## Agent ordering contract

For a new actionable delivery:

- A structured delivery already contains its page and subject, so the first
  model-initiated operation writes the work claim.
- A queued pointer first reads its immutable delivery. The next operation writes the
  work claim.
- The claim names the first concrete operation and uses the thread or widget
  subject when one exists. “Processing feedback” is not useful detail.
- Source inspection, planning, edits, tests, external calls, and delegation begin only
  after Leaf accepts the claim. The agent need not wait for a browser acknowledgement;
  the accepted write is the causal boundary the state feed paints.
- When several inputs are outstanding, the current subject becomes **Active** and the
  others retain their actual receipts. The banner combines both facts, for example:
  `Codex is working — Revising the heading (just now). 2 more updates are queued.`
- When the agent switches subjects or work phases, it updates the UI before beginning
  the new work.

A retry whose obligations are already settled must not flash a new work claim. Input
that arrives during unrelated work remains **Queued** automatically; it does not replace
the current claim until the agent starts it. If Leaf cannot record a claim, the agent may
diagnose and restore that feedback path, but it does not silently continue with the page
mutation.

## Latency objectives

These are initial user-perceived budgets, not claims about current production behavior.
They should be revised from phase traces rather than relaxed to make a test pass.

| Transition | Objective |
| --- | --- |
| Gesture → local semantic result | Same rendering turn; target under 100 ms |
| Server or queue acceptance → visible receipt | Next state application; target under 1 s |
| Turn entry → visible **Picked up** | Without waiting for model output; target under 1 s |
| Delivery in model context → accepted work claim | Before the first substantive operation; target under 2 s |
| Status or durable result write → browser paint | Next state application; target under 1 s |

Time to complete the requested work has no universal budget. The contract is that the
reader sees which phase the work is in while that time passes. A long operation renews
or changes its detail when the phase changes; it does not emit timer-driven chatter.

## Failure behavior

- An offline browser retains the local result and says that it is waiting to send.
- A refused event restores authoritative state and leaves a useful error at the surface
  where the reader acted.
- Queue acceptance never implies turn entry. A queued receipt remains queued until a
  carrier observes the exact turn or the agent makes a local work claim.
- Turn entry never implies settlement. Only a durable Leaf operation answers an
  obligation.
- A stale or ended work claim loses its active treatment. New queued input must not
  revive it.
- New queued input does not hide fresh work. The banner states current work and the
  additional queued count together.

## Evidence and tests

The contract should be proved at its owners rather than by one fragile full-stack test.

1. Projection tests arrange sent, queued, opened, active, stale, and settled evidence and
   assert the canonical activity reading, including work plus a newer queue.
2. Browser tests perform the reader gesture for local feedback and inject later durable
   transitions through the real server, asserting the rendered receipt and banner after
   each causal edge.
3. Agent evals inspect the tool trace for a direct delivery, a queued pointer, a
   mid-turn delivery, and an already-settled retry. The work claim must precede the first
   substantive operation in the first three and remain absent in the retry.
4. The existing website verifier remains the vertical smoke test. Its phase trace should
   record event admission, queue acceptance, turn entry, work claim, first substantive
   operation, settlement, and browser application so production latency can be measured
   without making wall-clock thresholds the sole regression gate.

Deterministic tests assert sequence and state. Repeated production traces evaluate the
latency objectives. A timeout or sleep cannot prove that the required transition was
reached.

## Implementation consequences

- The fast path for a work claim should be a typed, low-overhead host operation; making
  the UI-first action expensive creates pressure to skip it.
- The claim door should atomically confirm that its subject still has outstanding work
  before painting **Active**. A settled retry therefore becomes a refused or no-op claim,
  not a transient false status.
- The carrier should publish every fact it knows before invoking the model. Initial
  feedback must not depend entirely on prompt compliance.
- The canonical activity projection must preserve orthogonal facts: what is being worked,
  which subject owns that work, and how many other updates remain queued.
- Host activity details may refine an existing claim, but waiting for a plan, reasoning
  summary, or tool call is too late for the initial feedback.
- Delivery, activity, provisional response text, and settlement remain separate
  readings. Combining them to reduce latency would make the UI faster by making it
  untrue.
