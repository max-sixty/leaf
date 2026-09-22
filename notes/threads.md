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

## Package-visible Threads

Packages should be able to build page-content views of Threads without reading the raw
event log or reproducing Leaf's conversation fold. A package might present a work queue,
group Threads around its own domain records, or devote a pane to discussion. The built-in
Thread panel is one projection of the same semantic collection, not the owner of that
collection.

This is a model boundary, not a request to turn the panel DOM into a reusable component:

```text
events + pending gestures + activity
                 |
                 v
        Thread collection
          |          |
          v          v
  built-in panel   package selector
          |          |
          +----+-----+
               v
      canonical Thread renderer
```

The public surface returns complete immutable snapshots from the application publisher,
not an incremental event stream. A consumer must not fold accepted events, unresolved
reader gestures, refusals, receipts, Ask state, or host activity for itself. Before the
first admitted reading, `waiting` and `offline` are distinct from a known-empty Thread
collection. A later read failure retains the last admitted `ready` collection; current
connection health remains a separate canonical reading rather than erasing known Threads.

### Proposed package boundary

Expose one lifetime-bound Thread collection through the widget API. The built-in panel
must obtain its content through this same interface; it is the first consumer and the
conformance test for whether the interface is complete. Do not publish a reduced package
summary beside a richer private panel model. A field the panel needs belongs either in
the canonical record or in a shared derivation over that record.

The exact entry-point name can follow the widget-controller consolidation, but its shape
must support both app-owned and package-owned consumers without changing the reading. A
provisional `watchThreads(owner, callback)` would run immediately and after each semantic
publication with a clone-safe reading. Rendering from it must join the widget's
presentation proof: a state application cannot report the document presented while a
Thread consumer is still painting. Implement this through one controller-owned lifetime
or a dedicated watcher that claims and settles its own application-presentation region,
not an untracked publisher callback. Reconcile the existing watcher/controller split
rather than introducing a third lifetime convention.

The reading contains:

- the `waiting`, `ready`, or `offline` phase;
- every conversational Thread, excluding bare reactions, with its ordered turns;
- a stable key that survives admission of a pending root, plus its admitted id when one
  exists;
- its target coordinate and explicit resolution and settlement state;
- canonical attention and workflow facts, once the workflow projection above owns them;
- each turn's stable identity, author, timestamp, a JSON-shaped semantic body,
  delivery state, and reaction summary;
- collection presentation facts shared by indexes, such as topic and latest meaningful
  activity, derived once rather than independently by each consumer.

The record is a clone-safe, JSON-shaped semantic value, not the current server or
renderer object. A turn body is a discriminated record: prose carries its source and
plain text; an authored body also carries a stable document identity and registry-typed
semantic unit descriptors. For example, the shape may resemble:

```json
{
  "key": "thread-attempt-or-id",
  "turns": [
    {
      "key": "message-attempt-or-id",
      "body": {
        "kind": "authored",
        "text": "Choose a direction",
        "document": { "thread": "...", "message": "..." },
        "units": [
          { "id": "direction", "tag": "lf-options", "state": { "value": null } }
        ]
      }
    }
  ]
}
```

The example fixes the boundary, not the final property names. Packages can inspect,
search, group, and project the content as ordinary data. Do not expose DOM nodes,
transport promises, mutable runtime objects, prepared HTML, or frozen authored message
nodes. The registry owns each unit's semantic descriptor; Leaf alone turns the original
validated authored document into live widgets. This avoids making the markup and widget
lifecycle a second public renderer contract.

The panel uses these records both for its index and for its expanded cards. Shared
derivations turn a record into the immutable descriptor consumed by `ThreadView`; there
is no richer private conversation record available only to the panel. Leaf can still
keep renderer-only state such as prepared authored nodes and draft ownership private,
keyed by the public record's stable identities.

The collection also supplies capabilities bound to stable Thread identities. One reveals
a Thread at its canonical destination. One asks Leaf to render a complete Thread into a
consumer-provided outlet. Leaf resolves each key against the newest collection and owns
message rendering, replies, resolution, reactions, undo, optimistic state, refusal,
focus, and keyboard behavior. Packages never construct Thread events or receive those
commands directly. The renderer retains an explicit surface policy: in the first cut,
Leaf retains one live instance of a typed authored message island and hosts it in the
panel, while a package surface shows its ordinary Thread content and the existing route
to open that interactive content in Threads. The panel is the initial host, not the
semantic owner. A later surface may ask Leaf to move that one instance into its outlet;
it must never instantiate a second tree with the same widget identities and action seats.

