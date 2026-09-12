# Joint implementation checkpoint

This is a handoff for the unfinished [page-instance boundary](page-instance-boundary.md)
and [reactive runtime](reactive-browser-runtime.md) program, not another specification.
The user requested Astra implementation in worktrees, then asked to conserve tokens.
The implementation remains local on `reactive-page-runtime`; it is not ready to merge.

## Integrated foundation

- Page-owned declarations and widgets compose with the selected layer.
- Revisions capture HTML, registry, runtime, authored modules, styles, and media as an
  immutable dependency graph. Historical documents and event admission use captured
  contracts instead of mutable candidate files.
- Activation starts a fresh document with explicit continuity handoff. Parsed delivery
  rewrites imports and URLs without changing prose or duplicating page-module execution.
- Live shells and website bundles publish revision-specific resources. Static export
  inlines captured styles and media, including images added in conversation afterward.
- MCP full-page routes and inert snapshots read captured revisions even when candidate
  files are invalid. Snapshot styles retain separate stylesheet and media boundaries.
- A locked contributor build supplies Lit, Signals, and TypeScript output as committed
  self-contained assets. Authors and plugin users need no Node build.

## Integrated semantic boundary

The immutable semantic publisher is integrated at `e0578973`. One root owns accepted
state, authored baselines, unresolved attempts, effective projection/widget/conversation
readings, data, and the semantic epoch. Presentation failure no longer rolls accepted
truth back, while pending delivery still retires only after presentation proof. Active
presentation, conversation, context, and historical comparison read publisher-owned
selectors; the old writable accepted, projection, conversation, and pending stores are
gone.

Projection entries carry the action/report spec captured by the revision that admitted
them, so a historical view is never reinterpreted through the current DOM or registry.
The render gate's authored/carried/current comparison remains an explicit publisher-owned
counterfactual selector rather than an active-state fold.

Candidate compatibility is also integrated. Activation and re-vendoring share one causal
check for standing page contracts and frozen thread markup, while historical-only events
use their captured registries. Request-offer attributes are authored static state: registry
validation rejects an `x-state` or `x-report` record that could rewrite one.

## Integrated presentation kernel

The pure presentation coordinator is integrated at `2274f93a`. It owns document and
semantic/presented epochs, sealed publication barriers, stable regions, renderer and
ticket generations, replacement/disconnection, async descendant membership, fail-soft
completion, and stale-document/value suppression. Its causal domain suite covers work
that completes before sealing and obsolete seals as well as the longer renderer races.
An equal-value renderer replacement reopens mechanical readiness at the same semantic
epoch; the replacement must commit while the stale instance cannot satisfy the repair.

Semantic publication, document installation, the page interface, widget render and
preparation regions, frozen-thread capture, and external-data subscriptions now use the
kernel. Publication opens before the Signals root changes and seals after synchronous
subscribers have registered their work. Current readiness revalidates newer epochs and
same-epoch renderer replacement; scoped waits do not inherit unrelated deferred work.
The monotonic `data-lf-presented` mark remains only the initial presentation milestone.
Render checks, the browser harness, and export now revalidate the active document's
current coordinator reading after that milestone. Conversation and projection chrome use
the same coordinator, including frozen-widget preparation, drag deferral, fail-soft
settlement, and pending-action retirement. The synchronous browser probe lives on Leaf's
own bootstrap element so modular pages and bundled published shells share the contract.

## Integrated design intent

The no-alias design-comment cutover is integrated at `aa745905`. The closed event
contract, browser producers, conversation filtering and placement, transcript, example,
agent route, and package guidance now use `about: "design"`; `about: "layer"` is refused.
Infrastructure meanings of layer generation, composed package ownership, registry
sources, and delivery headers remain unchanged.

## Integrated fresh-document proof

The activation-continuity proof is consolidated at `f7526f72`. One causal browser
journey now holds a local option delivery, proves the candidate revision cannot replace
that document, releases the attempt, and observes a new `performance.timeOrigin` with
the accepted standing choice, semantic reading position, valid authored-control focus,
and closed general draft restored. A page-module global deliberately does not survive.
No runtime mechanism or cross-document retry state was added.

