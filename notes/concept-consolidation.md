# Concepts defined more than once

A survey, taken 2026-09-26 on `16a6b88ca`, of places where one Leaf concept has
several definitions: near-copies that must change together, a caller restating
its callee's rule, or two names for one thing. Six surveys covered the browser
runtime (geometry, state, UI), the Python protocol and page layers, and packages,
CSS, tests and scripts. Every site below was read. Evidence is marked **run** (a
probe reproduced the divergence), **read** (from code), or **inferred**.

Most findings have one of two causes. The first is a half-finished cut-over: a
primitive was written for the concept and some callers never moved to it
(`landingBand` after #992, the fast registry reader after #741, `declareOccluder`
after #1028, `handBackTo` after #873, `projectCommandScope`, `thread_memberships`,
attention after #933). The second is a patch that reached one copy only (the
visual-viewport clamp in #923, the queued-debt exception in #459, new readiness
probes in #913 and #1145, eval-arm isolation in #1172). Cross-runtime twins
(Python and JS passage readings, `TEXT_BLOCK`, optimistic folds) are mostly
deliberate and pinned by parity tests; they are listed under "Leave".

## Consolidate: the copies have drifted

### 1. Whose turn a thread is

- `events.py:401` `unanswered_agent_turn` and `workflows.py:63`
  `thread_response_batch` are one rule written twice (**run**: 200,000 random
  threads, no disagreement). `work.py:141-146` inlines it a third time.
- The browser gets three readings: `awaits_agent`, `awaits_user`
  (`served_state/thread.py:147`), and `attention` (`served_state/browser.py:21`).
  `thread/model.js:133-134` reads `awaitsUser` from `attention` but `awaitsAgent`
  from the raw field, which is #933's cut-over left half done.
- **Run**: after the documented flow (reply with `responds`, then
  `leaf status working --on <thread>`), the card reads Working
  (`attention.kind = waiting`) while `awaits_agent` is false. The "Waiting on:
  Agent" filter (`thread/narrowing.js:133`) hides a thread its own card calls
  Working. No JS reads `awaits_user`.
- **Fix**: one turn predicate in `events.py`; `attention` is the only published
  turn reading; the Agent filter reads `attention`. About 8 files, 60-80 lines.

### 2. Which thread an event belongs to

- `thread_context.py:108` `event_threads` says it is the one reading of this
  relation. `read_state.py:94-99` `unread_content` and `history.py:29`
  `thread_of` derive it again, and neither counts an answering action.
- **Run**: user comment, agent reply, then the user decides the suggestion that
  answers the comment. `build_threads` resolves the thread; `unread_content`
  still reports the agent reply unread, against `read_state`'s own docstring.
- **Fix**: `unread_content` and `history.py` read `thread_memberships`. 3 files,
  about 30 lines. Decide whether an `edit` or `undo` counts as a read.

### 3. Which acknowledged debts block the agent

- `hooks.py:84-99` drops `queued` obligations and turn answers a live carrier
  will commit. `session.py:198-202` (`leaf status idle`) filters neither.
  `session-lifetime.md:69` describes them as one rule.
- **Read**: both exceptions (#459, #1080) went into `hooks.py` only. **Inferred**:
  a Codex turn that queued a batch is refused `status idle` over a move the hook
  assigns to a later turn.
- **Fix**: one `blocking_obligations(state, carried=)` in `activity.py`. 3 files,
  about 25 lines. PR #1209 edits `session.py` and `session-lifetime.md`; land
  after it.

### 4. Which gestures can be undone

- `scripts/browser/application.ts:303-336` builds a widget's `undo` with no
  revision filter (deliberately, since #666, so carried decisions stay undoable).
  `projection/commands.js:21-37` (`z`) still requires
  `event.revision === currentRevision`, the rule #450 said both shared.
- Two POST paths (`application.js:230-268`, `projection/commands.js:46-64`) and
  three "safe to undo now" guards restate each other; `widget-controller.js:121`
  `undoCandidate` repeats `application.js:231`.
- **Inferred**: a decision carried from r1 into r2 is undoable from its widget
  but not from `z`, and the server accepts it.
- **Fix**: the server's view emits the final undo list; one `withdraw(event)`
  door. About 5 files, 80 lines, net negative.

### 5. Which page a document belongs to

- `storage.js:21-27` derives `PAGE_SCOPE` by stripping `/versions/vN.html` from
  the pathname. `context.js:7`, `interaction-log.js:4` and `bootstrap.js:50` read
  the server-declared root instead.
- **Run**: `/ex/foo/` scopes to `"/ex/foo/"` and `/ex/foo/versions/v2.html` to
  `"/ex/foo"`. On a nested page (every leaf.page example) drafts and tab state
  use different keys on the live and version addresses, breaking the contract at
  `drafts.js:11-13`.
- **Fix**: derive `PAGE_SCOPE` from the declared page root. 3 files, about 20
  lines, plus a site test.

### 6. How much of the window the page shows

- `geometry.js` owns `shownRect`, occluders and `landingBand`. Six sites
  hand-write the banner or foot band instead: `key-badge-placement.js:29`,
  `margin-projection.js:617-630`, `composing/surface.js:122,179,941`,
  `reading-place.js:66`, `design.js:159,194`, `leaf.js:246`.
- **Read**: `surface.js` hard-codes `BANNER_CLEAR = 48`, the desktop banner plus
  6px. `--lf-banner-h` is 88px at ≤840px (`assets/theme.css:415`), so on a narrow
  window a target still under the banner counts as clear. `reading-place.js`
  counts lines under the foot band as on screen.
- The floating-surface room is written twice: `surface.js:172-214`
  `floatBoundary` and `margin-projection.js:613-631` `threadCardBoundary`. #923
  added the visual-viewport clamp to the composer only, so **inferred**: a
  thread card's reply editor can sit under a phone keyboard.
- Five callers rebuild `landingBand` from its top inset only
  (`navigation.js:140`, `asks/view.js:943,969`, `anchor-travel.js:184`,
  `reading-place.js`, `lf-toc.js:408`). **Inferred**: a page step leaves about
  32px per step under the banner. Worth one browser check.
- **Fix**: declare the banner and foot band once in `geometry.js` (as occluders,
  or a `pageRoom({foot})` reading); one `floatingRoom`; callers use
  `landingBand`. About 10 files, 150 lines. The `ask-thread-focus` branch edits
  `surface.js` and `margin-projection.js`.

### 7. When a page is ready to read

- The runtime's contract (`runtime/presentation.js:18-36`) says an outside reader waits
  for `pageArrived`. `tests/render_harness.py:970` waits for all six probes;
  `render_checks.py:112` omits `pageArrived` and `renderingSettled`;
  `scripts/example-previews.py:43` and `scripts/record-demo.py` wait for three
  stamps.
- **Read**: #913 and #1145 each added a probe to the test harness only.
  **Inferred**: catalog stills and the render gate can read `lf-shot` before its
  deferred comparison lands.
- **Fix**: one composite `lfReady()` on the entry script and one Python
  `wait_ready(page)`. About 6 files, 60 lines.

### 8. Whether a bundle is safe under the page CSP

- `scripts/browser/build.mjs:36-63` parses each bundle with acorn.
  `scripts/vendor.py:185-205` searches for substrings and skips Pierre, whose
  grammar data contains `import(` as text.
- **Run**: the AST check passes Pierre, so the largest bundle is unchecked only
  because of the weaker check. It refuses `webawesome.esm.js` only for importing
  `/vendor/lit.js`, which an allowed-import list fixes. License notices are also
  written twice in two formats.
- **Fix**: `vendor.py` runs every output through `build.mjs --check-module`.
  2 files, about 40 lines.

### 9. A revision's vocabulary and document

- #741 added the fast `revision_artifact.read_registry`; six callers still load
  the whole bundle through `read_artifact(...).registry` (`registry/storage.py`,
  `served_state/page.py`, `served_state/browser.py`, `source_history.py`,
  `mcp_page.py`). `registry/storage.py:16` has a second `read_registry` that
  does something else.
- `structure.parse_revision` is cached; `served_state/browser.py:291` parses the
  revision uncached on every `/api/state` (**run**: 4 ms at 43 KB, 32 ms at
  309 KB).
- A page with no revision gets the composed candidate vocabulary in one reader
  and the bare layer in three others.
- **Fix**: one owner of `revision_document` and `revision_registry`, one
  `page_vocabulary(page_dir, revision)`. About 9 files, 60 lines.

### 10. Re-addressing a document's resource references

- Capture (`revision_artifact.py:271,318`), delivery (`revision_delivery.py:39`)
  and export (`exporting.py:73`) each walk CSS tokens. `http.py:116-255` then
  regex-rescopes the delivered bytes. Head composition is written three times.
- **Run**: the walkers disagree on a nested `@import` (export inlines it) and
  none sees `image-set()`. `<a href="/media/X.png">` and `<img src>` for the same
  captured file get two different addresses in one document, and a `/media/`
  reference in a style attribute goes to a different root than one in an HTML
  attribute (`route_root` vs `_scope_routes`).
- `media.js:13-20` spells its own constant in pieces to get past the regex pass.
- **Fix, first slice**: one `css_references` walker used by all three; about
  90 lines removed. **Full**: one `rebase_document(source, address)` and an
  import map for layer JS, which deletes the regex scopers; about 400 lines.

## Consolidate: duplicated, not yet drifted

- **Focusable-row walks.** `walkRows` in `keyboard/bindings.js:559` is
  reimplemented for leaves, Asks, versions and the Page Map, and hand-clamped in
  `asks/view.js:840` and `margin-projection.js:2099`. Two drift fixes are on
  record (#124; the stale "wraps at both ends" comment at `asks/view.js:383`).
  Home/End reach only the Page Map. One `rowWalk({...})` declaration; about 6
  files, net negative.
- **Retained Lit faces.** Five classes (`asks/banner-controls.js`,
  `asks/tray-list.js`, two in `live-leaves-list.js`, `thread-list-view.js`) copy
  the same present/commit/roll-back body; two copy "focused row removed, focus a
  neighbour". One base class and one helper; about −120 lines.
- **Watching a semantic reading.** `watchAsks` (`asks/model.js:26`),
  `watchProjection`, `watchData` and `watchSemantic` differ in immediate call and
  owner lifetime, and `packages.md:594`, `projection-watch.js:3` and
  `updates.js:34` each describe behaviour the code lacks. One primitive; about 4
  files.
- **Which server view the root reads.** `browser.views[rev]` is resolved in 8+
  places; `effective.updates` is published and never read; `semantic-news.js:19`
  keys on the active revision where every other reader keys on the shown one.
  Publish `effective.view` once.
- **The page-owned URL namespace.** `schema.py:524`, `http.py:116`,
  `worker/server.py:90` and `worker/src/routing.ts:10` list it four times; both
  worker lists route a `guidance/` prefix no server has served since #380. One
  `PAGE_ROUTE_PREFIXES`, carried to the Worker through `site.json`.
- **Aria shortcuts on Ask controls.** `asks/view.js:618-689` saves and restores
  `aria-keyshortcuts` beside `keyboard/scopes.js`'s projection door; correct only
  by paint order. Make projected scopes a list per element and delete the
  save/restore.
- **Page activity facts.** `banner.js` `statusWords` and `live-leaves.js`
  `rowPresence` share the silence dating, count phrases and listening rule; #915
  edited both switches in parallel. One `activityFacts(state)`; wording stays
  per seat.
- **Eval arms and children.** `scripts/eval_claude_delivery.py` lacks the arm
  isolation `notes/arrangement-eval/harness.py` learned in #1172 (cwd outside
  the checkout, auto-memory off). **Inferred**: both delivery-eval arms load the
  candidate's `AGENTS.md`. One `evals/harness.py`.
- **Chip geometry.** `.tag` (`assets/theme.css:1206`) and `lf-chip`
  (`default/theme.css:424`) are copies edited together twice (#389, #1181);
  eight more chip-like rules drift in padding and line-height, and the runtime's
  `.lf-chip` class is a different face under the element's name. Chip tokens in
  the kernel `:root`.
- **Agent-work paint on a margin carrier.** `assets/theme.css:1843-1899` and
  `chrome.css:1618-1642` restate five rules; edited in parallel twice. One
  `:is(.lf-margin-entry, .lf-page-map-action)` rule set.
- **Page-fixture preparation.** `tests/test_interact_product.py:1685-1722`
  reimplements `scripts/page_fixtures.prepare_page` and already differs on three
  inputs.
- **Drag in progress.** Four modules read `.lf-dragging` back out of the DOM, and
  two deferral mechanisms hold work until it clears (`projection/state.js`,
  `widget-controller.js`). `widget-elements.js` should own the state.

## Free fixes

Each is under 20 lines and removes a copy.

- `projection/model.js:8` copies `COLLAPSE` from `passages.js`; no parity test
  covers the copy. Move it to a module both closures may import.
- `state-application.js:66` `stale()` restates `adoptable()`'s first clause in
  `application.ts:721`.
- `vendoring.py:101-117` restates `registry/storage.layer_metadata`'s packages
  rule with a different message (PR #1209 edits `vendoring.py`).
- `render_gate/scheme.py:341` and `page_code.py:76` count `{action, report}` for
  the stamp the runtime counts from coverage records, which include undo. Read
  `coverage` from the state already held.
- `render-checks/widgets.js:110-122` rewrites `anchor-resolution.js:131`'s
  visual-part admission rule; export `visualPartAdmits`.
- `lf-column` restates the `$tones` enum instead of declaring `x-tone`.
- `chrome.css:572-573` writes the focus ring out in full, outside the ring scan
  (`TODO.md` tracks the general ring pass).
- `composing/capture.js:61` accepts generated `lf-*` ids as a passage's section;
  `anchor-resolution.js:221` `isAddressable` excludes them, and `design.js:230`
  records the same bug fixed for design comments. Use `isAddressable`
  (**inferred**; check by selecting text inside a diagram).
- `reading-place.js:59` misses `blockAt`'s Markdown-island rule (#993), so option
  prose never serves as a reading landmark.
- `presence.py:43` and `served_state/reading.py:70` stamp the page directory with
  different exclusions; #1182 patched both.
- `thread/replies.js:61,90` and `thread/landing.js:137-191` restate
  `thread/selectors.js` and `thread/focus.js` (`ask-thread-focus` edits both).
- Docstrings and comments cite code that no longer exists: `events.py:192`, `build_threads`,
  `seats_with_agent`, `spoken_turns`, `passages.py:603`,
  `media.js:13` (`_ROOTED_PAGE_ROUTE`).

## Worth it, but large

- **The unresolved-gesture ledger** (`application.ts:992-1041`,
  `application.js:90-98,243-250,473-486`, `pending/model.js`): one state machine
  spread over five flags, with the `kind === "action"` exit written four times.
  One `phase` per entry. No drift found; it sits on the hottest race path.
- **`page state` rebuilds `full_state`** (`agent_state.py`): three thread folds
  per call and every thread reading computed twice. Select from the served
  reading, as presence already does. About 150 lines; no user-visible bug.
- **Returning focus when a layer closes**: five closers with different
  fallbacks, three Tab-stop selectors (`reach.js:62` `FOCUSABLE` misses
  `summary`, which thread cards are). Generalise `handBackTo` into `focus.js`.
  The `markdown-composer` branch edits `focus.js` and `reach.js`.

## Marginal

Real, but nothing has drifted and the concept is small: the `followsTail` rule
for the thread panel and margin card; the clip walk in `margin-layout.js`;
"does this box scroll" predicates; the request-seat availability overlay (settle
`TODO.md`'s "whether requests earn their weight" first); draft-record liveness in
`drafts.js`; the pending-id name and `namedParent`/`localParent`; the state
coordinate key; workflow stage ranking in two JS inline copies; `pending` meaning
two counts in one `page state`; per-kind event facts split between `$events` and
`schema.py`; the page-is-initialized test in eight places; the active-document
descriptor; page-layout name literals (`interactions.jsonl` is missing from
`PAGE_STATE_FILES`); example source sets across five scripts; elapsed-time wording
(`presence.js` says "2h ago" where `lf-command` says "1h"; the
`codex/thread-attention-ontology` branch edits `presence.js`); lending a tab stop;
the arrival-pulse duration.

## Leave

- Python and JS passage readings, `TEXT_BLOCK`, `COLLAPSE_CHARS`, inline
  Markdown: file-side anchoring runs without a browser, and parity tests hold
  the lists equal.
- Optimistic folds (`foldedValue`, `pendingSeat`, `foldThreads`) mirroring
  Python: they paint before the server answers.
- `rendering.js`, `presentation.ts` and `repaint.js`: three layers, not copies.
- `reading-place.js` vs `user-place.js`; `margin-entries.js` vs
  `margin-entry-model.js`; `anchor-paint.js` vs `target-paint.js`: documented
  splits.
- Command reference vs Page Map Escape targets: deliberate per
  `keyboard/AGENTS.md`.
- Export CSP vs `PAGE_CSP`; `render-checks/open-roots.js` vs `shadowRootsIn`;
  `now_iso` in seconds and milliseconds: different on purpose.