Read-only access needs no registry declaration: package modules already share the page's
trust boundary and can read history. Keep `x-thread-surface` as the declaration for a
package that asks core to place complete Thread UI.

### Complete Threads inside widgets

Make `lf-diff` the first package consumer. It already demonstrates the intended split:
the package knows how a Thread target maps to a file or line and supplies the outlet;
Leaf renders retained messages, the composer, replies, reactions, settlement controls,
and receipts. Today `registerThreadSurface` privately iterates the internal conversation
model, prefilters it, and passes its adapter an internal `thread` object. Replace that
special path with the same collection record the panel consumes.

For each publication, `lf-diff` should:

1. read the canonical Thread collection;
2. select records whose exact target belongs to that diff widget;
3. map each target to its file or line outlet; and
4. return those placements to Leaf's canonical renderer.

Collection publication is not the only reason to reconcile placement. Expanding,
collapsing, or filtering a diff changes its available outlets without changing Thread
semantics, and a newly opened composer needs an outlet before a Thread record exists.
The consumer lifetime therefore retains a mechanical placement invalidation and a
separate composition-placement input. Neither creates a semantic collection record or
application epoch.

Leaf validates that the target resolves exactly inside the registering widget and that
the returned outlet is inside it before accepting the placement. Selection by a trusted
package does not replace core ownership validation. The existing surface handle's
`open()` operation remains the way `lf-diff` begins a Thread on its own datum, but it and
outlet placement should be capabilities of the same Thread-consumer lifetime rather than
a separate private feed.

The package should own collection layout, grouping, filtering, and which selected Thread
gets an outlet. Leaf should continue to own the Thread card, drafts, message widgets,
commands, focus, and event transport. The Thread panel remains the complete global
index. A widget-hosted complete Thread may replace its margin presentation while that
outlet is available, as existing local surfaces do; it does not remove the Thread from
the panel.

Keep the first surface boundary as sharp as today's `registerThreadSurface`: a package
can place only exact datum Threads anchored inside its own widget. `lf-diff` therefore
needs no general selector language or cross-widget priority. A future page-wide
collection introduces collisions between widgets and requires an explicit Leaf-owned
choice of which visible outlet, if any, claims a Thread; design that arbitration only
when such a consumer exists.

### Relationship to live specimens

A live playground specimen and a package-visible Thread reading share the production
conversation model but solve different boundaries. The package API lets another view in
the same page consume current Thread truth. A live specimen hosts a complete, isolated
page instance and event log so production UI can be exercised without copying rendered
DOM. It also needs an explicit focus-entry and focus-return contract; the existing
contained gallery remains an inert replay. Neither boundary should simulate Leaf's event
lifecycle.

Implement the collection by cutting over both existing consumers: the built-in panel and
`lf-diff`. This tests the global-index and widget-local-placement cases without inventing
a new package or page-wide arbitration. `lf-visual-review`, the other existing
`registerThreadSurface` consumer, must move to the same registration in the cutover so no
parallel private feed remains. The diff is also a useful live-specimen case later,
because it exercises a production package consuming production Thread state.

### Decisions before implementation

Two directions are settled for the first cut. Thread content is a JSON-shaped semantic
record, including registry-typed descriptors for authored units but no live nodes or
HTML. Topic and workflow status are shared derivations over those records rather than
parallel fields stored for the panel; counts are derived from turns.

1. **Authored island hosting.** Decide whether package surfaces need Leaf to move the one
   live authored widget tree out of the panel in the first implementation. The
   recommendation is no: keep the panel as its initial host and use the existing route
   from an inline surface. Moving the instance entails focus, retained-node, and
   presentation-proof contracts that the shared JSON data model alone does not settle.
2. **API consolidation.** Decide whether to replace `registerThreadSurface` and the
   watcher family with one Thread-consumer controller immediately, or first make the
   existing surface registration consume the public collection internally. The
   recommendation is one controller if the widget-controller work lands first;
   otherwise cut over the data model now and consolidate lifetimes separately.

Workflow-oriented fields can wait for the richer obligation/activity model above rather
than exposing the panel's temporary compact-status policy. Page-wide complete Thread
surfaces also remain deferred: they must choose a deterministic Leaf-owned winner when
two connected widgets request the same Thread, and packages must not settle that
collision by registration timing.

The implementation is ready to begin with the panel and `lf-diff` as paired acceptance
cases. That cutover removes the private conversation feed behind the existing diff
surface, carries `lf-visual-review` with it, and avoids committing Leaf to a second
conversation renderer.

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
