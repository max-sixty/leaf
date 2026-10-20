# Browser reactivity

How the browser runtime decides what to repaint, what moving further toward Lit's
reactive model would take, and what a paint's readers cost. This note gathers the
findings; each owning module's header states the current contract.

## Where it stands

- **One publication, shared parts.** The application publisher holds the semantic root
  in one Preact signal. Each publication shares every subtree equal to the previous
  one (`build/browser/snapshot.ts`, `share`), so an unchanged part keeps its identity,
  and a selection (`applicationState.select`, `readPart`) is a `computed` that changes
  only when its part does.
- **Watchers collect what they read.** `watchProjection(owner, paint)` collects every
  part of the publication its paint reads synchronously (`collectReads`, `snapshot.ts`)
  and repaints when one of those parts moves (`runtime/projection-watch.js`). It is the
  one watcher packages use too: a reading has a reader (`readObligations`, `readQueues`,
  `readThreads`, `readWork`, `reportSequence`, `readHistory`, a controller's `read()`)
  and no watcher of its own, so a paint that reads several needs one watcher, and a
  paint that narrates reports passes `reportsPresented` as the watcher's proof. The
  same record holds the paint's readings of what stands outside the publication
  (`outsideReading`): the time it shows and the page's `PRESENTATION` count, each
  followed by the same rule. Nothing else a
  paint reads is followed. A Preact effect also subscribes the paint to private
  signals it reads, such as where the user stands, which a paint may also write:
  tracked by an effect, the annotation inventory's paint re-ran itself without end and
  hung the page.
- **Chrome paints are watchers too.** The floating panel and the version picker each
  paint through one `watchProjection`, and call its `refresh()` for their own
  mechanical inputs, such as an open menu or a comparison. How the server answered the latest read is in the publication (`reach`),
  so the status reads it rather than the state feed pushing each answer at it.
- **Regions collect what they read.** The three document regions (projection, threads,
  obligations) are `applicationPresenter`s (`runtime/semantic-state.js`).
  Each one's `reading` says whether it owes a paint, and the parts its reading and its
  paint read are collected, as a watcher's are. A publication that moves none of them
  carries the region's last commit into the new epoch. Another owner a paint drives
  reads outside the collection (`untracked`, `snapshot.ts`), since what it draws is its
  own to follow: a widget a paint mounts, which connects inside that paint, and the
  margin the thread presentation refreshes once it commits, which has its own watcher.
- **Key and button availability are tracked effects** (`runtime/keyboard/scopes.js`).
  Private state their predicates read, such as where the user stands, is held in
  signals so the effects see it move.
- **Lit renders templates.** Paints call Lit's `render()` synchronously. `LitElement`
  appears in `LeafElement` (`runtime/leaf-element.js`), whose moves draw in the
  presentation pass the publication starts, and in the composer's media shelf
  (`composing/input.js`).

## Reads after an `await`

A region claims inside a publication and paints on the pass after it, once the regions
ranked before it have painted, so a paint reads the root, and the document those
regions wrote, as they stand then. Collection sees only what runs synchronously, and
JavaScript has no way to carry it across an `await` (the TC39 AsyncContext proposal
would, but no browser ships it). So a region paint is handed `resume`, which wraps a
continuation, a `.then` callback or a function called after an `await`, so its reads
join the paint's parts while the paint is current. The thread presentation resumes its
commit after a package's thread reader prepares (`renderReading`,
`thread/presentation.js`). The time a paint
shows is recorded with its parts (`outsideReading`, `snapshot.ts`), so `resume` carries
those reads too. Nothing checks that a continuation is wrapped: a read in one that is
not goes unfollowed, as a read outside a watcher's paint does.

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
`runtime.undo`, not the whole browser reading or view), and approval's blocking obligations
and approved state (not every obligation). No check finds the rest;
`leaf-dev bench-latency` against the previous commit shows one that costs time.

## What a comment's paint costs

`uv run leaf-dev profile corpus comment` lists, per run, the main-thread tasks from
the key to the server's reading on screen, each forced style recalculation by call
site, and JS by function. On the corpus page most of the comment's time was script,
not the theme's `:has()` rules:

- An obligation whose widget stands in a thread message no one has opened has no
  node in the document, so every `elementById` of its id fell through to
  `shadowRootsIn`, which queried the whole document for each `x-shadow` tag. Every
  `lf-atlas-worker`'s goal, and every read of where the user stands, asks for each
  obligation's source, so one comment ran hundreds of those queries, about half its
  time. `shadowRootsIn` now reads the stages' registry (`liveStages`, `arrivals.js`).
- `rowArrows` read the computed `direction`, so each diff file's key availability
  forced a style recalculation of up to 5,700 elements between the writes of one key
  reflection. It now reads `:dir(rtl)`, which the `dir` attributes decide without
  computing style.

`uv run leaf-dev bench-latency --page corpus --transition comment` after both, five
paired runs on a host at load 8–10 (18 cores): the comment painted in 91 ms [83–98]
against the merge base's 238 [226–288], and the server's reading in 179 ms [171–190]
against 539. Three earlier paired runs at load 14–52 read 95–107 ms against 273–295. Profiled style time fell from 129 to 51 ms a run; the largest
forced recalculations left are the thread marks' geometry reads (`targetParts`, about
4 ms each).

## What the server's reading of a comment costs

The server's reading reaches the screen after two waits: the POST's answer, then
applying that answer. Each `leaf-dev profile` run's `.trace.json` times the first by
the POST's `ResourceSendRequest` and `ResourceReceiveResponse` events, and the task
after the response is the second. Three causes held the reading back:

