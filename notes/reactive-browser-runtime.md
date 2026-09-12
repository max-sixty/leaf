# Reactive browser runtime

Status: proposed

## Outcome

Leaf should publish one immutable browser application state and render every semantic
surface from it. A reader gesture updates that state before network delivery begins, so
the widget, Ask, command, margin, conversation, and local delivery readings agree in the
turn that handles the gesture. An authoritative server response replaces the accepted
base and rebases unresolved gestures over it. Server-owned facts such as canonical agent
activity remain unchanged until that response supplies a new value.

The browser implementation should use:

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
composition or dragging is active. The new document restores only continuity that Leaf
records explicitly and can revalidate against stable identity: recoverable drafts,
reading position, standing destinations, and the bounded unresolved ledger. This is a
continuity handoff, not DOM or JavaScript-heap preservation.

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
Static export materializes lazy content, serializes declared shadow content, inlines CSS
and media, removes scripts, and strips or disarms controls whose behavior required
JavaScript. Interactive export packages the active revision's captured local behavior,
preserves local controls and navigation, removes host chrome and networking, and disables
host-dependent commands before dispatch. Both open without a server or external request.

## Non-goals

- The server event model, append-only log, revision store, and Python projection do not
  move into a frontend framework.
- Leaf does not become a single-page application and gains no client router, frontend
  server rendering, hydration protocol, or application framework such as SvelteKit or
  Next.js.
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

`runtime/widget-api.js` is the only Leaf browser import path content modules use. It
exports the minimum Lit primitives needed by a shipped widget and the Leaf
reading/controller capabilities above; it does not expose writable Signals values or
internal vendor paths. The validation slice fixes that initial export list and records
it in the build manifest. Further Lit helpers join only when a concrete page or package
needs them.

Lit is the default renderer, not a mandatory content-module language. A plain-JavaScript
custom element or page interaction module can consume the same read-only projection,
dispatch, subscription, local-edit, and presentation interfaces without extending
`LitElement`.

### Contributor build

TypeScript and dependency bundling run in development and when committed browser
artifacts are regenerated. The authoritative source and generated destinations are
declared by one build script. Resolved dependency versions are locked, and CI verifies
that committed ESM and CSS match their sources.

The output keeps the current distribution properties:

- core and each optional package have separate entry points;
- shared Lit and Signals code is vendored under the runtime and addressed by stable
  relative imports;
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
| unresolved | Ordered local attempts, dependencies, receipts, and delivery status |
| effective | Pure fold of the first three readings |
| semanticEpoch | Monotonic identity of the active document and effective semantic reading |

Derived projections carry values, provenance, and availability. A component never
decides availability by checking a DOM class or by separately inspecting network
traffic. The pending ledger remains one ordered ledger; a projection does not copy it
into a widget-specific queue.

The document context is one revision-bound value. Markup, page and package modules, the
effective registry, layer generation, and captured dependencies cannot advance
independently. Candidate state and commands retain the context against which they were
prepared or admitted; another document cannot interpret them under a newer schema.

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
records the explicit continuity handoff and navigates to a fresh execution environment
for the complete candidate revision. Candidate page modules are never evaluated in the
old document.

The continuity handoff carries the one unresolved ledger's bounded records: each original
command payload and document context, ordering and dependencies, stable attempt identity,
delivery state, and known receipt. The new environment boots one publisher from the
revision-bound document context and first reconciles those records with authoritative
events and receipts under their original context. Only then does it test a still-
unaccepted command against the new revision and retry or surface refusal. A removed
target never causes Leaf to forget an attempt that may already have been accepted.

The new environment restores recoverable drafts, reading position, and standing
destinations only when their stable identities still resolve. It does not preserve prior
element instances, arbitrary page-module state, or exact focus inside an interaction
that could not cross the activation boundary. Historical navigation uses the same
document lifecycle without inventing additional continuity.

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

## Alternatives

### Svelte 5

Svelte provides the strongest integrated contributor experience: compiler diagnostics,
templates, scoped styles, transitions, and a widely recognized component model. It is
the fallback if the Lit validation slice needs substantial adapter code.

It is not the first choice because Leaf's composition boundary is independently
authored custom elements rather than one component tree. Svelte custom elements wrap an
inner component, publish DOM on a later tick, cannot share ordinary Svelte context
across separate custom elements, and cannot use native slots when configured without a
shadow root. Leaf would still need the external domain store and explicit custom-element
bridge, reducing the advantage of the integrated component language.

SvelteKit is not a contender. Leaf needs neither its routing nor its server application
model.

### Preact with Signals and HTM

