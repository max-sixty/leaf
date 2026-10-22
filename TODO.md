# TODO

## Biggest current challenges

- **Improve our outputs against a standard HTML output.** The
  [recovered comparison](notes/agent-usability-evals.md#recovered-codex-comparison-2026-10-14)
  measures complete authoring and feedback cycles on saved Leaf and HTML pages.
  Use task-specific evidence to decide which compositions help, and measure current
  authoring time before adding more widgets or instructions.
- **Simplify the harness, host, and CLI workflow.** Make feedback delivery and
  agent wake-up reliable, including Codex's message back into the session and
  Claude Code's potentially overcomplicated state machine.
- **Make tasks and work in progress clear.** Find a robust state model that
  users can understand: what is running, waiting, blocked, or complete, and
  whose next move it is.
- **Keep authored pages flexible.** Find the useful middle ground between
  unrestricted HTML and brittle templates, especially for workspaces.
- **Make page-level Threads easy to create and use.** Give users a clear way
  to start, find, and continue conversations about the whole page.
- **Build coherent UI without repeated patches.** Improve the layout and
  interaction mechanisms so each new case does not require another fix.
- **Reduce the burden of tests.** Tests now take long enough to meaningfully
  slow development. Reduce their runtime and the work needed to run them while
  preserving useful coverage. `notes/shift-watch-cost.md` records what the
  Stability sensor costs and when a cheaper gate would be worth revisiting.
  Sharing one page across a test's cases (`tests/AGENTS.md`, "One page for the
  cases that can share it") reaches only cases that leave the log and the page's
  own UI alone, so most of the time spent opening pages needs each opening to
  cost less.

Priority runs from **Now** to **Next** to **Etc**. Themes group related work within
each priority; bullets are outcomes, not implementation plans. Linked notes hold the
evidence and detailed briefs. A `#N` id names one item across this file and `notes/`;
a new item takes a number neither uses.
Completed work and rejected ideas live in git history or the relevant research note.
An item marked **Unconfirmed** rests on a reading nobody has run or a design nobody
has tried; settle that before building it.

## Now

### User experience

- **#25 — Answer one decision beside its evidence and on a board.** A section's
  picker and its board card currently record independent facts. The section's widget
  owns the answer; build the board's write to that owner and test both views against
  one decision, including ordering, write-ins and revision retraction
  ([design](notes/shared-decisions.md)).
- **Make complete reading journeys feel coherent.** Audit a document, workspace,
  board or table, and populated thread in light and dark at wide and narrow
  widths. Fix recurring gaps in type, spacing, framing, controls, and responsive
  behavior.
- **Keep the Thread hierarchy clear.** Check context, search, filters, agent
  activity, selection, and reply editing in the floating panel's Threads view.
- **Keep a long Thread's current status visible.** Summary checkpoints already condense
  older messages. Test a current one-line reading of what is decided and what remains
  open, distinct from a historical summary, and decide how a revision invalidates it.
  See the [Thread plan](notes/threads.md#current-status).
- **Test annotation placement in context.** Compare a pinned marker card with a
  sparse left-comment layout on a document and a workspace. Keep full history and
  search in Threads and use Page Map on narrow pages; show only one margin treatment
  at a time.
- **Make the next move and its result apparent.** Play through `review-a-plan`,
  `triage-board`, `pr-walkthrough`, and `ship-review`; fix dead ends and moves whose
  result is hidden. Decide whether a page needs one progress reading across On me,
  board work, and version approval. Test a concrete first task before changing the
  public home page's prompt.
- **#28 — Finish the floating panel.** The floating panel, rebuilt on 12 October to
  the sketch the user configured (the header of
  `skills/leaf/assets/runtime/floating-panel.js` holds its contract), is Leaf's only
  chrome since 16 October, when the banner, the bottom bar and the switch between them
  went. Every follow-up the user named has landed, so the item waits on the user's
  review of the desktop design. The phone waits until the desktop design is firm, and
  where a passage thread opens from Threads waits until later.
- **Say when a held-news notice holds more than it shows.** A notice in a seat's
  head row keeps the width of the news it first said (`data-lf-room`) and shows each
  fact whole or not at all (`newsNotice`), so "1 new reply" with a message arriving
  after it still reads "1 new reply", with nothing on screen saying more waits; the
  title that names every fact doesn't reach touch. A count growing past that room
  ("1 new reply", then "2 new replies") still cuts at its end ("2 new repl…"). The
  notice stands absolutely over the free head row, so its room could be the whole
  slot up to the visible end (`thread-card.js`, `#retainHeaderSlot`), if a notice
  wider than its words under the pointer is acceptable; a "+1" for dropped facts is
  the other route. In a margin card the notice takes its width from the heads'
  track, and a wide one moved the head's time sideways in CI (PR #3250's first run).
- **Stop moving live content between parents.** A thread summary hides the messages
  it covers in place, so a frame keeps its document and a selection stays.
  Four places still move live nodes, which reloads a frame in WebKit (no
  `moveBefore`) and drops a selection everywhere: resolving a thread moves its card
  into the "Resolved · N" disclosure and reopening moves it back (`thread/inline.js`);
  re-rendering a file in `lf-diff` moves its comment threads beside the new rows
  (`lf-diff.js`); a modal dialog moves into its opener's popover for top-layer order
  (`keyboard/layer-stack.js`); and a reply's widgets move to whichever view shows
  them (see "A reply's widgets in every view of it"). Hiding resolved cards in place
  would show them among open ones unless CSS reorders them, so it needs the user's
  say; the `lf-diff` fix is keeping rows stable or the containers outside them.
- **A summary's fold button ignores a press while words are selected.** With text
  selected in a thread message, pressing "Show/Hide N earlier messages" does nothing,
  even twice; Enter works. Reproduced in Chromium with a selection set by script,
  before the flat transcript too.

### Agent and author experience

- **Consider a reminder when revising decided content.** An optional `--force`
  acknowledgment could make an agent pause over an existing decision. Revisions
  currently remain unrestricted; decide whether such a reminder helps before
  adding one.

- **#20 — Act on the plain HTML comparison.** The
  [recovered Codex rerun](notes/agent-usability-evals.md#recovered-codex-comparison-2026-10-14)
  split six pairs into two Leaf wins, two HTML wins and two order-sensitive splits.
  Judging now separates making decisions from reading the final record; the
  decision-authoring reference also distinguishes user requests from agent-proposed
  decisions.
  Test compositions where evidence supports them, using current code and an
  unfamiliar author; two samples per task do not settle which compositions work
  generally. Reproduce remaining authoring failures on current code before testing
  short composition suggestions; the older plain HTML configuration advantage
  preceded per-item playground controls and does not by itself justify more
  instructions. Keep widget-specific advice in `x-instructions`, cross-widget
  compositions in package instructions, and general selection principles in the
  authoring reference.
- **Keep delegated work in the panel's status on Codex and Pi.** Claude Code's
  `busy` session record keeps the status reading Working in the background after
  the coordinator's turn ends (#3370); Codex and Pi publish no such record, so their
  status stops reading Working while workers still run
  ([the note](notes/user-feedback-responsiveness.md#proposed-improvements)).
- **Decide what the reply budget counts.** A small page change takes 21–42 s to
  reply on every harness against a 7 s target, and Leaf's delivery and tool time is
  0.3–2.6 s of it ([readings](notes/user-feedback-responsiveness.md#latency-targets-and-readings)).
  Decide whether the target counts Leaf's share or the whole reply.
- **#24 — Measure time to an initial reviewable page and the value of review.**
  Retrospective replay now proves one usable Leaf candidate and one usable HTML
  candidate before their authors finished. Their observation triggers differ;
  earliest usability and the value of review still need a separate study.
  Measure from the user's request to the first browser-reachable page handed over
  for review. Separate preparation and reference reads, authoring, markup and
  render checks, the author's navigation task, independent reading, revisions,
  and serving and handoff. Record wall time, agent and tool cost, defects caught,
  and whether the author acts on findings; distinguish quick drafts from finished
  records and first handoff from later revisions. Compare the current scaffold and
  Layout examples with optional, editable compositions that make navigation and
  supporting material easy to place. Keep a composition only where it saves time
  or prevents defects while still letting agents change the layout or create their
  own; measure the cost of departing from it as well as starting from it.
  Run the study with actual page, registry, editing, and rendering tools so the
  measured handoff is a usable page rather than an HTML-only proposal.
  The catalog's
  `dashboard/reader-seeded` and `dashboard/reader-clean` contexts show the screenshot
  judge one triage board each, with a seeded count defect or the correct count, and
  ask both whether the count matches the cards. That narrow calibration scores count
  detection and false alarms separately from other page defects; it does not
  establish overall page acceptance. Author delegation traces and independent
  judge cost are separate evidence.

## Next

### User continuity and mobile access

- **Bring back a rewrite Escape discarded.** Escape drops a rewrite's changed words, as
  in Slack, Discord and Telegram, so an accidental press loses a long rewrite. Offer a
  way back, such as `g D` restoring the last discarded rewrite into its editor (the
  user's suggestion, 2026-10-06).
- **Show what `z` takes before it takes it.** `z` takes back the user's newest
  gesture however old, so on a page left for weeks it can reopen a thread resolved
  then, below the fold, and the notice names only the gesture's kind. The user chose
  (2026-10-21) to keep the reach unlimited, name the gesture and its age, and spend
  the first press revealing a target that is out of view or already picked up by
  the agent. [The undo-reach note](notes/undo-reach/README.md) has the build.
- **Decide when a page merits a separate phone composition.** Many pages are
  ephemeral and authored for a user reading on a large screen, so a bespoke phone
  animation may not repay its cost. Decide how the agent weighs the user's viewing
  context, expected reuse, and a readable fallback against that work. Distinguish
  those pages from maintained public examples such as `wt-merge`, where a phone
  design can be worth exploring.
- **Improve maintained examples through a phone-quality queue.** Keep desktop
  as the priority and address phone composition in a dedicated stream. Start with
  `triage-board`: at 390px only one bucket is meaningfully visible, while other
  buckets scroll horizontally and the release rationale sits below the board.
  Keep comparison context available during a move, preserving direct destination
  controls and undo.
- **Decide whether Back may restore a leaf.page page whole.** The local server
  sends `no-cache`, so Chrome and Firefox restore its pages on Back. leaf.page's
  container and the edge's state answers still send `no-store`, which keeps its
  pages out of Chrome's back/forward cache ([browser support](notes/browser-support.md),
  "Page cache"). Weigh an instant Back against what `no-store` protects there, a
  visitor's private page in the browser's disk cache on a shared computer, and
  exercise Safari on both.
- **Consider automatic Leaf recovery on resume.** Reuse the reconnect notice's
  eligibility checks to restore serving, ownership, and feedback delivery, while
  respecting explicit stops and transfers to another session.
- **Verify the native phone reading journey.** Check the explicit selection-to-comment
  handoff and reproduce the interactive-reply crash on a real iPhone. Browser emulation
  covers element targeting, commenting, passage geometry, and viewport sizing, but cannot
  show the native selection menu or software keyboard.
- **Finish what a phone user still cannot reach.** Remove keyboard-only hints,
  hover-only reasons, clipped diagram content, and remaining undersized touch targets.
  The hover-only reasons left are in Leaf's panel, whose phone design comes first: why
  a thread view's passage is gone, the compare state, a disabled menu row's reason,
  and On me's Approve version, whose title alone says why it is refused until a press
  does, and "Press z" once approved. Outside the panel, a finger
  holds a control to read its word (`held-word.js`). A finger can't comment on a whole
  block, since the leaf's menu leaves out Select element. A finger also lacks exits a
  key has: a mode's or search's steps take the counts off the panel's row until it ends, Android's back
  gesture closes nothing (the Escape ladder could answer it), Draw mode blocks scrolling
  and zoom, and an `lf-draft` has no close that keeps the edit.
- **Reconsider thread navigation.** Decide how Threads should change before
  refining it (`skills/leaf/assets/AGENTS.md`, "Space and scrolling"). The
  redesign also settles how focus stays off page content a panel covers (Max,
  2026-10-10). His rule (2026-10-06): the panels dominate focus, so moving focus never
  closes or changes an open panel, and focus never lands on content a panel covers.
  Tab walked onto page content under the old side panels, Threads and On, at
  1440×900 on an example since retired; the floating panel's views have not been
  checked for it. Making covered content inert
  was built and withdrawn: the visible part of a partly covered element went dead to
  clicks and selection, and focus still reached chrome markers, sample frames,
  overflowing children and content an attribute revealed. A comment box already
  refuses a covered seat (`underOccluder`, `geometry.js`). The two routes weighed
  before were laying the page out in the width a panel leaves, which reverses
  "the chrome opens over the page and never changes its geometry", and Leaf owning Tab beside a
  panel. The redesign also gives a thread's header controls a box no wider than they
  are: `.lf-thread-controls` stands transparent over the first message's author and
  time, so axe reads no contrast for those words, and the chrome's axe sweep cannot
  hold the overlap check the feature gallery's does (`overlapped_words`).

### Layout

The page arranges itself in CSS, starting from the Layout classes
(`skills/leaf/assets/layouts.css`), and Leaf keeps the contracts where pages, widgets
and its chrome coordinate.

- **Show returning threads without moving the current reading.** A thread returning
  above the open card makes the list scrollable, so the place hold scrolls the
  newcomer out of view rather than pushing down the card being read. The user sees
  it only in the count; give that arrival a visible route while preserving the
  current reading.
- **Let a page restyle Leaf's chrome on purpose.** A page's rules reach a widget's
  controls when they name the widget (`runtime/page-sheets.js`), but `chrome.css` is
  unlayered and adopted after the page's sheets, so a page rule naming a chrome class
  wins only by out-weighing the chrome's own selector. Choose the deliberate route for
  the chrome — tokens it reads, named parts, or a layer the page ranks above — so a page
  can change a thread card's format or hide one surface where it needs to.
- **Let a block be a workspace.** `feature-gallery` shows a workspace inside a column
  page, and since `layout-workspace` works only on `main`, it restates the Layout's
  full-height switch (720px by 480px) and its pane scrolling in about 20 lines. The pane
  rules now key on `--lf-full-height`, which a box sets for the children it sizes and
  which does not inherit, so a block workspace needs only to set it on its body and its
  grid of panes. Taking the Layout onto a block also means the runtime's layout region
  (`syncLayoutRegion`) and the render check's held-panes reading (`heldPanes`), which
  both look only at `main`, have to look at that block too. It waits for a page that
  needs it; a workspace page's own pane grid stays plain CSS.

- **Show each floating surface across the content it can hold.** `leaf-dev stills`
  screenshots the same states on the base and the branch, so it reports a change but
  misses a surface that is wrong on both. Until PR 1440 a margin thread card took all
  the room right of the text, 584px around the one word "why?" at 1920px, and no still
  showed it, because every card in the catalogue held a long thread. Build a suite that
  varies what a surface holds as well as the window:
  - Graded content for each surface. For a thread card that is one word, one line, two
    short lines, a paragraph, an exchange with an agent reply, and an unbreakable URL,
    each opened at 1920, 1440, beside an open panel, 1024 and 360px and cropped to the
    card and the marker that opened it. The comment box, the selection action bar and
    the floating panel's views take the same treatment.
  - Measurements beside each still: the surface's box, how much of its width its
    content fills, whether it covers the control that opened it while there is room
    beside it, and whether it crosses the visible edge. A threshold on each fails a
    surface that was already wrong, on both arms, which a comparison cannot do.
  - One page showing every still in a grid, a row per window width with the content
    growing along it and changed cells outlined. `lf-visual-review` steps through one
    case at a time, so the grid is a new view, in that package or beside it.
  - For comment placement alone, an SVG atlas of the side `comment-placement.js`
    chooses (`commentSide`) over a grid of inputs, which `pnpm run test:runtime` can
    draw without a browser.

  How to keep the candidates maintainable is not yet thought through, and comes before
  building. Adding a few dozen hand-written entries to `STATES` grows a list that
  nothing keeps complete. Decide whether a surface declares the ways its content
  varies and the suite takes every combination, where the graded fixtures live so one
  edit reaches every surface, how the matrix stays small enough to run and to read,
  and which measurements become thresholds a test enforces rather than numbers a
  person reads.

- **Test the Layouts on agents.** Give fresh agents tasks across the Layouts, then ask
  them to revise the results: turn a report into a report with live status while
  keeping its comments. They hold if revisions happen by ordinary composition. Include
  a cold agent asked for "a dashboard", the likeliest trigger for over-tiling. Run it
  with the agent-usability baseline, by extending the document, dashboard and
  queue tasks in `evals/`. For a workspace, also measure what a screenshot of the
  document cannot show: each pane's contents through its own scroll, how much of each
  pane is empty, and whether a reader reaches every pane by key. The arrangement
  judge sees only the first screen of a pane that scrolls and is told not to infer
  interaction, so no case yet measures whether a workspace works as a screen.
- **Layout values that wait for a task:** a selection-and-detail component whose phone
  form shows one side at a time; canvas regions, whose reading position is
  two-dimensional; slides as a presentation of `lf-tabs`.
- **Make a sidebar built from several blocks stick.** A sidebar's track sticks only
  when it holds one block (`:only-child` in `layouts.css`), so multi-block asides
  flow. The user decided (2026-10-21) to drop the condition: a multi-block aside
  sticks as a whole, scrolling within the window like a one-block track. Sticking the
  aside itself lets it cover a footer at the page's end (browsers bound a sticky flex
  item by its container, not its row; #2636), so the build waits on the user's pick
  between the runtime wrapping the blocks in one sticky box and keeping the rule.
- **Decide whether a too-narrow table fails a page at the fixed widths.** It is
  advice at every width, the two fixed viewports included, where it once refused
  the page.

### Layout stability

Boxes that still move without input, which the "Stability" rule in
`skills/leaf/assets/AGENTS.md` forbids. `tests/known_widget_findings.py` lists each widget
that changes size after first paint, with its cause.

- **Draw a text document's listing once its text has arrived.** Every
  `lf-text-document` now keeps its final box from first paint, but its module draws
  the listing as soon as it upgrades, before the state answer brings the text: one
  empty row under a caption reading “· no data”. When the text arrives, the gutter
  widens for two-digit line numbers and the code column moves right inside the box.
  `leaf-dev probe` on a page with a 20-line, a 3-line and a preview document scores
  that move 0.12 of layout shift at 1440px and 0.44 at 390px, though nothing outside
  the boxes moves, except where the “· no data” suffix wraps a long label onto
  another line and its removal shortens the box. Drawing nothing until the first
  state answer has been read would leave the theme's stand-in frame and caption until
  then.
- **Draw the contents map's spine in its first frame.** `lf-toc`'s initial drawing
  (`initial/lf-toc.js`) gives it its final box and rows, but in the margin its
  disclosure stays closed until the module opens it, so the spine and its markers
  first show at upgrade. Opening it earlier would show the markers evenly spaced and
  then move them, since each row's share is the module's measurement of the document
  (`#measure` in `lf-toc.js`); taking that measurement once the document has parsed
  would put them in place.
- **Let the shift watch see the runtime's own scrolls.** `tests/shift_watch.js`
  measures in layout coordinates, which remove scrolling, so a scroll the runtime
  makes during a gesture can move the control under the user's aim and fail
  nothing; #2895's reply box moved 9–14px on a send that way. The proposed rule:
  only a gesture that takes the user somewhere (the `t` and `q` walks, links,
  Go-to) may move its control, and every other gesture keeps it still. Declare the
  exemption on the command, not in a list in the watch. Then fix what it catches,
  starting with the landings that choose where a gesture's control ends up:
  `standOnThread`, the Threads list's landing, and `scrollThreadIntoView`. This
  needs the user's go-ahead, and its per-frame cost measured at 4x CPU throttling
  (`notes/shift-watch-cost.md`).

### Queues

A queue is one `lf-tabs list="side"` beside its open item (`page-layout.md`, "A
workspace"). The first real one, a 21-item triage page, showed these. Its list's
height and where a switch lands wait on the workspace decision under Layout.

- **Keep the open item's group named on a phone.** In the one-row strip a group's
  label stands before its run's first tab, so opening a later item in a long run
  (`alert-review`'s "Ledger consumer lag" at 390px) scrolls the label out of view. A
  label sticky at the row's start, stepping clear of the start press while stuck
  (`scroll-state(stuck)`, Chrome 133+), keeps it named, but `#showTab` then has to
  bring a tab in clear of a label whose width changes once it sticks.

### Before/after comparison

- **#29 — Make `lf-shot`'s views one coherent comparison.** A pair now offers
  Plain, Outlines and Pixels, and Pixels paints one picture: red where only the
  before image drew, blue where only the after image did, amber where both did. A
  shot with `pixels` alone opens in Pixels, one with `outlines` in Outlines, and
  any other in Plain. Settle the details as one design: which view a pair opens
  in, and whether every pair should offer every view rather than the author
  choosing them per shot; a key for the three colours; the rail's reading
  ("identical", "only slight changes", "2 areas changed"), which stands among the
  view buttons in another voice and reads as a view or a warning, as "identical"
  does over a pair of pin captures whose pins never moved; and the faint amber
  halo a moved mark's redrawn shadow leaves in Pixels.

### Recorded interaction review

Keep the optional Leaf timeline alongside Playwright's viewer, as Max chose
on 2026-10-07.

- **Explore DOM selection in the imported timeline.** The optional `playwright`
  package imports native actions, checkpoint images, captured frames and saved
  accessibility elements; following their comments restores the moment. Reuse
  Playwright's DOM renderer to add arbitrary element and passage selection, with
  comments scoped to the archive, action, phase and captured DOM identity. Preserve
  the distinction between a DOM snapshot and a separately captured image. Keep
  source, console and network inspection available through the full viewer.

### The agent's text interface

- **Decide the Leaf-owned defects the bad-pages eval left open.**
  [Bad pages and the checks](notes/agent-usability-evals.md#bad-pages-and-the-checks-2026-10-20)
  lists three that follow from recorded choices: an open thread card covers the text
  near its passage (14 of 40 pages), a phone's thread pin covers words (5), and a
  playground's bounded stage is 190–280px tall at 900×700 (4 of 9 configurations).
  Decide whether each choice stays, then fix the owner of any that goes and rerun
  `page-reads-at-every-width`.
- **Read the full render gate after handover.** Actual user views now supply passive
  geometry checks as agent context (`conversation-loop.md`, "The user's view"). The
  broader headless gate still runs on request. `page check --render` blocks the
  agent for the whole browser pass, so quick pages skip it and get none of its
  advice. Run the render readings on the server when a version goes live and
  deliver the findings through `leaf wait`: the agent hands the page over at once
  and refines it if a reading warrants, while a failure still blocks a record's
  stamp. **Unconfirmed:** measure how long the pass takes on a typical page, and
  whether agents act on findings that arrive after handover, before building it.
- **Consider loading a page once per render check.** `page check --render` loads
  the page afresh for each of its four passes, including dark mode and the narrow
  viewport. Switching those in place would save at most about 1.4 s on
  `triage-board` and 12.6 s on the corpus, measured by tracing the check's passes.
  The price is that dark mode and the narrow width would no longer be checked from
  a fresh start. Decide whether that coverage is worth the time before building it.
- **Decide what plain `page check` runs in a browser from the mistakes agents make.**
  It runs a page once in the host's browser, about 1.3 s, where the page has a script
  or places a page widget, a data widget or a widget naming page media (`needs_browser`,
  `render_gate/page_code.py`); any other page checks in about 0.15 s. Widgets that fail on their attribute values
  (`lf-playground`, `lf-visual-review`, `lf-text-document`)
  and every widget in thread markup report through `leaf wait` once a browser draws
  them, but nothing runs them first. Write `evals/` cases in which agents author each
  kind and measure how often what they write fails to draw, then run the kinds agents
  get wrong and stop running those they reliably get right. `page-reads-at-every-width`
  covers documents, dashboards, queues and playgrounds: none of its 40 final pages had
  a widget that failed to draw, and every plain-check finding during authoring was
  markup ([notes](notes/agent-usability-evals.md#bad-pages-and-the-checks-2026-10-20)).
  Thread markup and the other widgets above are still unmeasured.
- **Derive the waiting status from the page's open obligation.** Consider using the obligation's
  words when no explicit waiting detail is needed. **Unconfirmed:** try pages with
  several open obligations and an informational page before choosing how the panel's
  status explains who owes the next move. Keep explicit agent status available when the
  obligation alone does not explain the wait.

### Development velocity

- **Require `test` on `main` again.** Since 2026-10-13 Leaf merges any change that
  introduces no new failure, so `test` is not a required check: a pull request
  inherits whatever main fails among the tests it runs, and only an admin could merge
  past that (`tests/AGENTS.md`, "Selecting checks"). Once main stays green
  between merges, make `test` required again in `main`'s branch protection and drop
  that paragraph's exception.
- **Resume the thread appearance gate.** The user wants it working again at some point
  (2026-10-21). Since 2026-10-12 the message-delivery journey and acceptance tests in
  `tests/*/test_render_thread_snapshots.py` are skipped to save test time while
  development moves fast; the references had already drifted twice unnoticed, since
  only a manual macOS run compares them. Once development slows, remove the skips,
  then capture, review and accept current images (`leaf-dev thread-snapshots`), and
  have landing run the comparison so it cannot drift again, such as `wt merge`'s macOS
  pre-merge when the thread runtime or theme changes.
- **Guard thread appearance on CI again.** The thread snapshot gate compares images
  on macOS only (`dev/leaf_dev/commands/thread_snapshots.py`), so a pull request's Linux CI
  checks the delivery journey but not how it looks. Fonts and antialiasing differ by
  OS, so Mac and Linux images never match. A Linux image could only be made on CI's
  own runner, which meant pushing, downloading the run's images and accepting them
  by hand. Find an approach where whoever changes the appearance can render the
  compared images themselves. Candidates: render Linux baselines locally in the
  same container CI runs, the approach Playwright recommends (an arm64 image on a
  Mac matches CI only on an arm64 runner); or a hosted visual-review service that
  renders both sides itself.
- **Keep the agent journey's samples.** `leaf-dev journey` prints one timed sample
  per run, and `publish-site` runs it on every release, but only the machine that
  ran it keeps the sample (`$XDG_STATE_HOME/leaf-dev/journey.jsonl`), so CI's
  samples are lost and a slower title or reply shows only to whoever is watching.
  Find a durable store that CI and local runs can both write to, with the Worker's
  credential proxy in mind, and chart each step across releases against the targets
  in `notes/user-feedback-responsiveness.md`. Uploading a CI artifact needs no extra
  token but keeps 90 days; a file in `max-sixty/leaf-assets` keeps history but needs
  a token that can push there.

## Etc

Revisit these when their stated trigger becomes real; they are not an active queue.

### Product and harness ideas

- **Link filenames to their repository context.** When a page or thread knows the
  repository and revision, offer a GitHub source link for a filename such as
  `AGENTS.md` rather than treating it as a web domain. Establish how that context
  reaches Markdown before inferring a destination from the filename alone.

- **Decide the site's structure before release.** Choose how much of the status
  derivation the site explains, and whether to reorganize its pages by reader
  ([proposal](notes/site-structure.md)). Trigger: preparing a release.
- **Assess whether automatic measurement freshness is useful.**
  Keep the current `lf-num` source/write-time reminder for now. Look for cases where
  its warnings lead an author to update a stale claim, and weigh that benefit against
  the source binding, timestamp and special markup authors maintain. Consider
  removing the subsystem if it does not prove useful.

- **Revisit where an abandoned comment's words come back.** A page comment closed
  with Escape keeps its words, and the next box `c` opens, such as a thread card's
  reply, offers them, since Leaf can't know exactly where the user last typed. That
  is deliberate; a better approach may tie the words to where they were written.
  Trigger: a user is surprised to find their words in an unrelated box.
- **Revisit a pin's icons if they read unclearly.** A pin shows the rail's outline
  icon in white on its fill, at 26px. A filled icon reads more clearly at that size,
  and needs no second copy — the same SVG with its fill set — but only an icon whose
  outline is a closed shape fills cleanly. Trigger: a user misreads what a pin holds.
- **#30 — Try a feed of ready-to-approve actions.** An agent pass prepares
  actions, such as a drafted email, and the user approves, edits, dismisses or
  discusses each. Every verb exists as an item; Leaf lacks an agent that runs
  unprompted and a list across pages. The [feed note](notes/feeds/README.md) waits on
  the user's pick between a "Today" page owned by one background session and On me
  across every page, and on whether agents' offers become items.
- **Explore independent jobs.** Work out their identity, observer, continuation
  owner, and outcomes across background commands, delegates, and external waits.
  See the [Thread plan](notes/threads.md#independent-jobs-delegation-and-continuation).
- **Tell the agent when to ask before ending its own to-do.** The agent ends its to-dos
  itself, and asks first, with a decision widget or a question in a thread, when the result
  needs the user's sign-off, as the user decided. The shipped
  instructions don't yet say when that is. Trigger: an agent ends a to-do as done that
  the user wanted to see first.
- **Let the user edit items in the On view.** The user's only edit today is Done
  on a to-do the agent put on them, so dropping a to-do, renaming it or ending one of the
  agent's means asking in a thread. Editing the row directly in the view would record the user's change as
  their own move. Trigger: a user writes a comment only to close or adjust an item.
- **Multiplayer:** let several users share a page, each recorded as themselves.
  Every browser event is `author: "user"` today, so the log cannot say who moved,
  commented or voted, and nothing records who has the page open. Claude Code
  Artifacts store a viewer id on each row and resolve names, faces and presence
  from the host. Settle user identity and how it reaches the append door before
  building a feed or presence on it.
- **Show which pane has focus, and move between panes by key.** A terminal marks
  its active pane and one key moves to the next. In a workspace today the arrow keys
  walk a side list, `m` reaches the next item on On me, and a pane body that scrolls is a
  Tab stop, but nothing marks the active pane and no key moves from one pane to the
  next. The runtime already tracks it: `userReadingRegion` (`reading-regions.js`) is the
  pane holding focus, or else the last one pressed, wheeled or touched, and `j`/`k`/`d`/`u`
  scroll it. Until the user picks a pane those keys reach the page, which a workspace
  doesn't scroll, so they appear to do nothing. The feature is a mark on that region and
  a key that moves it. Pane focus belongs to the
  panes and the keyboard layer, not the Layout, so it works the same wherever panes
  stand. Draw it as a playground before building it.
  Trigger: a user loses track of the active pane, or tabs through a pane to reach the
  next one.
- **Expand everything waiting with a keypress.** A held notice, a collapsed summary,
  and a folded card or section each open one at a time, with Enter or Space on it,
  `g f` for a page's sections, or a `t` walk for a thread's held news. Nothing opens
  them all at once, yet a page-level key spent on that alone seems wasteful. Think
  about which surface should own it, such as one command on the panel. Trigger: a
  user steps through notices one by one to catch up.
- **Let a user add, remove and edit table rows.** A creating action carries only the
  new child's id and words, not a record of several fields. The
  [datastore review](notes/datastore-review.md) lists what a row feature must
  support; test that list on a real table task before extending the protocol.
  Trigger: a page whose table the user needs to edit.
- **#16 — Named widget interfaces:** let a typed reference name the interface its
  target implements rather than a role in its package's role table, such as
  `$work.widgets` ([proposal](notes/named-widget-interfaces.md)). Trigger: a second
  package implements the command `goal` or `readings` interface.
- **Visual review beside Leaf:** coordinate a real browser target through the harness
  when review work needs it; expand inspection only when focused workspaces fail a
  real task.
- **Other harnesses:** add a blocking `leaf wait` route when another agent harness needs
  foreground handoff.
- **Decide whether an exported page carries its threads.** `leaf page
export` writes a file that boots the page's own runtime offline, and that file
  embeds the page's threads in its state reading. The runtime turns the
  thread surface off offline (`threadAvailable: !offlineInteractive`
  in `leaf.js`), so a reader of the file sees no comments or agent replies.
  Decide whether an export is the page alone or the page with its discussion; the
  likely answer is threads shown read-only, with the composer and sends off.
- **Character bindings:** let users disable them when real use calls for it.
- **Replacement diffs and visual masks:** add them when repeated reviews need
  more than plain replacement and focused inspection.
- **Motion evidence:** define video, caption, and transcript handling when core
  gains durable video.
- **Revisit long-thread folding after using summaries.** If agent-written summaries
  leave users struggling with long histories or oversized messages, follow the
  [Thread plan](notes/threads.md#later-long-thread-reading).

### Implementation candidates

- **Remove the early-key hold once startup is fast on slower machines too.** Keys
  pressed before the runtime upgrades or the first saved state lands are queued, a
  "Page still loading" chip appears after 150 ms, and the keyboard controller
  replays them (`holdEarlyKeys` in `runtime/bootstrap.js`, `takeHeldKeys` in
  `keyboard/controller.js`, `INPUT_PENDING` in `keyboard/dispatch.js`, the pending
  clause of `scopeAvailable` in `keyboard/bindings.js`). Without the hold, such a
  key is lost or runs the browser's own action, such as Space scrolling or `/`
  opening Firefox's Quick Find. Trigger: every example presents in about 250 ms
  both on this Mac and with Chromium's CPU slowed 4x, which stands in for a slower
  laptop as Lighthouse's mobile run does; then delete the hold, which a 2026-10-14
  trial measured at 240 runtime and 540 test lines. This Mac is the fastest machine
  pages run on, so its reading alone would delete the hold where it still helps.
  The throttled bar is also 250 ms because the bar is how soon a reader presses a
  key after a page appears, which is the same on any machine. A throttled bar near
  1 s would add nothing to the unthrottled one, since the throttle multiplied the
  medians below by 3.7 to 4.3. Take each reading as the median of five runs per
  example, with the Mac's load average beside it, of
  `uv run leaf-dev probe EXAMPLE` and `uv run leaf-dev probe EXAMPLE --cpu-throttle 4`,
  reading `.startup.presented.at` from the JSON line each prints. A probe reads a
  fresh server's first load, which is what a reader gets when an agent hands them
  a page. On 2026-10-19 the trigger had not fired. Reloading each example five
  times on one running server, the median `startup.presented.at` was 167 to 238 ms
  on six of nine examples, but 289 ms on `code-comparison`, 335 ms on
  `command-hub` and 487 ms on `pr-walkthrough`. With a 4x CPU throttle the same
  medians were 632 ms (`triage-board`) to 1826 ms (`pr-walkthrough`). On four
  examples, a server's first load took 120 to 230 ms longer than its reloads. The
  Mac's load average was near 12 on 18 cores throughout.
- **Draw the margin's annotations once per thread pass.** They draw from their own
  watcher, which waits only for the projection's chrome, and again when the thread
  presentation commits (`untracked(renderAnnotations)`, `thread/presentation.js`):
  22 ms of applying a comment's answer, profiled. Making the watcher wait for the
  thread region drew the margin once (11 ms) but broke reply continuity
  (`continueReplies`, `thread/focus.js`, which expects the margin's cards drawn;
  seven cases in `tests/browser/threads/test_seated_threads.py`), and a held thread
  pass would withhold every margin paint. A fix needs continuity to wait for the
  margin's paint and the margin to stop depending on the thread region committing.
- **Consider moving the before/after reading out of the core.** How
  `runtime/image-difference.js` reads a pair (blocks, moves, outlines) is
  experimental and about 820 lines in the core runtime, consumed by `lf-shot`,
  `lf-visual-review` and `leaf-dev stills`. A package could own it, so the core keeps
  only what every page needs. Try it on non-Leaf captures first (another site, a
  terminal, a plot); where the capture is a browser's, recording each element's box
  beside the PNG would read moves exactly, as Percy's and SmartUI's layout modes do.
  Known gaps: a pane that scrolled within itself reads as scattered changes and moves
  rather than one region, a border that changed length draws a thin outline, and a
  changed 1440x900 pair costs about 40–70 ms on the main thread (8 ms before), which
  a worker would take off it.
- **Reduce plugin-update downloads by cleaning Git history.** Trigger: Leaf
  publishes releases, which will likely build the kernel another way than
  committing it, the source of most history growth (an estimated 5–13 MB a month).
  Then remove historical images and obsolete large JavaScript bundles while
  preserving current files. A disposable full-history rewrite saved about 27 MiB.
  Coordinate the rewrite across remote refs and local worktrees, retaining the
  commit mapping and testing that updates preserve active work without restoring
  the removed history.
- **Set interaction-trace privacy before sharing pages.** Define who can inspect
  traces, consent or opt-out, sensitive-field redaction (including passwords,
  pasted text, and selection), and retention/deletion for page-local files and
  hosted Workers Logs. Page-local traces currently record raw input for this
  single-user stage; the public site keeps interaction metadata only.
- **Make a leaf.page dispatch survive its container.** The Worker acknowledges an
  accepted event and hands its Codex turn to `waitUntil` (`worker/src/agent.ts`,
  `dispatchAgentTask`). Nothing records the event and turn identity in the
  container's Durable Object, and nothing recovers a dispatch whose container
  disappears or outlives the `waitUntil` window. Trigger: a hosted answer lost that
  way.
- **Start each release's containers on its own image.** The Worker goes live on a
  release before Cloudflare rolls its image out, so for up to ten minutes after a
  deploy a session's new container can start on the previous image. The Worker
  holds requests behind `503 Retry-After` (`rollingOut` in `worker/src/index.ts`),
  and only event sends retry it, so a sample opened then fails until a reload.
  Cloudflare's `durable_object` scheduling policy uploads the image map with the
  Worker version and lets the session pick its image at start
  ([docs](https://developers.cloudflare.com/containers/configuration/scheduling-policy/)),
  which removes the window, `rollingOut`, the retry, and `verify-site`'s rollout
  wait. Moving costs a new container application, a port off the `Container` class
  (pings, sleep, outbound interception) and `standard-1` in place of `basic`.
  Trigger: the policy leaves beta, or leaf.page gains visitors a deploy would
  interrupt.
- **Push page updates instead of polling.** Each visible tab asks `api/news` every
  250 ms (`runtime/state-feed.js`). Pages streamed updates until #1589 replaced
  per-document streams with polling, because the streams used up HTTP/1.1's six
  connections per host. Measured on 2026-10-13, polling costs about 1% of one core
  per visible tab locally; on 2026-10-20 the server spent 1.8 ms of CPU per look,
  0.7% of a core at four looks a second. On leaf.page each look bills a Worker and
  a Durable Object request, under $1.20 a month per user at list price and inside
  the included quotas, and polling accounts for about 1% of container hours. A
  stopped container stays asleep under polling, since its Durable Object answers
  `api/news` from the page the container last saved. A stream held in the
  container would wake it for a passive reader, so on leaf.page the Durable
  Object should hold the stream instead: under Cloudflare's WebSocket Hibernation
  API its clients stay connected while the object is out of memory, without
  duration charges
  ([docs](https://developers.cloudflare.com/durable-objects/best-practices/websockets/)).
  When the page server answers `api/news`, it renews the user's attention lease
  (`_news` in `http.py`); the Durable Object's saved answer does not. A push
  channel for a live page must carry that lease too. Push would show an agent's change
  sooner: locally the file watcher notices an append in about 90 ms against
  polling's 125 ms average, and on leaf.page, where a look takes about 370 ms, it
  would save roughly 250 ms. Push would not change how a tab loses or finds its
  server: a failed look already reports a dead server, a retry against a dead
  local server costs no measurable CPU, and a tab reaches its restarted server
  only because `service.json` keeps the server's address. A sketch of one stream
  per browser (a leader tab holding it through a Web Lock, relaying over a
  BroadcastChannel, with samples relayed through their parent) adds about 115
  lines more than it deletes; a WebSocket per document avoids the leader and the
  relay, and gestures stay on `POST api/event`, whose queue already orders and
  retries them. A WebSocket brings costs polling lacks. A connection broken by
  sleep or a network change still looks open, and browser code can't send
  protocol pings, so the tab needs a heartbeat message and a reconnect loop.
  Each server restart or Worker deploy drops every socket. The handshake can't
  carry `layerHeaders`. A WebSocket isn't bound by CORS, so the server must
  check `Origin`. Either way, first give
  the server one subscribable change detector per page: the stat token and the
  watched files already derive from one declaration of page inputs
  (`served_state/reading.py`), but `api/news` stats on every look while the row
  publisher and lifetime supervisor wake on the shared subscription
  (`file_changes.page_changes`), which runs only in a serving process. Trigger:
  hosted replies visibly lag, or a page streams an agent's reply as it is
  written, which polling would show in 250 ms jumps of whole-state reads.
- **Claude Code tool observation:** consider a cheap hook for sessions holding
  pages if status evaluations show that agent declarations are insufficient.
- **Leaf hook cost with owned pages:** Stop, prompt, and Codex tool-result
  hooks discover ownership before page reading and without importing the CLI.
  A session holding a page still imports page reading and reads each page's
  state before answering. Measure that cost before expanding tool observation;
  a compiled hook path is a further step if import cleanup is insufficient.
- **Invoker commands:** revisit when the browser support Leaf needs can replace
  the current dialog and popover handlers. At a Chromium floor of at least 135,
  test `command` and `commandfor`; Leaf still owns layer ordering, semantic state
  and focus restoration.
- **MCP Apps:** when a host the user runs renders MCP Apps, rebuild inline hosting
  as a direct resource: Leaf's runtime in the host's `ui://` resource, with reads and
  gestures carried by MCP tools to `PageStateService` and the event append boundary,
  one renderer and one log. Accept it once, in that host, its renderer allows the
  content security policy Leaf needs, including evaluating `lf-chart` bodies, a
  keyboard choice and an anchored comment reach the page log and show in Threads,
  reopening rebuilds the same state, versions, new layer assets and external data
  use the same transport, and delivery wakes an idle task (accepting `ui/message`
  doesn't show that). The
  removed transport and its probe are at `a8ed55e68` (`notes/mcp-apps/probe`); its
  last run rendered a page in the reference host but failed to save a choice.
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
- **Diff controls:** consider author-configurable wrapping and per-file review tracking
  when a page needs them. Keep their controls optional.
- **A reply's widgets in every view of it:** a reply's widgets show in one view
  at a time (the panel, then its margin card, then its seat), and the others draw
  only its words (`authoredRank`, `thread/messages.js`). Giving each view its own
  copy needs every id lookup to resolve inside the drawing that asks, through
  `elementById(id, root)` (`passages.js`): about 31 `elementById` and 9
  `getElementById` calls in the runtime and the package widgets' own lookups
  (`lf-board`, `lf-options-addition`). The lookups that arrive with no drawing
  each need a rule: obligation standing, `m` walks, an anchor on an element in a
  reply, and the presentation regions keyed `widget:<id>:render`. A 2026-10-20
  trial of per-drawing copies without that broke all four (reverted within
  PR #3436). Revisit if seeing a question in the page and the panel at once is
  worth it.