## Integrated public widget controller

The package-facing controller cutover is integrated at `027b8655`. One captured owner
now exposes an immutable complete reading, owner-lifetime subscription, synchronously
optimistic action/request/exact-Undo dispatch with separate delivery, bounded local-edit
deferral, and one asynchronous presentation seam. Every bundled widget and page fixture
uses that controller; the former request helper, public standing-state reads, package
private-runtime imports, and broad `lf-actions` semantic bus are gone.

The controller derives availability, Ask and request lifecycle, projected ownership,
provenance, carried history, and exact Undo from the semantic publisher. Authored identity,
declarations, bindings, quote state, and request offers remain captured revision facts.
Descriptor drift fails closed, and generated visual-review shots receive an explicit
presentation-only callback instead of weakening authored descriptor capture.

## Integrated Targeting foundation

The target-reference kernel and Targeting controller cutover are integrated at
`22c164f6`. Pointer and keyboard selection use one unbounded composed candidate walk.
Exact ids and prose-free structural references resolve to an explicit `resolved`,
`detached`, or `ambiguous` result; anonymous sibling insertion therefore blocks rather
than silently retargeting. The Targeting package keeps the visible label and context
separate from durable identity, exposes arm/disarm/reset/current-draft lifecycle, keeps
unresolved target cards visible, and refuses submission until every target resolves.
Its package schema was cut over with the widget so the new draft format is never emitted
into an admission contract that would reject it.

Generic multi-role declarations and admission are integrated at `b40980fe`. Action and
report contracts declare named reference roles; the browser captures exact ids or
prose-free structural records inside the immutable page or frozen-fragment boundary, and
the server resolves and validates those records against the captured source contract.
Dispatch re-resolves immediately before transport, so removal or newly ambiguous
structure refuses the gesture instead of silently retargeting it.

## Integrated first Lit owners

Shared request controls are integrated at `dc698331`. Lit owns only generated request
buttons and statuses; authored operation/release nodes and their descendants remain
identity-stable light DOM. One immutable controller reading drives the generated state,
and the holder's `updateComplete` includes its child controls.

Quoted and purely structural option groups remain outside semantic state at `a85a3c71`;
only live or settled decisions request a controller. This preserves the registry's
intentionally id-less specimen while keeping missing semantic identity a hard controller
error.

Option marks and the thread-only Done control are integrated at `4de2b74a`. Authored
`lf-option` descendants remain stable light DOM; one controller reading drives the
generated controls, and their `updateComplete` participates in widget presentation.

The Asks tray list is integrated at `dd0e66bf`. One keyed light-DOM Lit owner replaces
the manual row map, preserves row identity and focus across reorder or removal, resolves
activation against the current Ask id, and keeps pending action retirement behind the
`asks` presentation region. A failed update retains the prior usable list and settles
through the coordinator.

## Integrated interactive export

Offline-interactive export is integrated at `a9f3facd`. It packages the captured revision
graph, accepted state, locked runtime, authored modules, styles, and media into one file.
The normal publisher and presentation coordinator render it from `file://`; local controls
and navigation remain active, host commands are unavailable before dispatch, and CSP plus
embedded resource addressing permit no external request. Script-free static export remains
the default and uses its existing browser-rendered path.

The export work also exposed a startup cycle in the projection region: provisional
`waiting` chrome held the current barrier that had to finish before the first state feed
could start. That provisional ticket now settles without committing widget state; the
authoritative `ready` publication opens a new ticket and paints the actual projection.

## Remaining implementation

Continue converting generated regions to Lit by ownership boundary. The live Leaves list
and Ask banner/bulk controls are the active next slices; conversation surfaces, margin
entries, and remaining chrome follow where their authored-node and reparenting boundaries
can be retained explicitly. Resolve the two deterministic outbox/focus regressions found by
the serial browser run, complete the final integration and performance checks, then dissolve
this checkpoint plus both plan notes into their owning contracts.

## Verification checkpoint

