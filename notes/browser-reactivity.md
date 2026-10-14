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
  Preact effect also subscribes the paint to private signals it reads, such as where
  the user stands, which a paint may also write: tracked by an effect, the annotation
  inventory's paint re-ran itself without end and hung the page.
- **Regions collect what they read.** The four document regions (projection, threads,
  asks, the Questions panel) are `applicationPresenter`s (`runtime/semantic-state.js`).
  Each one's `reading` says whether it owes a paint, and the parts its reading and its
  paint read are collected, as a watcher's are. A publication that moves none of them
  carries the region's last commit into the new epoch. Another owner a paint drives
  reads outside the collection (`untracked`, `snapshot.ts`), since what it draws is its
  own to follow: a widget a paint mounts, which connects inside that paint, and the
  margin the thread presentation refreshes once it commits, which has its own watcher.
- **Key and button availability are tracked effects** (`runtime/keyboard/scopes.js`).
  Private state their predicates read, such as where the user stands and the thread
  list's models, is held in signals so the effects see it move.
- **Lit renders templates.** Paints call Lit's `render()` synchronously. `LitElement`
  appears only in `RetainedFace` (`runtime/retained-face.js`), whose updates wait a
  microtask unless the caller asks for `now`.

## Reads after an `await`

A region claims inside a publication and paints on the pass after it, once the regions
ranked before it have painted, so a paint reads the root, and the document those
regions wrote, as they stand then. Collection sees only what runs synchronously, and
JavaScript has no way to carry it across an `await` (the TC39 AsyncContext proposal
would, but no browser ships it). So a region paint is handed `resume`, which wraps a
continuation, a `.then` callback or a function called after an `await`, so its reads
join the paint's parts while the paint is current. The thread presentation resumes its
commit after a package's thread reader prepares, and the thread list resumes the rows it
derives again once frozen widgets have connected (`renderReading`,
`thread/presentation.js`; `renderThreads`, `thread/thread-list.js`). The clock keeps its
own record of what a paint read (`clocked`), so `clocked` hands a paint the same kind
of `resume` for its time readings, and the thread presentation composes the two.
Nothing checks that a continuation is wrapped: a read in one that is not goes
unfollowed, as a read outside a watcher's paint does.

A region checks its parts from one subscription to the publication, made when the
region is. Subscribing to each part it read, again after every read, put its claim
after the publication's other subscribers, and a send that waits for the page to be
presented went on before the thread had claimed its paint.

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

## What a paint's readers cost

With collected reads, every reader a paint calls decides when that paint runs again,
so how narrowly a reader selects is a performance contract. On the corpus page the
first cut-over doubled the time from a card move to the server's reading on screen
(Sent 126 → 280 ms), because each of the seven `lf-atlas-worker`s repaints through
`readWork`, about 10 ms a paint, and two readers on that path read more than they
returned:

- `HeldReading.hold` read the phase as `readApplication().phase`, the whole root,
  so every publication repainted every worker. A read of the whole root inside a
  collection now throws (`collectReads`, `snapshot.ts`), and the phase is read through
  `runtime.statePhase`.
- `passages.js` derived which widgets' decisions retire their slots from a selection
  of every widget's state, so any widget action repainted every paint that reads a
  passage's words. The settlements are now a selection themselves, which moves only
  when a settlement does.

After both, the corpus comment and move match the declared-reading baseline. The throw
catches only the coarsest case. The rule behind both is to derive a reader's result
inside its selection, so its callers subscribe to the result rather than to its
inputs (`skills/leaf/assets/AGENTS.md`, "Working on the runtime"). A review found more
readers breaking it, now selections of what they return: `readThreads` (the thread
collection, not all thread state), the to-dos and undo list (`runtime.todos`,
`runtime.undo`, not the whole browser reading or view), and approval's blocking asks
and approved state (not every ask). No check finds the rest;
`leaf-dev bench-latency` against the previous commit shows one that costs time.

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

## What reactivity will not fix

The corpus page's comment still paints in about 120–135 ms against the 100 ms
budget. The remaining time is style recalculation over the page's ~1,700 elements,
much of it forced by geometry reads during the paint and made costly by the theme's
`:has()` rules, not repaint work the runtime could skip. `uv run leaf-dev profile
corpus comment` lists each forced recalculation by call site and milliseconds.
Closing that gap is a CSS change: fewer `:has()` rules, or containment around the
regions the runtime writes.
