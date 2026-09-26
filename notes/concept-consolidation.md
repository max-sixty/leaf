# Concepts defined more than once

A survey on 2026-09-26 found concepts Leaf defines in several places: near-copies
that must change together, callers restating a callee's rule, or two names for one
thing. Most came from a primitive whose callers were never all moved to it, or a
fix that reached one copy. PRs #1214–#1221, #1223, #1228, #1231 and #1235 gave
the drifted ones a single owner. This note keeps what is left.

## Waiting on the markdown-composer branch

Each fix touches files that branch changes; take it once the branch lands or is
abandoned.

- **How much of the window the page shows.** `geometry.js` owns occluders and
  `landingBand`, but the banner and foot band are hand-written at
  `keyboard/key-badge-placement.js` (`chromeTop`), `margin-projection.js`
  (`threadCardBoundary`), `composing/surface.js` (`BANNER_CLEAR = 48`, which is
  short of the 88px narrow banner), `reading-place.js`, `design.js` and
  `leaf.js`. Declare the banner and foot band once. The composer's
  `floatBoundary` and the thread card's `threadCardBoundary` are one rule written
  twice; only the composer clamps to the visual viewport (#923), so a thread
  card's reply editor can sit under a phone keyboard (inferred).
- **When a page is ready to read.** `tests/render_harness.py`, `render_checks.py`,
  `scripts/example-previews.py` and `scripts/record-demo.py` wait on different
  subsets of the runtime's readiness probes; #913 and #1145 reached the harness
  only. One composite probe, one Python wait. `record-demo.py` also still counts
  actions only, where the gate now counts served coverage (#1235).
- **Whether a bundle is safe under the page CSP.** `scripts/vendor.py` uses a
  substring check that skips Pierre; `scripts/browser/build.mjs` parses bundles
  and passes it. Route every output through the parser and write license notices
  once.
- **Whether a drag is in progress.** Four modules read `.lf-dragging` back from
  the DOM and two deferral mechanisms wait on it (`projection/state.js`,
  `widget-controller.js`). `widget-elements.js` should own the state.
- **Returning focus when a layer closes.** Five closers use different fallbacks;
  `reach.js` `FOCUSABLE`, `command-reference.js` and `margin-layout.js` define
  Tab stops three ways, and `FOCUSABLE` misses `summary`. Generalise `handBackTo`
  into `focus.js`.
- **Thread identity in the runtime.** The served state gives each thread an `id`
  (#1235), but `scripts/browser/application.ts` and `thread/*` still key on the
  first message's id, so a thread whose first log line was torn reads as nobody's
  turn in the panel. `thread/replies.js` and `thread/landing.js` also restate
  `thread/selectors.js` and `thread/focus.js`.
- **Remaining single sites.** The Page Map walk (`margin-projection.js`) is off
  the shared `rowWalk`; `interaction-log.js` reads the page root itself instead
  of `storage.js` `PAGE_ROOT`; `lf-command.js` words elapsed time differently from
  `presence.js` (at 90 minutes, "1h" beside "2h ago"); two comments in
  `tests/test_render_threads.py` still name `awaits_user`.

## Waiting on the layout-survey branch

- **Chip geometry.** `.tag` (`assets/theme.css`) and `lf-chip`
  (`packages/default/theme.css`) are copies edited together twice; eight more
  chip-like rules drift in padding and line-height, and the runtime's `.lf-chip`
  class is a different face under the element's name. Chip tokens in the kernel
  `:root`.
- **Agent-work paint on a margin carrier.** `assets/theme.css` and `chrome.css`
  restate the same five rules for margin entries and Page Map actions.
- **The focus ring.** `chrome.css` writes one ring out in full, outside the ring
  scan; `TODO.md`'s ring pass covers the rest.

## Not started

- **The unresolved-gesture ledger** (`application.ts` `accept` and
  `accountPresented`, `application.js` `releasableEntries`, `pending/model.js`):
  one state machine over five flags, with the action-kind exit written four
  times. Nothing has drifted and it sits on the hottest race path, so it waits
  for a change that has to touch it anyway.
- **Re-addressing resource references, beyond CSS.** Capture, delivery and export
  share one CSS walker (#1217), but `http.py` still regex-rescopes delivered bytes,
  `media.js` spells its constant in pieces to get past that pass, and head
  composition is written three times. One `rebase_document(source, address)` and
  an import map for layer JS would delete the regex scopers; about 400 lines.
- **Request seat availability** is restated in `application.ts`,
  `widget-controller.js`, `application.js` and `request-elements.js`; settle
  `TODO.md`'s "Decide whether requests earn their weight" first.
- **Small and undrifted:** the tail-follow rule in the thread panel and margin
  card; the clip walk in `margin-layout.js`; "does this box scroll" predicates;
  draft-record liveness in `drafts.js`; pending-id naming; the state coordinate
  key; workflow stage ranking copied inline in `margin-projection.js` and
  `margin-entries.js`; `pending` meaning two counts in `page state`; per-kind
  event facts split between `$events` and `schema.py`; the page-is-initialized
  test in eight places; the active-document descriptor; example source sets
  across five scripts; lending a tab stop; the arrival-pulse duration.

## Leave

Python and JS passage readings, `TEXT_BLOCK` and inline Markdown (file-side
anchoring runs without a browser, and parity tests hold them equal); optimistic
folds that mirror Python (they paint before the server answers); the render loop,
epoch claims and repaint phases (three layers); the command reference and Page Map
Escape targets (deliberate per `keyboard/AGENTS.md`); export CSP and `PAGE_CSP`.
