# Solid 2 and UI dependencies

Evaluation date: 2026-10-22. Implementation: [draft PR #3462](https://github.com/max-sixty/leaf/pull/3462).

Leaf's application views and reactive state now use Solid `2.0.0-rc.16`.
WebAwesome `3.14.0` remains responsible for copy feedback and screenshot
comparison. Its private Lit implementation is bundled with those controls;
Leaf no longer exposes Lit as its application rendering or package author API.

The selection criterion is maintained behavior and integration quality. Reducing
the dependency count is not a goal. A native HTML button, search field, select
or radio is appropriate where the browser already supplies the needed behavior.
A component library is appropriate when it supplies useful behavior Leaf would
otherwise have to maintain.

## Lit versus Solid for Leaf

| Concern                            | Lit                                                            | Solid 2                                                                                |
| ---------------------------------- | -------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Existing custom-element lifecycle  | Fits directly; lowest migration cost                           | Leaf keeps the lifecycle and gives generated views retained Solid roots                |
| Reactive state                     | Native Preact selections with SignalWatcher and AsyncDirective | Native memos, effects and projections share one graph with view updates                |
| Authored HTML and retained editing | Leaf must preserve nodes and native state across redraws       | Still a Leaf responsibility; keyed rendering alone does not preserve all browser state |
| Build-free package authors         | Tagged templates                                               | Tagged templates through the shared `/vendor/solid.js` API                             |
| Parser-time first paint            | Shared initial/live Lit rendering on main                      | Shared initial/live Solid rendering; live modules adopt the same nodes and graph       |
| Maturity                           | Stable and already integrated                                  | Release candidate, with pinned local upstream adaptations                              |

Solid offers a more coherent reactive graph and selective updates within retained
views. Solid now schedules a graph of explicit DOM dependencies and settles bindings
before focus and geometry work. Leaf retains its semantic presentation ledger,
immutable state and DOM movement integration. Bindings receive snapshots from their
owners; semantic readers and native DOM callbacks belong to those owners' lifetimes.

**Review recommendation: keep this as a draft experiment; the net benefit does not
yet justify replacing Lit on main.** The implementation demonstrates a viable
direction, but changes package authoring, scheduling, first-paint delivery and
focus retention without an established startup speedup. The matched corpus
comparison against the earlier main baseline found less than a one-percent reduction
in total delivered HTML and code. Those historical measurements are not results
against the newly merged main and do not establish a performance reason to migrate.

The build documents and checks the upstream seams for retained DOM movement,
quiet form writes, detached-root event collection, template traversal,
custom-element upgrade before refs, and follow-up notification when a draw
publishes a dependency it has already read. See [build/AGENTS.md](../build/AGENTS.md)
and [build/solid.mjs](../build/solid.mjs). These are review and upgrade costs,
not reasons to replace mature controls with bespoke implementations.

Review also reproduced an error-isolation regression: a throwing template binding
could halt Solid's shared scheduler and freeze unrelated views, even when Leaf
caught the error. `createView` now uses Solid's public `Errored` boundary, releases
the failed root and rethrows at Leaf's synchronous presentation boundary. The next
props update can remount it. The regression test covers failed initial mounting,
failed updates, cleanup, unrelated updates and recovery; a browser probe also
checks recovery with the delivered shared runtime.

Local component signals can fail between props publications too. Those failures
keep a visible native boundary and report through the platform's error path. View
error delivery waits for its publication to retire, so cancellation cannot swallow
a fault, and a commit-owned error is not reported a second time.

Reconsider adoption when Solid's release and the upstream fixes reduce the cost
of these adaptations, or when a measured interaction or maintenance improvement
outweighs it. Ordinary native controls and retaining WebAwesome can be chosen
independently of the rendering framework; neither is evidence for Solid itself.

## Review after merging current main

The merge incorporates main through `0c4bb28` (85 commits since the original
comparison), including its repository reorganization, serving-runtime delivery,
unified panel search, focus visibility, flat summary folds, shared screenshot
inspection, and indexed diff preparation. These product and performance improvements
remain in the candidate independently of the renderer choice. The final integration
also preserves main’s shared composer draft payload and Resume writing selection,
wrapped trace labels, publication admission simplification, bounded upload reader,
explicit unstamped-export refusal, and startup tests for serving-runtime URLs.
On me’s Show action keeps its route until arrival has chosen a thread or page
destination, preserving the exit control when travel remains inside the panel.

**Recommendation: retain Lit on production main.** The Solid branch improves on its
own earlier architecture, but current main makes migration less compelling. Main
already removed `watchProjection` in `23dff9c`, uses `SignalWatcher(LitElement)` for
tracked rendering, `AsyncDirective` for command attachment, native computed
selections, and keyed templates for generated lists. Retained DOM and shared initial
and live rendering are shared capabilities. Removing a redraw bridge is no longer
a reason to migrate.

Solid's distinct gains are selective bindings through top-level props projections
and explicit dependencies on committed DOM. They are useful architectural properties,
but no matched evidence yet shows a user-visible speedup over current main. They
come with six pinned upstream adaptations, a custom element lifecycle adapter,
explicit imperative reaction roots, and deferred error ownership. Main also patches
Lit movement and refs; the comparison is an increased integration burden rather
than patches versus no patches. Solid remains a release candidate.

The presentation redesign removes numeric ranks and their microtask queue. It does
not eliminate application coordination: semantic proof, asynchronous preparation,
generation checks, cancellation and retained editor ownership remain necessary.
Those are Leaf responsibilities, and deleting them would weaken correctness.

Useful work to carry onto Lit main:

- Express which committed DOM a dependent owner requires, using native reactive
  dependencies and Lit completion. Main's numeric scheduler currently guarantees
  only that an earlier renderer reached its first await. Keep DOM completion
  separate from held asynchronous proof, so one held region cannot stall unrelated
  drawing.
- Keep main's native framework lifecycle and command directives. The experiment
  confirms the cost of maintaining application substitutes for those interfaces.
- Port behavioral regression cases for retained selection/editor identity,
  replacement, disconnection, late failures and balanced input attribution. Port
  the behavior, not Solid's error adapter, which addresses Solid-specific timing.
- Publish mechanical DOM changes and signal changes atomically. Preact `batch`
  already gives main the appropriate primitive.
- Declare visual-review capture resources in its data contract:
  `resources: ["cases[].before", "cases[].after"]`. This fixes missing images in
  offline exports on Lit as well. The merged offline browser regression proves
  decoded images, case changes and keyboard slider use without network requests.
- Keep dependency decisions independent: WebAwesome's maintained copy and
  comparison behavior remains valuable. Native ordinary controls and any future
  component-library trial should be justified by their own behavior and quality.

Main's hidden-in-place summary folds, retained search editors, lf-shot ownership and
off-document/indexed diff preparation are concrete examples of framework-independent
improvement. They are already present on main; they should not be credited as new
benefits of this branch.

The candidate through `d76ea44` passed 146 framework/build, 534 runtime and 85 Worker tests.
Focused browser checks and independent desktop/light and phone/dark review cover
search focus and retained drafts, flat summary folds, option state and tab history,
late screenshot loads, source refresh/reordering, offline capture inspection, diff
selection, focus visibility and registered-property shift attribution. A focused
WebKit check also verifies that summary folds retain iframe documents and selected
text. Search retention checks assert the initial focus handoff before filling the
field, including opening search while replying in a thread.

The corpus comparison before the final 12 main commits, at `0c1a1de` against Lit `d76ea44`, uses each renderer's
matching page modules. The committed corpus HTML is unchanged. Both arms report no
console errors, failed widgets or startup layout shifts. External code (JavaScript,
CSS and registry) is 6,401,506 bytes on Lit and 6,331,105 on Solid: about 70 KB or
1.1% less. JavaScript requests fall from 118 to 116. Single sequential loads under
a shared host do not establish a startup timing improvement.

## Native rendering phases

The ranked microtask presentation pass is removed. `createPresentationFlow` owns
Solid effects connected by explicit DOM dependencies: a widget follows its current
parent, projection follows committed widget DOM, threads follow projection, and
obligations follow threads, and annotations follow obligations. A dependency advances after synchronous rendering and
post-render work, including failure; an unrelated owner's asynchronous preparation
cannot hold the graph behind it. Independent effects have no FIFO contract.

`renderCommit(write)` separates publishing retained view props from native Solid
settlement. `afterRender` runs focus, DOM queries, layout measurements and third-party
setup after those bindings settle. Nested writes settle before outer measurements.
`committed` covers that DOM work; `ready` also adopts asynchronous preparation. The
presentation ledger uses its ticket's final verdict, including explicit fallback
proof, rather than confusing DOM completion with semantic completion.

The conversion covers `LeafElement.updated()`, retained views, document
presenters and their asynchronous continuations, thread messages/cards/reactions,
the floating panel, command reference, Page Map, media inspection, visual review,
file editor, recording timelines, diff summaries and draft controls. Native inputs,
editor instances, keyed nodes and browser selection remain retained. A custom widget
that formerly queried its freshly created template inside `render()` now uses a
binding or `afterRender`; the page-owned fixture exercises that authoring contract.

Supersession belongs to the owning render generation. A departed owner skips its
remaining callbacks while retiring their input-attribution jobs. A newer publication
of the same view owns any deferred binding error; an obsolete check cannot consume
that error and let the latest failed reading appear successful. Root construction
precedes connection registration because native effects may run during registration.

Leaf still records which semantic revision is actually visible across gesture holds,
external-data delivery, asynchronous preparation, renderer replacement and failure.
That ledger schedules no renderer. Small native reaction roots track imperative
owner callbacks and their explicit lifetimes, including post-render reads; they are
not another reactive dependency engine. The former perpetual tracked-effect adapter,
element microtask queue, ranked pass and projection-watcher microtask are gone.

The public primitives are Solid's `createEffect`, `createMemo`, `createReaction` and
`onSettled`. No additional upstream scheduling adaptation was introduced. A direct
read immediately after writing props inside an effect remains stale; consumers now
use the post-render phase instead of asking for a nested flush.

Regression coverage lives in `browser/framework/rendering.test.mjs`,
`browser/framework/presentation.test.mjs`, `tests/runtime/solid-views.test.mjs`,
`tests/runtime/leaf-element.test.mjs`, and the application-boundary, input-attribution
and parent-widget ordering browser tests. These protect asynchronous holds, failed
measurements, retained focus/editing, native/shadow owners, disconnection and
supersession rather than the old queue's incidental order.

Before merging main, the redesigned candidate passed 145 framework/build, 538 runtime and 85 Worker
tests, plus 28 focused Chromium cases. Independent browser review covers delayed
image loads and acknowledgements during editing, disconnects, command-hub
save/discard/undo, keyboard navigation and narrow dark layouts. The matched corpus
load has no console errors or startup layout shifts in either arm. The reduction in
delivered HTML plus external code remains below one percent; external JavaScript
requests fall from 115 to 113. These single loads do not establish a timing
improvement.

An offline handoff check also found that the visual-review data contract omitted
its capture resource declarations on both Lit and Solid. Declaring the before/after
images now makes the standard snapshot/export capture them. An offline browser
regression checks decoded captures, case selection and the keyboard slider without
HTTP requests.

## UI library evaluation

Versions and package source were inspected, rather than assuming a permissive
peer range implied compatibility with Solid 2's changed API.

| Library                                                                                                  | Evidence                                                                                                                                                                                                                              | Decision                                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [WebAwesome 3.14.0](https://www.npmjs.com/package/@awesome.me/webawesome/v/3.14.0)                       | Framework-independent custom elements. A Chromium probe with the shipped Solid runtime passed input binding, focus/selection retention and select upgrade. Leaf's restored copy and comparison behavior also passes browser journeys. | Keep copy feedback and screenshot comparison. Load comparison with its consumer; keep Lit private to the library.                                                  |
| [Kobalte 2.0.0-alpha.4](https://www.npmjs.com/package/@kobalte/core/v/2.0.0-alpha.4)                     | Exact peers match Solid and `@solidjs/web` `2.0.0-rc.16`. Its README explicitly says components have not been fully tested.                                                                                                           | Best native Solid candidate for a future component-specific trial. Package compatibility was inspected; a complete Kobalte browser integration was not tested.     |
| [Ark UI Solid 6.0.0-next.0](https://www.npmjs.com/package/@ark-ui/solid/v/6.0.0-next.0)                  | Published source and its Zag Solid adapter still use Solid 1 APIs, despite the open-ended peer range.                                                                                                                                 | Not a drop-in dependency for this migration.                                                                                                                       |
| [Corvu 0.7.2](https://www.npmjs.com/package/corvu/v/0.7.2)                                               | Peer range is Solid `^1.8`.                                                                                                                                                                                                           | Revisit after explicit Solid 2 support.                                                                                                                            |
| [Spectrum Web Components 1.12.5](https://www.npmjs.com/package/@spectrum-web-components/bundle/v/1.12.5) | Framework-independent custom elements, with an established component set and its own visual system.                                                                                                                                   | Technically viable; changing libraries would require a separate theme and behavior integration. No demonstrated advantage for Leaf's current two library controls. |

A Kobalte trial should start with a concrete missing or inadequate control, and
compare keyboard navigation, focus after refresh, assistive semantics, touch,
print, and Leaf theme integration. Its alpha status adds another prerelease
surface today. Replacing WebAwesome wholesale has no demonstrated benefit.
