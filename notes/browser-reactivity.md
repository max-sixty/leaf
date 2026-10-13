# Browser reactivity

How the browser runtime decides what to repaint, what moving further toward Lit's
reactive model would take, and where the code could get simpler. This note gathers the
open questions; each owning module's header states the current contract.

## Where it stands

- **One publication, shared parts.** The application publisher holds the semantic root
  in one Preact signal. Each publication shares every subtree equal to the previous
  one (`build/browser/snapshot.ts`, `share`), so an unchanged part keeps its identity,
  and a selection (`applicationState.select`, `readPart`) is a `computed` that changes
  only when its part does.
- **Watchers collect what they read.** `watchProjection(owner, paint)` collects every
  part of the publication its paint reads synchronously (`collectReads`, `snapshot.ts`)
  and repaints when one of those parts moves (`runtime/projection-watch.js`). The named
  watchers (`watchAsks`, `watchReports`, `watchWork` and the rest) are that watcher
  around a reader, and a widget callback that also calls `readWork` or a controller's
  `read()` is subscribed to those parts too. Only reads of the publication count. A
  Preact effect would also subscribe the paint to private signals it reads, such as
  where the user stands and the thread list's models, which a paint may also write, so
  a paint could set off its own repaint.
- **Regions declare their reading.** The four document regions (projection, threads,
  asks, the Questions panel) are `applicationPresenter`s that name, as a `reading`, the
  parts they draw (`runtime/semantic-state.js`). A publication that leaves that reading
  alone carries the region's last commit into the new epoch.
- **Key and button availability are tracked effects** (`runtime/keyboard/scopes.js`).
  Private state their predicates read, such as where the user stands and the thread
  list's models, is held in signals so the effects see it move.
- **Lit renders templates.** Paints call Lit's `render()` synchronously. `LitElement`
  appears only in `RetainedFace` (`runtime/retained-face.js`), whose updates wait a
  microtask unless the caller asks for `now`.

## Tracking the regions too

A region's `reading` is a hand-written list of its inputs. A read outside the list
leaves the region showing stale state, silently. So far no review has found such a
miss in a region: each one was in a widget watcher or a memo key, which is why the
watchers moved to tracking first.

Tracking cannot replace the regions' readings as they are written, because a region
paints across `await`s. The thread presentation reads its threads, waits for frozen
widgets in thread messages to load and present (`prepareFrozenWidgets`) and for a
package's thread reader to prepare, then commits. Collecting reads, like a signals
effect, sees only synchronous reads, and JavaScript has no way to carry a collection
across an `await`: the TC39 AsyncContext proposal would, but no browser ships it.

The change that would let tracking cover a region is a split into two phases: a
synchronous read that gathers everything the region draws from the root into one
immutable model, tracked, and an asynchronous paint that touches only that model and
the document. The thread presentation already reads its threads before its first
`await`; its later reads (approval history, frozen widgets' descriptors in
`thread/thread-list.js`) happen to fall inside its declared reading. Nothing would
enforce the split: a later edit could read the root after an `await` again, and no
runtime check can tell a read inside a region's paint from any other, for the same
reason tracking can't.

## LitElement and microtask updates

`LitElement`, and Lit's `SignalWatcher` mixin built on it, update a component on the
microtask after its inputs change. A microtask finishes before the browser draws the
next frame, so the delay costs no visible latency. It costs code that reads the
document right after a paint, in the same script: moving focus onto a control just
drawn, measuring a box or reserving its room, held news deciding whether a change
would move what the reader sees (`thread/held-news.js`), and a region committing its
paint in the presentation coordinator's ordered pass. Under a microtask update each of
those awaits `updateComplete`, which turns synchronous code asynchronous and lets
other work run in between. When the margin's chip placement went asynchronous to use
Floating UI, it took three ordering bugs to settle.

`SignalWatcher` would also bypass the coordinator: a region claims its presentation
inside the publication and paints in the order `PRESENTATION_ORDER` declares, while a
self-updating component schedules itself. Tracking itself needs neither LitElement
nor the microtask: a Preact `effect` tracks in the current script, as the watchers and
key availability already do. So `skills/leaf/assets/AGENTS.md` keeps paints that must
land in the current script on `render()`, and nothing on the path toward tracking
needs that rule lifted.

## Reads of the whole root

`readApplication()` reads the whole root, so a watcher whose paint calls it repaints
on every publication. Under declared readings that cost nothing, since the declared
list decided when to paint; with collected reads it decides. The readers on watcher
paths now go through narrow parts (`readPart`, the runtime getters in
`runtime/context.js`, `readAsks`, `threadState`). The other callers of
`readApplication()` are mostly event handlers and the regions, which collect nothing.
A lint rule refusing `readApplication()` outside `semantic-state.js` and the publishers
would keep a new watcher paint from reaching for the whole root.

## Simplifications this opens

- **One watcher.** With tracking, `watchAsks(owner, cb)` is
  `watchProjection(owner, () => cb(readAsks()))`, and each named watcher is that
  composition. The repository asks for one canonical API per capability: the named
  watchers could go, leaving one watcher and the readers. That changes the public
  widget API across the packages and examples, and `module-authoring.md`'s "Page
  readings" section.
- **One record of what a paint read.** `clockValue` and `clocked`
  (`runtime/presence.js`) keep their own record of which paints read the time, and the
  watcher separately compares the projection deferral (`projectionDeferred`) and the
  `PRESENTATION` count it last saw. Readings of the clock, the deferral and the
  presentation that record themselves in the same collection as the publication's
  parts would leave the watcher one rule for every input and retire those records.
- **Region readings, after the split above,** would go with the hand-written lists.

## What reactivity will not fix

The corpus page's comment still paints in about 120–135 ms against the 100 ms
budget. The remaining time is style recalculation over the page's ~1,700 elements,
much of it forced by geometry reads during the paint and made costly by the theme's
`:has()` rules, not repaint work the runtime could skip. `uv run leaf-dev profile
corpus comment` lists each forced recalculation by call site and milliseconds.
Closing that gap is a CSS change: fewer `:has()` rules, or containment around the
regions the runtime writes.
