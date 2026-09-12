# Reactive browser runtime

Status: implementation in progress; see the [joint checkpoint](reactive-page-runtime-progress.md).

## Outcome

Leaf should publish one immutable browser application state and render every semantic
surface from it. A reader gesture updates that state before network delivery begins, so
the widget, Ask, command, margin, conversation, and local delivery readings agree in the
turn that handles the gesture. An authoritative server response replaces the accepted
base and rebases unresolved gestures over it. Server-owned facts such as canonical agent
activity remain unchanged until that response supplies a new value.

The settled implementation foundation uses:

- a plain TypeScript domain model for authored state, authoritative state, unresolved
  gestures, receipts, and the effective state derived from them;
- `@preact/signals-core` to publish the one immutable application snapshot and derive
  read-only projections;
- Lit custom elements and templates to render generated widget and chrome regions;
- committed, self-contained ESM and CSS produced by a contributor build.

Authored pages remain ordinary HTML. Opening, editing, serving, and exporting a Leaf
page does not run a frontend build. A Leaf installation still needs only the plugin,
`uv`, `jq`, and a browser; Node belongs to Leaf development and to package authors who
choose compiled source.

This note owns the implementation plan while the work is open. Once the cutover lands,
move its lasting contracts into `CLAUDE.md`, `skills/leaf/assets/CLAUDE.md`, module
headers, and the package reference, then delete this note.

This plan and the [page-instance boundary](page-instance-boundary.md) are one program.
That boundary owns what an immutable revision contains, how page-owned dependencies and
declarations compose, and which export modes exist. This plan owns semantic publication,
rendering, and presentation inside the active document. A revision activates as a fresh
document execution environment; it does not ask the old runtime to install and execute
the new revision. The [Playground capability plan](playground-capability-plan.md) is the
first demanding consumer of the combined boundary, not a separate runtime architecture.

## Why change the runtime

Leaf's durable state model is sound: authored markup starts state, the append-only log
changes it, and the server returns one transaction-consistent view. The current browser
can nevertheless expose different moments of that view. A widget may paint an
optimistic action while its Ask and Undo surfaces still read accepted history. A later
async render can publish part of a newer state before another surface has adopted it.
These are consistency failures in browser projection, not conflicting durable data.

The immediate-withdrawal work established the required fold for one difficult case:
accepted history and pending forward or undo gestures produce one effective widget
state, and refusal restores accepted state plus every surviving later gesture. The
runtime should make that relationship its general application model instead of asking
each projection owner to reconstruct the relevant subset.

A framework does not supply Leaf's semantics. It can supply dependency tracking,
batched publication, lifecycle cleanup, declarative DOM updates, and component
composition. Leaf must continue to own event admission, exact undo dependencies,
receipt accounting, revision windows, authoritative rebasing, and export readiness.

## Goals

### One semantic moment

Every semantic reading comes from the same immutable application snapshot. One gesture
cannot be complete in a widget and absent from Ask eligibility, commands, receipts, or
conversation state. Browser code may retain local mechanical state such as focus,
selection, a draft, drag geometry, disclosure, and scroll position, but that state
cannot decide the accepted or pending semantic result.

### Immediate local results

When the browser has enough information to draw a gesture's result, dispatch publishes
that result before starting delivery. Awaiting confirmation may affect tone or
availability, but it does not stand in for the result. Refusal removes the rejected
gesture and derives the replacement state; it does not restore a DOM snapshot or invent
an inverse action.

### Stable authored documents

The framework owns generated regions, not the authored document. Authored children
remain real nodes through ordinary updates within one active document. Nested widgets
retain their element instances, and anchors continue to resolve against the visible
words the document owns. Rendering must preserve focused inputs, selections, drafts,
media, native disclosure, and a drag already in progress.

A revision change is different: it starts a fresh document and therefore cannot retain
custom-element instances or arbitrary module state. Automatic activation waits while
composition or dragging is active and until every local semantic attempt has settled.
The new document restores only continuity that Leaf records explicitly and can revalidate
against stable identity: recoverable drafts, reading position, and standing destinations.
This is a continuity handoff, not command retry, DOM preservation, or JavaScript-heap
preservation.