Preact is the conservative no-build alternative. Its signals integrate directly, and
HTM avoids JSX compilation. It fits Leaf-owned application chrome well. A virtual
component tree is less natural for arbitrary authored children, independently upgraded
custom elements, and nodes that move between owners while retaining identity.

### HTMX

HTMX makes a server's HTML response the update mechanism. That is useful for navigation
and server-confirmed forms. Leaf's primary gestures change several semantic surfaces
before a response exists and must later rebase over a newer authoritative view. HTMX
does not remove that model. Adding HTML swaps beside it would create a second rendering
authority and make focus, selection, nested widget identity, and anchor continuity
harder to guarantee.

### Solid, Vue, and React

Solid's fine-grained reactivity is technically strong, but JSX compilation and
component-root ownership offer less direct custom-element composition than Lit. Vue has
a capable custom-element mode but no stronger fit at Leaf's document boundary. React
has the broadest ecosystem but would require the most deliberate isolation from its
root-owned rendering assumptions. None supplies Leaf's receipt, rebase, revision, or
exact-undo semantics.

The framework comparison was reviewed against the following primary documentation on
2026-09-11:

- [Lit components](https://lit.dev/docs/components/overview/),
  [reactive controllers](https://lit.dev/docs/composition/controllers/), and
  [lifecycle](https://lit.dev/docs/components/lifecycle/)
- [Signals Core](https://github.com/preactjs/signals/tree/main/packages/core)
- [Svelte custom elements](https://svelte.dev/docs/svelte/custom-elements)
- [Preact no-build workflows](https://preactjs.com/guide/v10/no-build-workflows/)
- [HTMX requests and swaps](https://htmx.org/docs/) and
  [preserved elements](https://htmx.org/attributes/hx-preserve/)

## Implementation plan

### 1. Prove the joint boundary

First complete revision capture and fresh-document activation from #1 of the
[page-instance boundary](page-instance-boundary.md). Then build one unshipped structured
Playground page with Lit, Signals Core, the real server transport, one page-owned module,
and one page-owned declaration that reuses a package implementation. This slice
establishes the final public behavior API and the minimum end-to-end page-declaration
path rather than adapting either later. It contains:

- an authored board whose cards move between parents;
- a nested editable draft with retained focus and selection;
- an options Ask;
- generated Ask, Undo, margin, receipt, local-delivery, server-activity, and conversation
  surfaces;
- one lazy content renderer and one declared shadow root.

Hold one response, make a later gesture, publish a newer server view, undo the first
gesture, refuse an attempt, and move a card while its editor is active. The slice passes
only if every semantic surface agrees before each visible frame, element instances and
text anchors survive moves within the active document, a complete revision restart
restores only the declared continuity, and reloading reaches the same final state.

Export the settled page statically and open it with scripting disabled. Block all
external requests and run under the real CSP. Change authored prose, widget attributes,
and ordinary page JavaScript and activate them without running a frontend build. Step 6
reuses this fixture to prove offline-interactive export. If the slice requires state
synchronization effects, DOM reconstruction within one revision, or a growing framework
adapter, implement the same slice in Svelte 5 and compare the code and behavior before
proceeding.

### 2. Establish the build and public framework seam

The validation slice must finish with a build manifest naming the authoritative source
roots, committed output roots, lockfile owner, exact build and stale-output-check
commands, public `runtime/widget-api.js` import path, and every externalized shared
module. It also distinguishes layer-owned output from browser-ready page modules captured
with a revision. That manifest is the authority for the full cutover rather than a
checklist each later package or page interprets again.

Add the pinned dependencies, deterministic build, generated destinations, and CI check
described by that manifest. Expose only the Lit and state-reading capabilities content
modules need through `runtime/widget-api.js`; internal package names do not become a
second public API.

The build must preserve optional-package splitting, self-only CSP, plugin installation
without Node, and source maps useful from the vendored page directory. Optional package
builds externalize the exact shared Lit and Signals artifacts named by the manifest;
tests reject an embedded second copy. Measure generated request counts and bytes before
choosing chunk boundaries.

### 3. Introduce the one application publisher

Define the snapshot and publisher operations. Move the current pure projection,
pending, Ask, request, and conversation folds behind computed readings without changing
their server inputs. Make the application's state adoption path build a private
candidate and publish once.

At the end of this step, only the active document's publisher writes accepted history,
unresolved attempts, document context, and the effective semantic root. Module-boundary
tests reject direct writes and forbidden imports. Delete replaced mutable runtime fields
and projection-specific pending stores in the same change.

### 4. Cut semantic consumers over

Move widget state, action availability, exact Undo, Ask completion, request lifecycle,
conversation, receipts, local delivery, banner, margin contributions, and the display of
authoritative agent activity to computed readings from the snapshot. Keep canonical
activity derivation and the agent-stop gate in Python. Keep one semantic command for each
browser result and route visible controls and keyboard bindings to it.

Use the held-response journeys to cut over all consumers before removing their previous
read paths. The final merged state has no consumer that combines server events and
pending gestures independently.

### 5. Cut rendering over to Lit

Convert generated regions by ownership boundary rather than by visual proximity:
widget controls, Ask, request controls, conversation surfaces, margin entries, and
remaining chrome. Each conversion retains the existing semantic command and receives a
read-only computed value. Move authored children into an explicit retained region before
letting a template own adjacent generated children.

Preserve transient interaction within an active document through node retention and
explicit local controllers. Cross-revision continuity uses the bounded handoff from step
1, not a generalized DOM transaction, module-state serializer, or rollback mechanism.
When the last caller of an imperative reconciliation helper moves, delete the helper and
implementation-coupled tests. Move every surviving behavioral case to the new public
entry point, including refusal, pending exact Undo, frozen-thread scope, draft
generations, repeated anchors, and cross-parent widget continuity.

### 6. Unify presentation readiness and export

Replace owner-specific commit proof with the ticketed semantic/presented epoch contract.
Adapt widget upgrade, external data, revision activation, conversations, render gates,
and export to the same barrier. Verify that stale renderer instances and superseded
epochs cannot complete the active barrier. Verify serializable shadow roots and
stylesheet materialization in screen and print. Reuse the structured Playground fixture
to prove both outputs: a script-disabled static copy and an offline-interactive copy that
uses the same captured renderers while exposing no host transport or command path.

### 7. Remove transition code and publish the contract

Remove adapters used only during the branch, unused DOM state attributes, old event
subscriptions, and duplicate lifecycle stores. Run the import-boundary and unused-export
checks over the final graph.

Move the stable contracts from this note into their owners:

- cross-runtime state and publication invariants into repository `CLAUDE.md`;
- browser ownership, presentation, local-state, and build boundaries into
  `skills/leaf/assets/CLAUDE.md` and module headers;
- package authoring and plain-JavaScript usage into
  `skills/leaf/references/packages.md`;
- contributor build commands and generated-output ownership into
  `scripts/CLAUDE.md` and the build script's help;
- reader-visible effects into the appropriate public authoring references.

Delete this note and its link from the joint `TODO.md` item once those homes are complete.
Keep that item until the page-instance outcome is complete too.

## Acceptance

The cutover is complete when all of the following hold:

1. A forward gesture and its exact Undo change the widget, Ask, commands, margin,
   receipt, conversation, and local delivery readings immediately, before a held request
   resolves. Canonical agent activity remains the server-supplied reading.
2. Multiple unresolved gestures remain ordered across accepted, refused, duplicated,
   delayed, and overlapping state responses. A reload matches the final local result.
3. An authoritative read prepared before a later gesture rebases over that gesture at
   commit instead of overwriting it. A read that finishes preparing after a newer server
   reading committed is discarded, including when the newer response changes non-event
   state without advancing the event sequence.
4. A rejected gesture reveals the newest surviving local action, accepted action,
   standing report, or authored value in that order.
5. Within one active document, focus, caret, text selection, draft generations, media,
   disclosure, drag state, reading position, and nested custom-element instances survive
   every applicable render. Automatic revision activation waits for active composition
   and drag to end, then a fresh document restores only recoverable drafts, reading
   position, and standing destinations whose stable identities remain valid. It carries
   the bounded unresolved ledger, reconciles known acceptance first, and only then tests
   remaining commands against the new document context.
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

## Implementation handoff

The next session starts with complete revision capture from the page-instance boundary,
then the joint validation slice, not a repository-wide mechanical conversion. It should
treat the current optimistic projection fold as source material, not preserve every
surrounding browser interface. The spike decides whether the Lit boundary is as small as
expected; its acceptance evidence authorizes the full cutover. Page-owned declarations
then land through that final public API, the remaining semantic and rendering consumers
cut over, and interactive export follows the shared presentation contract. Playground
package expansion comes after those primitives exist.

The implementation stays one architecture: one publisher, one immutable snapshot, one
pending ledger, computed semantic readings, and renderers that receive values. A
temporary adapter may exist within the unmerged branch to keep the test suite runnable,
but no compatibility layer, feature flag, duplicate store, or old read path remains in
the final change.