The full everyday suite passed **1069/1069** at foundation commit `522ad464`. After the
semantic and compatibility integration, 142 outbox/startup browser cases, all 113
projection cases, all 99 server cases, 274 interaction-contract cases, and 10 browser
build/domain tests pass. Generated browser output and pre-commit are clean. Run the final
everyday suite again after the remaining slices are integrated.

The presentation kernel has ten focused causal cases; its TypeScript check, 20-case
browser/build suite, and touched-file pre-commit checks pass.

The design-intent cutover passes its 12 focused admission, composition, filtering,
label, placement, transcript, and gallery cases plus an integration rerun of the server
round trip and composed panel facets. The locked browser build remains unchanged.

The consolidated application-boundary and outbox files pass all 49 cases; the combined
fresh-document journey also passes independently on the integration branch.

The controller cutover passes all 27 browser build/domain tests, the restored false
settlement proof, focused public-boundary and direct widget journeys, and 279 of its
282-case broad browser selection. The three remaining failures reproduce on the
pre-cutover integration baseline: one cross-revision option-button identity expectation
and two chart covered-word SVG cases. Full pre-commit passes.

The Targeting foundation passes four core-reference journeys, two package-controller
journeys, standing replay, package validation, syntax checks, and touched-file
pre-commit. The complete widget module passes 152 cases; its two chart failures are the
same baseline failures above.

The integrated coordinator and external-data cutover passes all 32 browser domain/build
tests. A combined current-branch run of application-boundary, target-reference, startup,
and the package-init render regression passes all 104 cases; eight focused semantic
reference contract cases and the quoted settled-options journey also pass. The external
data slice separately passes 13 startup/provenance cases and touched-file pre-commit.
The current-readiness probe slice passes the 32 browser domain/build tests, causal
same-epoch replacement/failure and late-export browser cases, nine neighboring harness
journeys, and touched-file pre-commit. Its synchronous harness correction passes the nine
formerly early-returning journeys. The complete suite then passed 1082 of 1083 cases; the
one bundled-shell failure identified an unpublished-module assumption in the probe, and
both bundled and modular published-shell cases pass after the bootstrap-element cutover.

Conversation/projection coordination passes its focused region, frozen-widget, retirement,
and startup journeys. The interactive export's `file://` journey, static preview neighbor,
waiting-to-ready projection proof, 33 browser domain/build tests, and touched-file
pre-commit checks pass on the integrated tree.

The keyed Asks list passes five focused journeys and all 33 browser domain/build tests on
the integrated tree. The broader Ask keyboard selection exposed one stale test proxy for
generated custom-element controls; its authored-Ask ownership proof now passes directly.

The website bundler slice passed 61 worker tests, typecheck, five immutable-shell tests,
three site tests, and a complete site build/bundle. Local pre-commit passes.
The MCP slice passed 29 of 30 cases before the final media-path fixture correction;
the remaining complete-interface browser case then passed on the integrated tree.
The final focused export run passed all five cases, including both conversation-media
states, captured historical CSS, corpus, and visual-review gallery.

One render-gate failure was reproduced at clean base `214588e3`: the `new-widget`
parameter of `test_render_accepts_actions_made_after_the_authored_change` lacked its
banner at dark 1200×900 under `-n0`. That evidence covers only that exact failure.

Before landing, run the remaining browser journeys and compare startup requests/bytes
with the base using `scripts/verify-site-local.sh`; no performance improvement is
established yet. Review the integrated semantic publication path and refresh this
checkpoint with final test evidence. Landing still needs explicit authorization.

## Worktree ownership

- Integration: `/Users/maximilian/workspace/leaf.reactive-page-runtime`.
- Semantic publisher: `/Users/maximilian/workspace/leaf.astra-fresh-revision-activation`.
- Presentation coordinator and design intent:
  `/Users/maximilian/workspace/leaf.sol-vocabulary-compatibility`.
- Contributor build and website bundler: `/Users/maximilian/workspace/leaf.astra-browser-build`.
- Captured revisions, static export, and MCP: `/Users/maximilian/workspace/leaf.astra-revision-artifact`.

Do not discard these branches or treat another worktree's unfinished edits as integrated.
Use the integration branch's commit history to identify which slices were cherry-picked.