- Every claim on a region a report waits for makes `reportsReady` false until the
  region commits, and a `LeafElement` that read it drew again on each move. A comment
  moved it seven times, so each `lf-atlas-worker` rendered four times, recomputing
  `readWork` each time, though every one of those renders ran after the proof had
  risen again and drew what it already showed. A `LeafElement` now draws again only
  when the proof rises (`leaf-element.js`).
- `readWork` read the whole obligation inventory, which a comment changes, so every
  worker drew again on the answer. It now selects the widget obligations that wait on
  the user, which a comment leaves alone (`work.js`).
- `postEvent` awaited the layer's settled promise, which put the POST behind every
  microtask queued before it, among them the presentation the comment's own
  publication claimed: the request left 28–41 ms after the key, profiled. It now goes
  out in the press, 7–10 ms after the key, once the layer is known (`layer-client.js`).

`uv run leaf-dev bench-latency --page corpus --transition comment` after all three,
fifteen paired runs over three invocations at load 10–17 (18 cores): the server's
reading reached the screen in 177 ms (interquartile 169–191) against the merge base's
203 (191–216), the POST answered in 61 ms against 89, and the comment painted in 94
against 105. A card move's reading fell from 151–154 ms to 116–121 in two five-run
invocations. A fourth comment invocation, at load 17–26, could not tell the arms
apart.

Admission read the page's obligations before and after the append, to decide whether
the event needs attention (`event_contracts.admitted_event`), and the answer's state
read them a third time. Most of each reading went to finding which widgets can ask, a
question of the document and its vocabulary alone. A stored revision's reading now
holds that answer across requests (`SourceReading.obligation_sources`,
`obligations.ObligationSources`), so each reading takes only what the log decides. In
process, a corpus comment's POST and its answer's state took 22 ms against 44, median
of nine.

`uv run leaf-dev bench-latency --page corpus --transition comment`, ten paired runs
over two invocations at load 9–17 (18 cores): the POST answered in 41 ms
(interquartile 35–79) against the merge base's 57 (46–87), but the server's reading
reached the screen in 169 ms against 168. Sent stays put because the server's time is off its critical path.
The answer arrives about 45 ms after the key, while the main thread is still running
the press (about 52 ms of script in its long frame) and the frame after it (about
35 ms, the pass `bundle-sample-visibility.js` names). Applying the answer then took
about 62 ms of script, 54 since the receipt joined the reading's publication (below).
What holds the main thread:

- **The press and its frame**, about 87 ms of script before the answer can be
  applied.
- **The margin's annotations draw twice per thread pass**: once from their own
  watcher, which waits only for the projection's chrome and so draws while the
  thread presentation waits on its preparation, and again when that presentation
  commits. Profiled, the two took 22 ms of applying the answer. Making the watcher
  wait for the thread region too, with the commit asking the watcher for its paint,
  drew the margin once (11 ms profiled), but the bench could not tell it apart from
  the base, and it broke two orderings that the inline draw in the commit had held
  without stating them. Reply continuity (`continueReplies`, `thread/focus.js`)
  runs after the commit and expects every surface, the margin's cards included, to
  be drawn, so a user on a thread that moved between its margin card and its seat
  lost their place (`tests/browser/threads/test_seated_threads.py`, seven cases). And
  the thread presentation has no fail-soft proof, so a failed or held thread pass
  would withhold every margin paint, Questions and ages included. A fix needs the
  continuity step to wait for the margin's paint and the margin to stop depending
  on the thread region committing.
- **The receipt took a second publication.** An accepted comment stayed in the
  ledger after the reading that logged it, until the pass drawing that reading had
  run, because held news (`thread/held-news.js`) must read the thread as the user's
  gesture through that pass. Accounting for the receipt then published again, and
  the thread region and the margin drew a third time to show nothing new. An
  accepted gesture other than an action now leaves the ledger in the publication
  that adopts the reading logging it, and the publisher keeps its thread gestured
  until it adopts a reading after a pass has drawn that one (`settled`,
  `build/browser/application.ts`), so a failed pass's retry still reads it. A later
  reading that changes nothing else then moves `gestured` and costs one thread pass
  off the critical path. An action still waits for the pass and its release,
  since a deferred widget can hold its reading past the pass, so a card move still
  publishes after its pass. Fifteen paired runs over three invocations at load
  6–10 (18 cores): applying the answer took about 54 ms of script against 62, and
  Sent fell to 164 ms (interquartile 156–169) against the merge base's 172
  (164–178), faster in ten pairs of fifteen.
- **Targets read twice.** The thread presentation reads its targets before and after
  preparation (`readTargets`, `thread/presentation.js`). The second read is not a
  copy of the first: preparation and the thread surfaces have written to the
  document since, and it measures the layout they left (about 13 ms profiled,
  mostly forced layout in `targetParts`). The first read's paint (about 5 ms) never
  reaches the screen when preparation settles before the frame, as it does here.
  Deferring that paint to the frame would drop it, but it would draw the user's own
  comment before the next frame rather than in the task that handles it, which root
  `AGENTS.md`, "Responsiveness", asks for; that trade is the user's to make.

The server's answer read, parsed and hashed every data source again (`read_data`),
most of a corpus state answer's time in process. Each source's parsed publication and
its value's revision are now kept under the file's stamp (`data._publication`), so a
corpus state answer took 4 ms against 19 in process, median of fifteen interleaved
pairs. Ten paired `bench-latency` comment runs over two invocations at load 4–8, with
this change and the receipt's single publication: the POST answered in 31 ms (interquartile 22–37)
against the merge base's 40 (29–53), and Sent read 162 (156–171) against 168
(165–178).

Fifteen of the corpus page's sample children also ask `/api/news` every 250 ms
(`LOOK_MS`, `state-feed.js`), each behind a CORS preflight. In one timed comment
those news answers took 12–40 ms each beside the event, which does not move Sent
while the main thread holds it.
