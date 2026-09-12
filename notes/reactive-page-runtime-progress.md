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

The kernel is deliberately not wired into runtime readiness yet. That cutover follows
the public widget controller so one presentation seam can replace every legacy queue at
once; until then, existing presentation stamps and queues remain authoritative.

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

## Remaining implementation

Implement the public `widgetController(owner)` and migrate package/page modules away from
the separate action/request helpers, `watchActions`, public DOM standing-state reads, and
the broad `lf-actions` semantic bus. The controller must expose an immutable complete
reading, synchronous optimistic dispatch plus separate delivery, an owner-lifetime
subscription, bounded local-edit deferral, and the single presentation seam. Static
identity, quote, declaration, and request-offer facts come from the authored revision;
projected ownership, Ask state, lifecycle, availability, provenance, and exact Undo come
from the publisher.

Then wire the integrated semantic/presented epoch and ticket coordinator across every
independent readiness queue before converting generated regions to Lit. Complete the
Targeting identity/controller cutover, add offline interactive export without weakening
script-free static export, then dissolve this checkpoint plus both plan notes into their
owning contracts.

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
