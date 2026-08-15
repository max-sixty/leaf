# TODO

- (2026-08-14) Left on the table by the framework-robustness sweep (its session
  holds the evidence; the landed half is in that branch's history):

  - `x-retired-when` is declared open but the id-survival licensing
    (`retirable_ids`) still reads the suggestion's own slot bookkeeping, so the
    registry door now refuses the key outside the suggestion family rather than
    letting a third-party slot fail three versions in. The generalization is to
    record holder/slot structure for any tag pair the declaration relates and
    write the licensing in its terms.
  - `applyAction` absoluteness — the contract every fold rests on — is never
    checked; a relative implementation passes every gate. The candidate check:
    the render gate replays a version twice and asserts the second pass's
    `shallowSigs` diff is empty.
  - (done 2026-08-15) The render gate reads two module contracts a static lint
    can't: an `x-verbatim` widget whose rendered words differ from the file's,
    and a shadow root on a host whose entry lacks `x-shadow`.
  - (done 2026-08-15) Every page declares the layer's one CSP and `version
    check` requires it, so "a vendored page can't phone home" is the browser's
    to enforce.
  - Residue of the retraction-floor fix in thread settlement (landed: an accept a
    later version `restated` no longer resolves its thread forever, via one
    predicate — `action_retracted` / `retractedIds` — shared by the fold, the
    rewrite gate, replay and the thread builders on both sides). Three things it
    deliberately did not settle: a `reject` recorded after an `accept` on the same
    suggestion still leaves the thread resolved — un-resolving that case means
    folding by unit, a separate decision; the panel is now not version-scoped while
    replay still is, so a reader pinned to an older version correctly sees a thread
    reopened by a later retraction beside a suggestion still painted accepted, and
    no prose yet says both readings answer different questions. (The other two —
    `build_threads`'s defaulted `spk`, done 2026-08-14: required, `{}` explicit for
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
  - `bin/leaf` records `$PPID` as the long-lived Codex process; if Codex execs the
    shim through an intermediate shell, that PID dies with the command and
    `claim_page`'s stale-session sweep deletes a live session's entry. Needs a real
    Codex invocation to settle.
  - lf-options writes `answered` and `open` onto page markup undeclared — real widget
    state `x-state.answer` records nowhere, so it lands in `shallowSigs` and nothing
    outside the module knows it exists. Either a `record` form or the paint
    vocabulary — note before picking: `shallowSigs`' comment shows widget `data-lf-*`
    state is deliberately visible to the signature (lf-suggestion's `data-lf-state`
    rides it), so a paint rename must not blanket the namespace. (The orphaned Done
    press under a settled collapse: done 2026-08-14 — it hides with the options.)
  - One unmeasured hot path left, flagged where to point the measurement, per the
    rule that no cost claim ships unmeasured: `openAsks()` rebuilds `stateFold`
    two to four times per key-line paint and per poll. (The other two are done
    2026-08-15: `retiredSlots` is computed once for the load, and
    `retractionFloors` memoizes on the log's identity, which is what
    `buildThreads` walked per call.)

- (2026-08-08) lf-compare's terse variants keep the auto-fit grid the options gave up,
  and with it the geometry the options were complained about: equal-height cells and an
  orphaned last row once a group holds more than the columns take. It stayed by
  argument — an exhibition is looked across, and shipped compares are pairs — not
  because the failure was verified unreachable, so the day a page holds four terse
  variants, this is that report.

- (2026-07-30) The g leader shipped with digits only (`g 1` reaches the nth open
  thread's reply box) and the namespace open. Settle its shape before growing it:
  should the sequence carry a verb (`g r 1`, leaving `g` room for other nouns), or
  stay flat? Bare `r` resolves the focused thread now, so a verb vocabulary should
  keep the bare keys' meanings — `g r 1` reading "reply" would give one letter two
  verbs. A group's options answer to bare digits under focus now (`a` lands there),
  which relieves the pressure for widget addresses; if the leader still grows them —
  a board's grips, a draft's ✎ — the registry should declare the address (an `x-`
  key the leader dispatches on), not modules registering keys, per the never-closed
  widget list.

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

- (2026-07-31) An unsent draft dies with the tab. sessionStorage carries one through a
  reload, a version navigation, and a server restart — the port is derived from the page
  directory, so a re-serve lands on the same origin — and a closed tab is the one case
  it doesn't cover. That is the ordinary case here rather than a rare one: each round's
  reply hands the URL over again and the user opens the page from the turn in front
  of them, so a page's tabs accumulate. Swapping the store for localStorage trades the
  gap for a worse failure, since one store shared across those tabs means a send or a
  Cancel in an old tab clears text being typed in the new one. The build that avoids
  both is localStorage for durability plus a channel (`BroadcastChannel`) that says what
  happened, so every tab renders one copy and a cleared draft arrives as "sent" rather
  than as words going missing — a value diff cannot tell those apart. What it costs is
  an index from a draft's context to the box showing it, which nothing needs today: each
  box closes over its own context where it is built, and the reconciled panel keeps
  that box for its thread's life, so the index would be one more store to hold in step
  with the list. The server is where Slack keeps drafts and the one place
  these cannot go: here the server is the agent, and an unsent draft would be words the
  user has not decided to say, sitting where the next `leaf wait` can read them.

- (2026-08-07) A changed line in `lf-diff` says only that the line changed. (The
  suggestion half of this landed 2026-08-14: lf-suggestion's slots deepen the words
  that moved, through `alignText` and the highlight registry — no vendoring, cleared
  on decide, gated on shared ink so a swap paints nothing. `alignText` may make the
  jsdiff vendoring below unnecessary for the diff too; ::highlight cannot reach the
  diff's shadow tree, so its emphasis would be module-built spans instead.) jsdiff's
  `diffWordsWithSpace` narrows it to the words that moved, and bundles to 6 KB on its
  own, vendored beside the tokenizer the way `highlight.esm.js` already is. Pairing is
  what has to be settled first: a word-level mark compares one deletion against one
  addition, and a hunk offers a block of each, so something has to say which line
  answers which. Pierre walks the change block and pairs a deletion row with the
  addition row opposite it. The spans can be built in the pass that already colours
  each side, and they nest inside the token spans the way `synNodes` nests now, so no
  text moves and neither reading changes.

  This came out of measuring `@pierre/diffs` rather than adopting it. Pierre divides at
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
