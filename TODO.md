# TODO

- (2026-08-14) Left on the table by the framework-robustness sweep (its session
  holds the evidence; the landed half is in that branch's history):

  - (done 2026-08-15) `x-retired-when` is open in the licensing too:
    `retirement_slots` reads the holder/slot pair the declaration relates,
    `retirable_ids` is written in its terms, and the door that refused the key
    outside the suggestion family is gone. What the pair could not say —
    what an unanswered widget means when the author takes it back — is the
    holder's own declaration now (`x-withdrawn-as`).
  - (done 2026-08-15) `applyAction` absoluteness is checked: the render gate
    applies each standing action a second time and reports what moved
    (`RELATIVE_REPLAYS`). Not the candidate check — replaying the log twice is
    a no-op by construction (every action carries its seq and replay retires
    each exactly once), and `shallowSigs` alone is blind to a `body` record, so
    the unit's declared record form is read beside it. What it cannot reach is
    a verb no user has exercised yet: the corpus's own logs carry no actions, so
    `test_example_renders` never applies anything and the coverage is a page
    of its own.
  - (done 2026-08-15) The render gate reads two module contracts a static lint
    can't: an `x-verbatim` widget whose rendered words differ from the file's,
    and a shadow root on a host whose entry lacks `x-shadow`.
  - (done 2026-08-15) Every page declares the layer's one CSP and `version
    check` requires it, so "a vendored page can't phone home" is the browser's
    to enforce.
  - Residue of the retraction-floor fix in thread settlement (landed: an accept a
    later version `restated` no longer resolves its thread forever, via one
    predicate — `action_retracted` / `retractedIds` — shared by the fold, the
    rewrite gate, replay and the thread builders on both sides). One of the three
    things it deliberately did not settle is still open: a `reject` recorded after
    an `accept` on the same suggestion leaves the thread resolved, and un-resolving
    that case means folding by unit, a separate decision. (The other two are done:
    the panel's window against replay's, 2026-08-15 — the two answer different
    questions, and the rule is one section of the skill's CLAUDE.md, "A pinned
    version scopes the document, never the conversation", since it binds
    `buildThreads` and `applyActions` alike and neither site owns it; and
    `build_threads`'s defaulted `spk`, 2026-08-14 — required, `{}` explicit for
    the no-page callers.)
  - (done 2026-08-14) The collapse class is one set now: `COLLAPSE_CHARS` /
    `collapse()` beside `TEXT_BLOCK_TAGS`, leaf.js's `COLLAPSE` its twin, a test
    pinning the two spellings to each other by expanding the JS class over the BMP.
  - (done 2026-08-14) `resolves` is a reserved detail field: `$state` says what it
    means and `validate_registry` holds any verb spelling the name to a plain
    string.
  - (done 2026-08-14) The block-slot rule inverts the platform's phrasing set
    instead of enumerating widgets — any layer's block widget is covered unnamed —
    with the registry's `x-inline` tags as the one declared residue, pinned by test
    (lf-compare's stacked-variant trigger shares the list and the pin).
  - (done 2026-08-14) `_PassageParser.close()` unwinds the stack at EOF.
  - (done 2026-08-18) `bin/leaf` recorded `$PPID` as the Codex process, and it is
    that process for some command shapes and a shell of the moment for others.
    Measured against codex-cli 0.147.0, which runs each shell tool call as
    `/bin/zsh -lc '…'`: a bare command, a `cd … && …` chain and a `bash -lc "…"`
    all reported the codex process, the wrapping shell having exec'd the command
    in place, while `leaf … | cat` reported the wrapping shell itself — a pipeline
    is what stops that exec. So the pid was right by accident and wrong by
    accident, and the wrong one exits with the command: the sweep in `claim_page`
    drops a live session's entry, `stop_when_session_ends` takes the page's server
    down `ORPHAN_GRACE_SECS` after the command that started it, and the banner
    tells the reader no session holds the page while the session sits there
    working. A launcher can't know it, so the launcher no longer states it:
    `session_pid` reads `CLAUDE_PID` for Claude Code (measured to be the session
    process, where that shell's `$PPID` is an ephemeral `zsh`) and walks to the
    nearest ancestor running `codex` otherwise, failing loudly where none is —
    that environment is hand-built, and a guessed pid is a claim that expires on
    its own. The walk is libproc on macOS and `/proc` on Linux rather than `ps`,
    which is the one door that looks portable and is refused (`/bin/ps: Operation
    not permitted`, setuid root) inside exactly the seatbelt sandbox Codex runs
    its shell tool under. All of it read off one `codex exec`, the last of its
    five commands being the real shim claiming a page through a pipeline: the
    shell it ran under was pid 93641 and the claim recorded 87087, the codex
    process itself.
  - (done 2026-08-15) lf-options wrote `answered` and `open` onto the group in the
    author's namespace, which its entry closes. Neither was state to declare: the
    `answer` verb is a thread's, and no version can carry a thread's markup to honor a
    record of it, while open-or-closed is this tab's reading position. Both were second
    copies of what the module already says on the control that carries them, so each is
    now said once (`aria-pressed`, `aria-expanded`) and the theme keys on that.
    `version check --render` asks the rendered page for the rest
    (`UNDECLARED_ATTRS`) — the second writer shows on no other side. (The orphaned Done
    press under a settled collapse: done 2026-08-14 — it hides with the options.)
  - (done 2026-08-15 — measured, no change) The last unmeasured hot path was
    `openAsks()` rebuilding `stateFold`, and the count it was flagged for holds: four
    folds a poll — the banner's, the key line's `a` and its `Shift+a`, and
    `paintPending`'s — and two per key-line paint. Nobody had asked what a fold costs.
    Timed in Chrome on `examples/gallery.html`, served from a page directory with its
    vendored `leaf.js` wrapped in a timer, each fold read off a tight loop because
    `performance.now()`'s 100µs clamp is wider than the thing measured: 0.4µs over a
    fresh page's log, 62µs after eight decisions and twenty comments, 137µs with three
    hundred comments over those same eight. So the three redundant folds cost
    0.19–0.41ms of a two-second poll, and the key line's second fold 62–137µs of a
    16.7ms frame; a sixfold CPU throttle multiplies both by about six. The page
    directories on this machine hold one to eleven events. Memoizing it the way
    `retractionFloors` is would be wrong rather than merely unnecessary: `foldable`
    reads the DOM (`elementById`, `inChrome`) and `retractedIds` asks containment, so
    a version switch changes the answer with `events` still the same array. The code
    stands as it is.

    A fold does cost at hundreds of *actions* (300: 2.1ms a fold, 13ms a poll), and it
    is still not the thing to point at. That page spends 1.1s of its load in replay:
    `lf-options` and `lf-suggestion` dispatch `lf-answered` from the absolute setter
    that replay itself calls, and each dispatch runs a whole `paintAnchors` (600ms over
    the batch) and `syncAsks` (450ms, of which the folds are 420ms). The batch already
    does both — `applyActions` ends on `paintAnchors` when it applied anything, and
    `lf-actions` fires `syncAsks` the moment it returns — so every per-answer pass is
    superseded a few milliseconds later. That makes it redundant work rather than work
    to coalesce, and the shape at fault is a widget announcing a reader's answer from
    the path that replays one. Nothing is owed until a page carries such a log; a fold
    memo would take out the smaller half of it in any case.

    A second measurement, taken independently on ship-review with a synthetic board
    log, agreed: seven calls across the load and six per two polls, 1.1ms at 200
    actions and 4.0ms at 1000, linear in the log.

    (The other two are done 2026-08-15: `retiredSlots` is computed once for the load,
    and `retractionFloors` memoizes on the log's identity, which is what
    `buildThreads` walked per call.)

- (done 2026-08-18 — verified, changed) lf-compare's terse variants keep the auto-fit
  grid the options gave up, and with it the geometry the options were complained about:
  equal-height cells and an orphaned last row once a group holds more than the columns
  take. It stayed by argument — an exhibition is looked across, and shipped compares are
  pairs — not because the failure was verified unreachable, so the day a page holds four
  terse variants, this is that report. The page was built: groups of four, five and seven
  terse variants and one of three unequal lengths, served and read in both palettes at
  the suite's width and at 460px. Half of it reads wrong.

  The stretch does. Out of 720px of column a one-sentence variant beside a six-line one
  came out 278px tall with 190 of that blank under a single line, which reads as a card
  whose words never arrived — and a group's geometry moved with content that was not in
  it. `align-items: start` is the whole fix, and a cell is the height of what it holds
  now.

  The trailing room does not. Four come out three across with the fourth under them, and
  that fourth is a card the size of its peers on a row with space left rather than the
  demoted case the option's orphan was. Both ways of closing it pay in cell width: a
  wrapped flex line grows whatever lands on the last line, and measured worse than that
  here — two per row, the basis being content-box against a padded card — while a column
  count read off the child count is a different width per count. An exhibition is read
  down its columns as much as across its rows, so the room stays.
  `test_a_terse_variant_is_the_height_of_its_own_words` measures the two readings against
  each other. Narrow, a group is one column and none of it arises.

- (2026-07-30) The g chord names a list and then a place in it, and the lists it
  can name are core's own table. If it ever grows a widget's parts — a board's
  grips, a draft's ✎ — the registry should declare the address (an `x-` key the
  chord dispatches on) rather than modules registering keys, per the never-closed
  widget list. No pressure for it yet: a group's options answer to bare digits
  under focus, which is where the demand came from.

- (2026-07-30) A widget can't own a conversation — the page half. In a thread the
  question and its words are one thread now, but a page group's box for words still
  posts a comment only the panel shows: the answer to a question the page asked
  reads as a remark *about* the widget rather than as the thing it asked for, and
  the box that asked shows nothing of what was said in it. What closing it properly
  has to answer: that a thread rendered inside a widget is a second *view* of one
  thread and never a second store, since two stores is the bug this codebase keeps
  not having; what the panel shows for an owned thread, because a reader scanning
  comments should still find every word they wrote; how ownership is declared,
  which has to be a registry key rather than a tag any consumer names, so the
  twelfth widget can claim a conversation without core hearing of it; and whether
  ownership is a property of the anchor or of the widget, which decides what
  happens to the thread when a later version drops the element it was anchored on.
  Reported again 2026-08-17 from the reader's side: what is typed into the box goes
  to the panel and nothing on the widget points back at it, so it can feel like it
  went into the ether. One shape raised then — no box on the widget at all, and
  ⌥-click on the item as the one way to say something about it, which opens the
  composer where the words will be anchored.

- (done 2026-08-18) An unsent draft died with the tab, which is the ordinary end of a
  tab here rather than a rare one. Drafts are the reader's now (`draftStore`,
  localStorage under `PAGE_SCOPE`; `tabStore` keeps the reading position and the
  widgets' working state), and every tab renders one copy: `watchDraft` routes the
  store's own `storage` event to the box on that context. The index the item priced is
  the document's listener list rather than a store of our own, so a box out of the
  document drops its view and nothing has to be held in step with the panel.

  The channel is not there. Once an emptied box stores `""` and only a settlement
  removes the key, `newValue` tells an edit from a send-or-Cancel by itself — and
  *which* settlement it was is a question nothing asks, both leaving the same box to
  render and the log carrying what was sent. That rule also retires lf-draft's JSON
  wrapper, which existed to keep an empty edit distinct from absence. What a settlement
  does is the box's own — a reply or general box empties, the composer on that anchor
  closes, a draft editor closes so replay can paint the body — while a mirrored edit
  opens nothing that was not already open. The composer's key is its anchor, since one
  key shared across tabs is two passages overwriting each other; its record carries the
  anchor, the mode and a touch time, which is what the load reopens the most recent of.

  The alternative that stays unbuilt: the server is where Slack keeps drafts and the one
  place these cannot go, since here the server is the agent and an unsent draft would be
  words the user has not decided to say, sitting where the next `leaf wait` can read
  them.

- (done 2026-08-18) A changed line in `lf-diff` marks the words that moved. Within a
  change block the i-th deletion answers the i-th addition, leftovers unmarked; the marks
  are spans nested inside the token spans, `::highlight()` reaching no shadow tree. What
  ends a block and why each mark is built where it is are `movedInFile` and `bodyNodes`.

  Nothing was vendored. `alignText` was already the layer's alignment, and the gate it
  needed was lf-suggestion's, written inline there — `movedWords` in leaf.js is that gate
  lifted out, and both widgets read it. The marks are ruled underneath rather than
  deepened the way a suggestion's are, because a diff line's tint has already spent the
  contrast the render gate holds code to; `bundled/theme.css` carries the measurement.

  The pairing came out of measuring `@pierre/diffs` rather than adopting it. Pierre divides at
  Shiki. Its diff model — parsing, hunks, patches, accept/reject, conflict detection —
  is 34 KB and never touches a highlighter, but it does what `parseDiff` already does
  here. The renderer is what carries split view, and it reaches its highlighter through
  a module-level singleton with no injection point on the component, so taking it means
  Shiki's engine and a TextMate grammar per language: about 1.25 MB in every page
  directory, against the 75 KB `highlight.esm.js` spends on the same fifteen. Split
  view is the only feature on the far side of that, and it would pull `lf-code` and the
  plain `<pre><code>` path onto Shiki with it.

- (2026-08-08) The tab wears one bubble in one colour, which is enough to pick a page
  out of a row of tabs and is the whole of it. Two things it is not. It carries no
  count, where the banner's `Asks (n)` already has one from `x-awaits`, so a reader who
  wants to know how much is waiting still has to open the page — and whether a 16px
  square can say a number, or show anything but a still image, is a measurement nobody
  has made, because no automated browser can see its own tab strip. And the mark is
  themed only in its status: `icon.svg` spells out paper, ink and the marked line as
  literals, since a favicon cannot link a stylesheet, so a project that overrides
  `--paper` gets a tab still drawn in leaf's.

  The second is the one with a shape already. The runtime writes one declaration into
  the mark on every paint — `.lf-tone { fill: … }`, from the dot's own colour — so the
  fix is to write the theme's tokens in beside it and let a mark read them with `var()`.
  That turns the contract from "keep this class" into "these tokens reach you", which is
  the difference between a mark that must be built around one hardcoded property and one
  that can take its status on a stroke, a gradient stop, or nothing at all. Worth doing
  the first time someone themes a page and notices the tab didn't follow.

- (2026-08-17) Escape in a text box, as reported: the key line shows Escape as closing
  the comments while a reply box has focus, and the press both leaves the box and closes
  the panel. Two norms say otherwise — the line promises one press, and the typing
  scope's own Escape row ("back to thread") should shadow the panel's, since a nearer
  scope naming a binding hides the outer row. Reproduce it first, in the box it was seen
  in; expected: Escape leaves the box and does nothing else, and the line says so. Not
  reproduced (2026-08-17, main d4cb071, the ui-sweep): driven in a thread's reply box
  and the general box, both palettes — the line offered esc as "back to thread" while
  typing, and one press left the box with the panel open, the draft intact, and focus
  on the thread. Stands until it is seen again, with the page and the box it was seen
  in.

- (2026-08-17) A thread's Reply and Resolve controls don't look elegant. Walked
  (2026-08-17, the ui-sweep, both palettes) with a reply box open; what specifically
  reads wrong, before changing anything: the send button says "Reply" and stands beside
  the box at all times, so an idle thread shows the word twice in two roles — the
  field's own placeholder ("Reply · g 2") and a disabled button beside it; the button
  rides the bottom edge of a box that grows (the row aligns flex-end), so a grown
  draft leaves it hanging under a strip of empty row; and "✓ Resolve" — borderless,
  check-first, right-aligned on a row of its
  own under every thread — reads as a status rather than an action, in a different
  visual language from the bordered Reply above it. A redesign is constrained by the
  hold-still norm (a control may not appear on focus and move the row), so the shape
  wants deciding rather than patching.

- (2026-08-17) A design comment whose fix belongs in leaf's shipped layer, made from a
  session outside a leaf checkout. Design mode is for the reader's own layers — a
  project's `.leaf/`, a user's `~/.config/leaf/` — and a change to leaf itself is
  secondary, asked for in the comment's words. When it is asked for, the round trip is
  long: the session's launcher decides which layer `page init` vendors from (a
  checkout's for a session in a leaf worktree, the plugin cache's elsewhere), so a fix
  landed on main reaches an open page after a push, from the next session, on a
  re-vendor. Today the comment is handed to a leaf session by hand (`/dispatch`, with
  the target and the page). What would shorten it is unmeasured: the dispatch carrying
  the comment's anchor and the page's URL so the leaf session can look at what the
  reader saw; a served page re-vendored from a checkout the session names, so a fix is
  seen before it lands. Neither is worth building before the second time it is asked.

- (2026-08-17) Left out of design mode's build, each with the day it becomes worth
  building:

  - A screenshot in a design comment. The agent can render the page with the log
    replayed, so a crop is a command it runs rather than bytes the reader sends. Worth
    adding once a design comment has been misread for want of one.
  - A stamped widget tag on comment events. The tag is one join from the version file,
    the join `action_widget_tags` already makes for actions, so stamping it buys
    nothing until a consumer reads the log without a page in hand.
  - An inventory in the panel — the legend as a list, each row jumping to its item.
    The boxes on the page are that list; a row earns its place on a page long enough
    that finding an item means scrolling for it.