### An open widget layer

A new content-widget family still joins through one complete registry entry, one
module, and theme rules. Core runtime code does not acquire tag-name branches. Widget
modules receive read-only state and semantic commands through the public widget API;
they do not import application or transport owners.

### Text-first authoring and self-contained distribution

An agent can change page text, attributes, or widget markup and reload without a build.
Pages load no runtime dependency from a CDN. Plugin installation and first use run no
Node build. Optional packages remain independently vendored, so a page does not carry
renderers it never uses.

### Faithful standalone copies

Export waits for the same presentation contract as a live page and follows the two modes
defined by [the page-instance boundary](page-instance-boundary.md#5--export-states-its-execution-mode).
The completed static path materializes lazy content, serializes declared shadow content,
inlines CSS and media, removes scripts, and strips or disarms controls whose behavior
required JavaScript. The remaining interactive path packages the active revision's
captured local behavior, preserves local controls and navigation, removes host chrome and
networking, and disables host-dependent commands before dispatch. Both open without a
server or external request.

## Non-goals

- The server event model, append-only log, revision store, and Python projection do not
  move into a frontend framework.
- Leaf does not become a single-page application and gains no client router, frontend
  server rendering, hydration protocol, or application framework.
- The server does not gain a second renderer for package widgets.
- A renderer does not own `body > main` or reconstruct arbitrary authored markup from
  strings.
- Signals do not become independent writable stores attached to widgets.
- Synchronous dispatch does not promise that a newly introduced lazy module or remote
  payload has finished preparing. It promises that readable application state has
  changed; presentation readiness has a separate boundary.
- The cutover does not preserve old internal browser APIs or the current imperative
  behavior-module API. The authored vocabulary and package registration model remain;
  behavior modules move to the read, command, and presentation contract below, and
  obsolete paths are deleted.

## Chosen stack

### TypeScript domain model

The domain model is a set of pure functions over serializable values. Its central
operation is equivalent to:

```ts
effective = derive(authored, authoritative, unresolved)
```

`authoritative` is one admitted server view. `unresolved` is an ordered ledger of local
attempts with stable attempt identities, delivery state, dependencies, and any accepted
event identity. The derivation resolves exact undo, revision windows, restatements,
standing reports, request seats, Ask completion, and conversation projection without
reading the DOM.

The domain model receives already validated values. TypeScript describes the internal
contract; Python remains the validation boundary for external data and the authority
that derives server-owned meaning.

### Signals Core publication

One root signal holds `ApplicationSnapshot`. Only the application publisher writes it.
Commands and transport callbacks call publisher operations such as `dispatch`,
`adoptAuthoritative`, `acceptReceipt`, `rejectAttempt`, and `resetDocument`; they never
mutate derived state.

Computed signals expose narrow read-only projections for widgets, Asks, commands,
conversation, margin entries, local delivery, and server-supplied activity. A projection
may combine semantic state with a component's local mechanical state, but it cannot
write a second semantic value. Effects connect readings to rendering and host side
effects; effects do not synchronize competing stores.

Canonical agent activity remains the top-level reading Python derives from host status,
claims, turn identity, watcher leases, pickup events, and unsettled reader moves. The
browser selector exposes that field without recomputing or overriding it. Local delivery
may update immediately from the unresolved ledger, but it is not agent activity. The
agent-stop guard stays server-owned; the browser only renders the authoritative result.

Signals and Lit have separate responsibilities. Signals owns global domain state and
dependency tracking. Lit owns element lifecycle and DOM rendering. Lit reactive
properties carry a component's latest read-only input, not another application model.

### Lit rendering

Leaf-owned custom elements extend `LitElement` or use `lit-html` where a custom-element
class would add no value. A small reactive controller subscribes to a computed reading,
requests an element update, and disposes its subscription on disconnect.

Lit templates own explicitly generated children. Authored children use light DOM or
native slots and are retained as nodes. A template may pass a node through a supported
directive; it does not serialize and recreate authored markup during state updates.
Keying is not a substitute for preserving cross-parent identity.

Light DOM is the default for authored readable content. Shadow DOM is appropriate for
self-contained generated controls when encapsulation is useful. Every such root is
open and serializable, receives the shared accessible theme slice, and participates in
composed focus, anchors, print, copy, and export checks. Runtime styles that must survive
export exist as serializable `<style>` content rather than only as adopted style sheets.

### Public behavior contract

The cutover preserves registry declarations, authored markup, package selection, themes,
and the rule that one module upgrades one widget family. It replaces the behavior
module's imperative semantic-state contract. Package widgets, page-owned widgets, and
page interaction modules use the same public interface; their ownership changes where
their source and declarations live, not how they reach Leaf state.

The public widget API supplies five capabilities:

1. A read-only projection containing the widget's complete effective state,
   availability, and provenance.
2. A semantic `dispatch` command that synchronously returns the new effective reading
   and separately exposes the eventual delivery result.
3. A lifetime-bound subscription that delivers changed readings and disposes on
   disconnect.
4. A local-edit deferral mechanism for an active draft, drag, selection, or other
   explicitly declared mechanical state, followed by reconciliation against the newest
   reading.
5. A presentation ticket for asynchronous work whose visible result is required before
   the current epoch is presented.

`/runtime/widget-api.js` is the only Leaf browser import path content modules use. It
exports the minimum Lit primitives needed by a shipped widget and the Leaf
reading/controller capabilities above; it does not expose writable Signals values or
internal vendor paths. That module's exports and the corresponding rules and examples in
[package authoring](../skills/leaf/references/packages.md) jointly own the public
contract. The contributor-build manifest records how committed output was produced; it
does not define or extend this API. Further Lit helpers join only when a concrete page or
package needs them.

Lit is the default renderer, not a mandatory content-module language. A plain-JavaScript
custom element or page interaction module can consume the same read-only projection,
dispatch, subscription, local-edit, and presentation interfaces without extending
`LitElement`.

### Locked contributor build

The contributor build is settled. TypeScript and dependency bundling run in development
and when committed browser artifacts are regenerated. The build script owns source and
generated destinations, the lockfile fixes dependency versions, and CI verifies that
committed ESM and CSS match their sources. Its manifest is generated evidence about
inputs, outputs, dependencies, and byte identity, not an author-facing contract.

The committed output keeps these distribution properties:

- one self-contained internal runtime bundle supplies locked Lit and Signals code;
- optional packages remain independently vendored browser modules and consume the
  public widget API rather than embedding a second framework copy;
- generated artifacts contain no CDN URL, dynamic package resolution, `eval`, or runtime
  compiler;
- `page init` copies committed output and does not invoke Node;
- browser modules remain valid under Leaf's self-only CSP.

Package authors may ship plain JavaScript modules and use the vendored Lit interface
without a build. A package written in TypeScript or another compiled component language
owns its contributor build and ships the resulting JavaScript through the same package
contract. Page authors have the same choice: ordinary page JavaScript runs directly,
while optional compiled source must produce JavaScript before Leaf captures the revision.
Editing, activation, and export never invoke that compiler. Authored page HTML imports
only captured browser-ready modules, never source files from either contributor build.
Relocating captured dependencies for export is Leaf's delivery work and does not require
Node or a page-author frontend build.

## Application snapshot

`ApplicationSnapshot` should make the semantic state boundary explicit. Its exact
TypeScript shape belongs beside the implementation, but it contains these concepts:

| Reading | Meaning |
| --- | --- |
| document | Active revision, effective registry, captured dependency-graph and layer identities, and typed authored baselines |
| authoritative | One complete accepted `/api/state` view and calibrated server time |
| unresolved | Ordered local attempts, dependencies, receipts, and delivery status for the active document |
| effective | Pure fold of the first three readings |
| semanticEpoch | Monotonic identity of the active document and effective semantic reading |

Derived projections carry values, provenance, and availability. A component never
decides availability by checking a DOM class or by separately inspecting network
traffic. The pending ledger remains one ordered ledger; a projection does not copy it
into a widget-specific queue.

The document context is one revision-bound value. Markup, page and package modules, the
effective registry, layer generation, and captured dependencies cannot advance
independently. Candidate state and commands retain the context against which they were
prepared or admitted; another document cannot interpret or retry them under a newer
schema.

The snapshot is immutable by convention and by development assertions. Publisher
operations create the next snapshot, batch the root write with any derived invalidation,
and expose the new readable state synchronously. `semanticEpoch` advances when the
active document identity or an effective semantic reading changes. Accounting an
accepted attempt may replace snapshot inputs without advancing the epoch when the
document and effective reading are identical.

Presentation is mechanical coordination outside this semantic snapshot. Recording a
render completion therefore cannot create another semantic epoch or invalidate the work
that just completed.

## State transitions

### Reader gesture

1. The semantic command validates current availability from the effective snapshot.
2. The publisher creates an attempt with a stable local identity and declared meaning.
3. The unresolved ledger is folded over the current authoritative view.
4. One new snapshot is published. Every computed semantic reading now includes the
   attempt.
5. A delivery job begins after publication.
6. Lit updates affected generated regions in the same microtask checkpoint. The
   presentation coordinator records completion before the next visible frame.

### Authoritative response

1. State application prepares and validates a private candidate without mutating public
   runtime fields or visible DOM. The candidate retains the server `taken` ordering
   value, event coverage, document revision, layer generation, and application base it
   was prepared against.
2. At commit, state application rejects a candidate older than the currently committed
   server reading or incompatible with the active document revision, effective registry,
   captured dependencies, or layer generation. Event sequence alone is insufficient
   because newer non-event state may have the same sequence. A candidate prepared before
   a newer committed response can never replace it.
3. After freshness succeeds, it re-reads the latest unresolved ledger. A gesture made
   while the candidate was preparing is therefore not lost.
4. The publisher atomically replaces the authoritative base, accounts terminal
   receipts, and derives the next effective state.
5. Components render that state. Accepted attempts remain until their semantic result
   is present in both the authoritative reading and the required component presentation.

### Refusal

1. The publisher marks the exact attempt rejected and removes dependent attempts whose
   meaning can no longer be admitted.
2. It derives accepted history plus every surviving later gesture.
3. One snapshot publishes the corrected state and failure reading.
4. The widget and every related surface render the same correction. No DOM rollback
   path runs.

### Revision activation

Revision validation and dependency capture finish before activation. Automatic
activation waits while the current document owns an active composition or drag, then
waits until the active document's unresolved ledger is settled. It then records the
explicit continuity handoff and navigates to a fresh execution environment for the
complete candidate revision. Candidate page modules are never evaluated in the old
document, and unresolved commands are neither serialized nor retried across the document
boundary.

The new environment boots one publisher from its revision-bound document context and a
fresh authoritative reading. It restores recoverable drafts, reading position, and
standing destinations only when their stable identities still resolve. It does not
preserve prior element instances, arbitrary page-module state, or exact focus inside an
interaction that could not cross the activation boundary. Historical navigation uses the
same document lifecycle without inventing additional continuity.

## Presentation contract

The semantic snapshot and the presentation coordinator distinguish two monotonic epochs:

- `semanticEpoch` is carried by the snapshot and advances only when effective semantic
  state changes;
- `presentedEpoch` is owned by the coordinator and advances when every renderer required
  by that semantic epoch has committed its DOM and declared preparation has settled.

Each presentation ticket names the active document identity, semantic epoch, renderer
instance, and required region. A Signals subscription that receives a changed reading
synchronously registers the element's Lit `updateComplete` promise for the current
epoch. The controller obtains that epoch from the publisher; including a global epoch in
every component value would rerender unaffected components. A widget that introduces
asynchronous content registers its preparation before yielding and settles it exactly
once. An unchanged selector needs no new rendering work only when its current renderer
instance has already committed that value. Unfinished required work whose inputs remain
applicable is carried into the new barrier under a current-epoch ticket. Changed or
removed work is superseded; its old completion cannot acknowledge a new value.

The publisher starts an epoch before writing the root signal. Synchronous subscribers
register their tickets, and the coordinator seals membership after that publication
checkpoint. A newly mounted required descendant joins before sealing. A descendant that
appears from asynchronous preparation is part of its parent's already registered ticket
until it has mounted and registered its own required region.

A newer semantic epoch supersedes every incomplete older barrier. Completion from an old
epoch, prior document, disconnected renderer, or replaced renderer instance is ignored.
Disconnection retires that instance's tickets; if the region is still required, its
replacement must register before the current barrier can complete. Preparation failure
reports a page error, installs the defined fail-soft result, and settles its ticket, so
obsolete work cannot block export forever.

`data-lf-presented`, render checks, screenshots, export, and external automation wait
for `presentedEpoch >= semanticEpoch` for the active document. Application commands and
semantic consumers read the effective snapshot immediately and do not wait for that
barrier.

Local mechanical state does not advance the semantic epoch unless it changes an
application fact. A caret move, draft keystroke, hover, open `<details>`, or drag
placeholder can repaint locally. The eventual semantic drop or send goes through the
publisher.

## Implementation plan

### 1. Seal the public API and its consumers

Finish the one immutable publisher and move widget state, action availability, exact
Undo, Ask completion, request lifecycle, conversation, receipts, local delivery, banner,
margin contributions, and authoritative agent activity display to computed readings from
it. Only the active document's publisher writes accepted history, unresolved attempts,
document context, and the effective semantic root. Canonical activity derivation and the
agent-stop gate remain in Python.

Expose the resulting read, command, subscription, local-edit, and presentation
capabilities through `/runtime/widget-api.js`, and specify their package-facing use in
[package authoring](../skills/leaf/references/packages.md). Those two surfaces are the
public contract; the generated build manifest remains build evidence. Module-boundary
tests reject forbidden imports, direct writes, duplicate pending stores, and consumers
that independently combine server events with local attempts.

### 2. Establish the presentation coordinator

Implement the ticketed semantic/presented epoch contract before changing rendering
ownership. Adapt first load, authoritative adoption, widget upgrade, external data,
revision readiness, conversations, render gates, screenshots, and external automation to
the same coordinator. Verify that stale renderer instances, disconnected regions, prior
documents, and superseded epochs cannot complete the active barrier; required descendants
join before membership seals, and fail-soft work always settles its ticket.

### 3. Complete design intent and Targeting

Record design comments as presentation or interaction intent without assigning source
ownership. Finish the stable Targeting controllers for multi-role references, detached
and ambiguous targets, hit testing, keyboard targeting, and declared-reference
validation. The same gesture must remain anchored whether the resulting edit belongs to
the page, a package, or core Leaf.

### 4. Convert rendering ownership to Lit

Use the locked contributor build and convert generated regions by ownership boundary:
widget controls, Ask and request controls, conversation surfaces, margin entries, and
remaining chrome. Each Lit owner receives one read-only computed value and invokes the
sealed semantic command. Move authored children into explicit retained regions before a
template owns adjacent generated children.

Preserve transient interaction within one document through retained nodes and explicit
local controllers. When the last caller of an imperative reconciliation helper moves,
delete the helper and its implementation-coupled tests. Preserve refusal, pending exact
Undo, frozen-thread scope, draft generations, repeated anchors, and cross-parent widget
continuity through the public API.

### 5. Prove the fresh-document rule

Exercise complete revision activation with the real server and browser. Automatic
activation waits for composition and dragging to end and for every local semantic
attempt to settle, then navigates once. The new publisher starts from the new revision and
a fresh authoritative reading; only recoverable drafts, reading position, and standing
destinations are restored after stable-identity validation. Tests reject any serialization
or retry of an unresolved command across the document boundary and any execution of a
candidate page module in the old document.

### 6. Add interactive export

Keep the completed script-free static path and add offline-interactive export on the
captured revision graph. It uses the same renderers and presentation coordinator,
materializes serializable shadow roots and styles for screen and print, exposes no host
transport or command path, and performs no external request. Static and interactive
copies of the same structured page must preserve the appropriate visible state without a
second export runtime.

### 7. Dissolve the implementation contracts

Remove transition adapters, unused DOM state attributes, old subscriptions, duplicate
lifecycle stores, and obsolete read paths. Run import-boundary and unused-export checks
over the final graph. Move lasting state and publication invariants to repository
`CLAUDE.md`; browser ownership and presentation rules to
`skills/leaf/assets/CLAUDE.md` and module headers; public module usage to
`skills/leaf/references/packages.md`; build ownership to `scripts/CLAUDE.md` and the
build script; and reader-visible behavior to its authoring references. Delete this note
and its joint `TODO.md` link only after the page-instance outcome is complete too.

The separate [Playground capability plan](playground-capability-plan.md) consumes these
primitives after this program establishes them; it is not an implementation step in this
runtime cutover.

## Acceptance

The cutover is complete when all of the following hold:

1. A forward gesture and its exact Undo change the widget, Ask, commands, margin,
   receipt, conversation, and local delivery readings immediately, before a held request
   resolves. Canonical agent activity remains the server-supplied reading.
2. Multiple unresolved gestures remain ordered across accepted, refused, duplicated,
   delayed, and overlapping state responses. After they settle, a reload matches the
   final authoritative result.
3. An authoritative read prepared before a later gesture rebases over that gesture at
   commit instead of overwriting it. A read that finishes preparing after a newer server
   reading committed is discarded, including when the newer response changes non-event
   state without advancing the event sequence.
4. A rejected gesture reveals the newest surviving local action, accepted action,
   standing report, or authored value in that order.
5. Within one active document, focus, caret, text selection, draft generations, media,
   disclosure, drag state, reading position, and nested custom-element instances survive
   every applicable render. Automatic revision activation waits for active composition,
   drag, and every unresolved semantic attempt to settle. A fresh document then restores
   only recoverable drafts, reading position, and standing destinations whose stable
   identities remain valid; it serializes and retries no unresolved command.
6. Authored and projected passages resolve to the same visible words before and after
   rendering. Anonymous repeated widgets and nested preserving boundaries retain their
   identities.
7. One presentation barrier in each active document governs first load, state adoption,
   lazy widgets, screenshots, browser checks, and export. It reaches and retains
   readiness without creating another semantic epoch. Completion from a lazy renderer
   removed before a fresh document activates cannot stamp that document; a required
   descendant introduced while its parent renders joins the active barrier. An unrelated
   semantic change while required lazy content is preparing carries that work into the
   new barrier and remains unpresented until it settles. Fail-soft completion cannot
   leave the barrier pending.
8. Static exported HTML opens from `file://` with scripts disabled and no server,
   preserves visible state and styles, and exposes no control that requires removed
   JavaScript. Offline-interactive exported HTML opens with no server or external
   request, preserves local controls and navigation through the captured runtime, and
   refuses every host-dependent command before it can appear accepted.
9. A page author changes prose, markup, ordinary widget attributes, or plain JavaScript
   and sees the complete revision activate without Node or a frontend build.
10. A fresh installed plugin serves pages with `uv`, `jq`, and a browser and performs no
    install-time build or external browser request.
11. A new plain-JavaScript package or page-owned widget joins through its registry entry,
    module, and theme without editing Leaf core or running a page-author build. A page
    may replace a package declaration's complete schema while retaining the package's
    implementation module.
12. The ordinary suite, browser render gate, standalone-export coverage, strict-CSP
    checks, module-boundary checks, and worker tests pass on the final generated output.

## Measurement

Run `scripts/verify-site-local.sh` on the merge base and final candidate. Compare
document receipt, widget upgrade, authoritative presentation, request counts, and bytes
loaded by presentation. Request counts and bytes are release evidence; elapsed time is
diagnostic and should be sampled repeatedly rather than treated as a deterministic
threshold.

Record the dependency and generated-output sizes by core and optional package. Any new
work before `data-lf-presented` needs a reader-visible reason; parsing a component that
is absent from the page is not one. Confirm that a plain page and each package load no
bundle outside their declared layer.
