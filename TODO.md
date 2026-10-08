# TODO

## Biggest current challenges

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

Priority runs from **Now** to **Next** to **Etc**. Themes group related work within
each priority; bullets are outcomes, not implementation plans. Linked notes hold the
evidence and detailed briefs. Numbered items keep the ids shared with `notes/`.
Completed work and rejected ideas live in git history or the relevant research note.
An item marked **Unconfirmed** rests on a reading nobody has run or a design nobody
has tried; settle that before building it.

## Now

### User experience

- **#25 — Answer one decision beside its evidence and on a board.** A section's
  picker and its board card currently record independent facts. Choose the owner
  and test both views against one decision, including ordering, write-ins and
  revision retraction ([design](notes/shared-decisions.md)).
- **Make complete reading journeys feel coherent.** Audit a document, workspace,
  board or table, and populated thread in light and dark at wide and narrow
  widths. Fix recurring gaps in type, spacing, framing, controls, and responsive
  behavior.
- **Keep the Thread hierarchy clear.** Check context, search, filters, agent
  activity, selection, and reply editing in the implemented accordion.
- **Name a Pi Thread promptly.** Claude Code and Codex pages and leaf.page name a
  thread from the user's words a few seconds after they arrive (`thread_titles`).
  `PiHarness` has no `title_generator`, so a Pi page's thread is named only by the
  agent's reply. Give the page server a request on Pi's configured model, such as
  a print-mode run with tools, extensions and hooks off, and measure it.
- **Keep a long Thread's standing visible.** Summary checkpoints already condense
  older messages. Test a current one-line reading of what is decided and what remains
  open, distinct from a historical summary, and decide how a revision invalidates it.
  See the [Thread plan](notes/threads.md#current-standing).
- **Test annotation placement in context.** Compare a pinned marker card with a
  sparse left-comment layout on a document and a workspace. Keep full history and
  search in Threads and use Page Map on narrow pages; show only one margin treatment
  at a time. Include dense phone prose with anchored pins: the comparison report
  showed pins covering text at 390px. Test what happens when no text-clear seat
  exists, preserving annotation access without moving the reading column. See
  [the comparison finding](notes/comparisons.md#phone-annotation-placement-2026-10-05).
- **Make the next move and its result apparent.** Play through `review-a-plan`,
  `triage-board`, `pr-walkthrough`, and `ship-review`; fix dead ends and moves whose
  result is hidden. Decide whether a page needs one progress reading across Asks,
  board work, and version approval. Test a concrete first task before changing the
  public home page's prompt.
- **Keep Tab off page content a panel beside the page covers.** Threads and the
  Questions panel leave the page live beside them while standing over part of it. Max's rule
  (2026-10-06): the panels dominate focus, so moving focus never closes or changes a
  standing panel, focus never lands on page content a panel covers, and Threads still
  stands beside a full-width workspace. A comment box already refuses a covered seat
  (`underOccluder`, geometry.js). Tab still walks onto `annotation-workspace`'s rail
  under Threads, or the Questions panel that shares its right edge, at 1440×900. Making what a panel covers inert was built and withdrawn: it left the visible
  part of a partly covered element dead to clicks and selection, and focus still reached
  chrome markers, sample frames, overflowing children and content an attribute revealed.
  Decide between laying the page out in the width a panel leaves beside it, which
  reverses "auxiliary surfaces never change the page's geometry"
  (`skills/leaf/assets/AGENTS.md`), and Leaf owning Tab beside a panel, skipping stops
  `hides` says it covers.

### Agent and author experience

- **Consider a reminder when revising decided content.** An optional `--force`
  acknowledgment could make an agent pause over an existing decision. Revisions
  currently remain unrestricted; decide whether such a reminder helps before
  adding one.

- **#3 — Prevent an obsolete execution from closing continued work.** A later
  `task start` records a new execution, but admission still accepts an older
  session's `task_end`. Test competing continuations and keep the delayed result
  from closing the newer work ([comparison proposal](notes/comparisons.md#concrete-follow-up-proposals-2026-10-04-revised-2026-10-05)).

- **Compare Leaf authoring with plain HTML (#19).** The
  [agent-usability baseline](notes/agent-usability-evals.md#second-slice-2026-09-27)
  now covers the live loop, a mixed batch, an elided thread, an unfamiliar package and a
  shared data source, and calls for no new interface. Compare authoring and a feedback
  cycle with plain HTML before improving Leaf's authoring instructions;
  **#20** then [teaches the compositions that prove useful](notes/workspace-followups.md#item-20),
  including how authors discover diagram comparison suggestions.
- **Keep agent activity intelligible throughout a task.** Run the
  [status evaluations](notes/user-feedback-responsiveness.md) for delivery,
  multi-step work, and delegation. Show the plan as well as the current step;
  check that the hosted website agent's status is readable without delaying its
  reply. Keep delegated work visible while its watcher is live.
- **#24 — Measure time to an initial reviewable page and the value of review.**
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

### Prose

- **[Rewrite Leaf's prose for its readers](notes/prose-review.md).** The maintainer
  rewrite is written and awaits independent review and landing. Agent instructions are
  the next phase, scored with `evals/`. Site structure, UI vocabulary and example
  selection wait on the five decisions in the note. Judge each rewrite by reader
  usefulness and preserved behavior; word counts describe the cut, not its quality.

## Next

### User continuity and mobile access

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
- **Consider automatic Leaf recovery on resume.** Reuse the reconnect notice's
  eligibility checks to restore serving, ownership, and feedback delivery, while
  respecting explicit stops and transfers to another session.
- **Verify the native phone reading journey.** Check the explicit selection-to-comment
  handoff and reproduce the interactive-reply crash on a real iPhone. Browser emulation
  covers element targeting, commenting, passage geometry, and viewport sizing, but cannot
  show the native selection menu or software keyboard.
- **Finish what a phone user still cannot reach.** Give touch users visible passage
  threads, and remove keyboard-only hints, hover-only reasons, clipped diagram content,
  and remaining undersized touch targets. Hover-only today: why Approve version is
  disabled, and "Press z" once approved; a reaction's word before it is sent; a margin
  marker's label and its status (Sent, Stalled); the diff's line "+"; and the
  latest-edit error, a dead passage's reason, a disabled More entry's reason, and the
  compare state. A finger also lacks exits a key has: a mode's or search's steps take
  Threads off the row until it ends, Android's back gesture closes nothing
  (the Escape ladder could answer it), Draw mode blocks scrolling and zoom, and an
  `lf-draft` has no close that keeps the edit.
- **Decide whether the response bar's reactions and Suggest need a pointer route.**
  The floating comment bar shows no ellipsis (⋯), so its field spans the bar and a sent
  message keeps the card's measure. Its other responses, Suggest and the emoji
  reactions, open only by key: Tab from the field, or `e`. A mouse alone has no
  route to them, and a finger has none at all. Decide whether to make them more
  available, such as a banner control under a coarse pointer, a reaction row on the
  sent card, or a control that keeps the field's measure
  (`skills/leaf/assets/runtime/composing/selection.js`).
- **Give the thread panel's touch grip its own space.** Reserve room for the grip
  and collapse inactive reply controls if more thread cards should fit.

### Layout

The page arranges itself in CSS, starting from the Layout classes
(`skills/leaf/assets/layouts.css`), and Leaf keeps the contracts where pages, widgets
and its chrome coordinate.

- **Show returning threads without moving the current reading.** A thread returning
  above the open card makes the list scrollable, so the place hold scrolls the
  newcomer out of view rather than pushing down the card being read. The user sees
  it only in the count; give that arrival a visible route while preserving the
  current reading.
- **Hold the shipped workspaces to the overflow advice.** `alert-review` shows one
  alert's decision at a time, but `page check --render` still advises that its queue
  (`ar-queue`) runs 106px past its region at every width from 720 to 1920px, and
  `rust-sort`'s stage pane 100px at 720px. Fit both, then make
  `test_page_fixture_renders` fail on that advice for workspace examples, with
  `rust-sort`'s source pane the one reader allowed to scroll; today it asserts only
  the gate's failures ([plan](notes/chrome-and-covers.md)).
- **Decide whether the desktop bottom bar goes.** Its key hints would move behind `?`
  and its status into the banner; the bar is how a desktop user learns the keys
  without asking, which is the trade to weigh ([plan](notes/chrome-and-covers.md)).
- **Let a page restyle Leaf's chrome on purpose.** A page's rules reach a widget's
  controls when they name the widget (`runtime/page-sheets.js`), but `chrome.css` is
  unlayered and adopted after the page's sheets, so a page rule naming a chrome class
  wins only by out-weighing the chrome's own selector. Choose the deliberate route for
  the chrome — tokens it reads, named parts, or a layer the page ranks above — so a page
  can change the thread panel's format or hide one surface where it needs to.
- **Let a block be a workspace.** `feature-gallery` shows a workspace inside a column
  page, and since `layout-workspace` works only on `main`, it restates the Layout's
  full-height switch (720px by 480px) and its pane scrolling in about 20 lines. The pane
  rules can't simply key on `--lf-full-height`: they say which panes the workspace sizes
  by where they stand under `main`, and the property is inherited by every descendant.
  Taking the Layout onto a block also means the runtime's layout region
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
    the Threads panel take the same treatment.
  - Measurements beside each still: the surface's box, how much of its width its
    content fills, whether it covers the control that opened it while there is room
    beside it, and whether it crosses the visible edge. A threshold on each fails a
    surface that was already wrong, on both arms, which a comparison cannot do.
  - One page showing every still in a grid, a row per window width with the content
    growing along it and changed cells outlined. `lf-visual-review` steps through one
    case at a time, so the grid is a new view, in that package or beside it.
  - For comment placement alone, an SVG atlas of the side `comment-placement.js`
    chooses (`commentSide`) over a grid of inputs, which `npm run test:runtime` can
    draw without a browser.

  How to keep the candidates maintainable is not yet thought through, and comes before
  building. Adding a few dozen hand-written entries to `STATES` grows a list that
  nothing keeps complete. Decide whether a surface declares the ways its content
  varies and the suite takes every combination, where the graded fixtures live so one
  edit reaches every surface, how the matrix stays small enough to run and to read,
  and which measurements become thresholds a test enforces rather than numbers a
  person reads.
- **Offer the Page Map with the first paint.** The margin pass marks where markers are
  pins (`data-lf-pins`), and the banner's Map toggle follows it, so on a phone the
  toggle appears one pass after the banner rather than with it.
- **Test the Layouts on agents.** Give fresh agents tasks across the Layouts, then ask
  them to revise the results: turn a report into a report with live status while
  keeping its comments. They hold if revisions happen by ordinary composition. Include
  a cold agent asked for "a dashboard", the likeliest trigger for over-tiling. Run it
  with the agent-usability baseline (#19), by extending the document, dashboard and
  queue tasks in `evals/`.
- **Layout values that wait for a task:** a selection-and-detail component whose phone
  form shows one side at a time; canvas regions, whose reading position is
  two-dimensional; slides as a presentation of `lf-tabs`.
- **Unconfirmed: scrolling a live sample sometimes sticks.** A user reported it
  while a sample still scrolled inside a fixed-height frame, with no reproduction.
  The frame now takes its page's height, so nothing scrolls inside it; check that the
  report no longer reproduces once the scrolling changes land.

### Layout stability

Boxes that still move without input, which the "Stability" rule in
`skills/leaf/assets/AGENTS.md` forbids. `tests/known_widget_findings.py` lists each widget
that changes size after first paint, with its cause.

- **Size the activity feed and text documents at first paint.** `lf-activity` draws the
  log's history and `lf-text-document` its bound source's value, and both arrive with
  the first state answer, after first paint. Serving that state inside the page does
  not work: modules run after first paint, and a page revision is immutable while the
  log keeps changing. Follow #1566's Command Hub pattern instead: draw a summary whose
  structure is fixed, declared as the widget's `x-prepaint` so the first paint lays it
  out, open the rows from it, and hold later growth with
  `HeldReading` (`runtime/thread/held-news.js`) while it would be seen. Check first
  whether a text document, which the reader came to read, can stand behind a summary.
- **Decide the contents' form before first paint.** `lf-toc` changes size because the
  margin pass decides after first paint whether it is the fixed map in the margin or
  the outline in the flow (`data-lf-margin`, `margin-layout.js`), from the room
  it measures at that point. A held summary does not answer that cause. Check first whether a
  container or media query on the space beside the column can make the same decision
  in CSS.
- **Find a first-paint fix for targeting.** `lf-targeting` has no recorded cause;
  read `lf-targeting.js` for what it builds after first paint before choosing an
  approach.
- **Check that margin markers paint in place in their first frame.** The shift watch
  exempts the page until it is presented (`tests/shift_watch.js`), and #1603 records
  startup shifts only as diagnostics, so a marker drawn in the wrong place in its first
  frame and then moved would fail nothing. Read `leaf-dev probe`'s startup readings on
  a page with margin markers at a few widths.

### Queues

A queue is one `lf-tabs list="side"` beside its open item (`page-authoring.md`, "A
workspace"). The first real one, a 21-item triage page, showed these. Its list's
height and where a switch lands wait on the workspace decision under Layout.

- **Start `a` from the open item's Ask.** From a row, `a` goes to the queue's first
  open Ask, and `1` then picks for an item the user isn't looking at. The walk
  measures from focus (`askPosition` in `asks/view.js`), and the row precedes every
  panel; `t` and `T` measure the same way. A tab could stand at the view it opens for
  the walks (`standing-target.js`), while `c` on a row still names the row.
- **Keep the open item's group named on a phone.** In the one-row strip a group's
  label stands before its run's first tab, so opening a later item in a long run
  (`alert-review`'s "Ledger consumer lag" at 390px) scrolls the label out of view. A
  label sticky at the row's start, stepping clear of the start press while stuck
  (`scroll-state(stuck)`, Chrome 133+), keeps it named, but `#showTab` then has to
  bring a tab in clear of a label whose width changes once it sticks.

### Recorded interaction review

Max's assessment (2026-10-05): "I'm not sure this is great." Ship the optional
Leaf timeline as a trial alongside Playwright's viewer. Keeping it is undecided;
we may use Playwright directly. Try the comment workflow before investing further
in the integration.

- **Explore DOM selection if we keep the imported timeline.** The optional `playwright`
  package imports native actions, checkpoint images, captured frames and saved
  accessibility elements; following their comments restores the moment. Reuse
  Playwright's DOM renderer to add arbitrary element and passage selection, with
  comments scoped to the archive, action, phase and captured DOM identity. Preserve
  the distinction between a DOM snapshot and a separately captured image. Keep
  source, console and network inspection available through the full viewer.

### The agent's text interface

- **Keep a blocked stop from hiding the agent's answer.** When Leaf's Stop hook blocks
  a stop, the agent writes one more message, and where the harness shows only the last
  message (Claude Code's focus mode) that message replaces the answer: a user who typed
  `/whereami` twice saw two notes about a missing watcher and never the briefing. #1502
  removed that trigger, since the hook now does the watching. **Unconfirmed:** check
  whether any remaining block, such as input the turn still owes an answer to, reaches
  a turn whose answer is already written.
- **Reproduce the Codex delivery-start race.** Another client may start a turn
  between Leaf's idle check and its start request. **Unconfirmed:** test the installed
  App Server's behavior before changing delivery policy; the
  [Codex brief](notes/codex-integration.md#delivery-start-race) owns the experiment.

- **Measure how often agents produce bad pages.** Write `evals/` cases in which agents
  author ordinary pages, and have a judge read each result at wide, middle and phone
  widths for defects a user would notice. Record beside each defect whether
  `page check` reported it and whether the agent changed the page in response. That
  gives the rate of bad pages and how much the checks catch. Fix a recurring defect in
  the widget, Layout or theme that produced it, so pages need fewer checks, rather
  than adding readings or widths to the check. In the
  [layout vocabulary eval](notes/agent-usability-evals.md#layout-vocabulary-2026-09-29)
  every one of the 36 runs passed the gate, yet the judge still found tiny text at
  900px and phone defects.
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
  or places a page widget or a data widget (`needs_browser`,
  `render_gate/page_code.py`); any other page checks in about 0.15 s. Widgets that fail on their attribute values
  (`lf-playground`, `lf-targeting`, `lf-shot`, `lf-visual-review`, `lf-text-document`)
  and every widget in thread markup report through `leaf wait` once a browser draws
  them, but nothing runs them first. Write `evals/` cases in which agents author each
  kind and measure how often what they write fails to draw, then run the kinds agents
  get wrong and stop running those they reliably get right.
- **Derive the waiting banner from the page's open Ask.** Consider using the Ask's
  words when no explicit waiting detail is needed. **Unconfirmed:** try pages with
  several open Asks and an informational page before choosing how the banner
  explains who owes the next move. Keep explicit agent status available when the
  Ask alone does not explain the wait.

### Development velocity

- **Check what handing over on chosen tests costs.** Since 2026-10-04 a handover runs
  the tests the agent picks for its change, and the broad selection runs only at
  landing (`tests/AGENTS.md`, "Run what the change needs"). Before that, 25 of the
  200 pull-request `ci` runs that finished between 2026-10-02 22:00 and 2026-10-04
  ~19:00 UTC failed on tests. Compare the pull requests' test-failure rate since the
  change with that baseline, and weigh it against the local test time saved: the
  broad selection is about 3,700 s of test time on a CI runner. If the rate rose,
  look at which escapes a cheap fixed set of tests would have caught, and choose
  that set by measured catches per second rather than by kind.
- **Guard thread appearance on CI again.** The thread snapshot gate compares images
  on macOS only (`dev/leaf_dev/thread_snapshots.py`), so a pull request's Linux CI
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
- **Decide whether `leaf-dev` should draw charts.** `leaf-dev journey-chart` prints
  an `lf-chart` of the kept journey samples, so a reading needs no numbers copied
  into a page by hand. It is an experiment: the alternative is for the command to
  print the samples' rows and leave the chart to the agent writing the page. Keep it
  if it gets used for later readings; otherwise reduce it to the rows.
- **Consider bundling the browser runtime.** A navigation loads about 220 JS modules
  over HTTP/1.1's six connections. A prototype bundling `leaf.js` with esbuild cut a
  widgetless page from 217 requests to 38 and its open from 332–483 ms to 238–258 ms,
  roughly 10% of browser-test time. The bundle would hold `assets/runtime/` and Leaf's
  own packages; custom packages stay unbuilt and import only `/runtime/widget-api.js`,
  a bundle entry, which `page check` would then enforce, since any other runtime import
  loads a second runtime. **Unconfirmed:** it needs automatic rebuilds on preview, test
  and merge, since a committed bundle would conflict across concurrent runtime PRs.
  Untested alternative: `modulepreload` hints.

## Etc

Revisit these when their stated trigger becomes real; they are not an active queue.

### Product and harness ideas

- **Revisit where an abandoned comment's words come back.** A page comment closed
  with Escape keeps its words, and the next box `c` opens, such as a thread card's
  reply, offers them, since Leaf can't know exactly where the user last typed. That
  is deliberate; a better approach may tie the words to where they were written.
  Trigger: a user is surprised to find their words in an unrelated box.
- **Revisit a pin's icons if they read unclearly.** A pin shows the rail's outline
  icon in white on its fill, at 26px. A filled icon reads more clearly at that size,
  and needs no second copy — the same SVG with its fill set — but only an icon whose
  outline is a closed shape fills cleanly. Trigger: a user misreads what a pin holds.
- **Explore independent jobs.** Work out their identity, observer, continuation
  owner, and outcomes across background commands, delegates, and external waits.
  See the [Thread plan](notes/threads.md#independent-jobs-delegation-and-continuation).
- **Model how work breaks into pieces.** A task links only to its thread, widget or
  page. Most real work forms a fuzzy hierarchy: much of planning is breaking a goal into
  pieces, and the breakdown changes as the work teaches what the goal needs, with
  pieces split, merged, dropped or moved under another parent. Fixed trees, like Pi's
  owned subtasks or a tracker's parent and child tickets, are too brittle for that.
  Find a shape that holds a changing breakdown, and say what it means for the queues:
  whether a parent ends when its children do, and whose queue shows a child. Two links
  are already planned: none for a task answering the user's comment, and one back to
  the dispatcher for work handed to another session (step 7 of
  [What needs you](notes/what-needs-you/page.html#task-hierarchy)). Trigger: a page
  whose work the user wants to see broken down.
- **Tell the agent when to ask before ending its own task.** The agent ends its tasks
  itself, and asks first, with an Ask or a thread question, when the result needs the
  user's sign-off
  ([What needs you](notes/what-needs-you/page.html#task-done)). The shipped
  instructions don't yet say when that is. Trigger: an agent ends a task as done that
  the user wanted to see first.
- **Let the user edit items in the Questions panel.** The user's only edit today is Done
  on a task the agent put on them, so dropping a task, renaming it or ending one of the
  agent's means asking in a thread. Editing the row directly in the panel would record the user's change as
  their own move. Trigger: a user writes a comment only to close or adjust an item.
- **Name the record both queues share.** The page calls what's on the user Questions
  and what's on the agent Tasks, while the code, the event log, `leaf page state` and
  `leaf task open --on user` still call the shared record a task. "Task" also means
  the harness's unit of work, as in a task claim. Obligation, commitment and item are
  the candidates weighed
  ([What needs you](notes/what-needs-you/page.html#internal-name)). Trigger: the
  two meanings of task confuse an agent or a reader of the code.
- **Multiplayer:** let several users share a page, each recorded as themselves.
  Every browser event is `author: "user"` today, so the log cannot say who moved,
  commented or voted, and nothing records who has the page open. Claude Code
  Artifacts store a viewer id on each row and resolve names, faces and presence
  from the host. Settle user identity and how it reaches the append door before
  building a feed or presence on it.
- **Show which pane has focus, and move between panes by key.** A terminal marks
  its active pane and one key moves to the next. In a workspace today the arrow keys
  walk a side list, `a` reaches the next open Ask, and a pane body that scrolls is a
  Tab stop, but nothing marks the active pane and no key moves from one pane to the
  next. Pane focus belongs to the panes and the keyboard layer, not the Layout, so it
  works the same wherever panes stand. Draw it as a playground before building it.
  Trigger: a user loses track of the active pane, or tabs through a pane to reach the
  next one.
- **Expand everything waiting with a keypress.** A held notice, a collapsed summary,
  and a folded card or section each open one at a time, with Enter or Space on it,
  `g f` for a page's sections, or a `t` walk for a thread's held news. Nothing opens
  them all at once, yet a page-level key spent on that alone seems wasteful. Think
  about which surface should own it, such as one command on the panel. Trigger: a
  user steps through notices one by one to catch up.
- **#23 — Workspace persistence:** use repeated real tasks to decide whether
  users return and how much customization Leaf should own.
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
- **Favicon count:** keep a pending count only if it reads clearly at 16px.
- **Character bindings:** let users disable them when real use calls for it.
- **Authoring vocabulary:** add tabbed sections only when root and embedded
  placement cannot express a real page.
- **Replacement diffs and visual masks:** add them when repeated reviews need
  more than plain replacement and focused inspection.
- **Motion evidence:** define video, caption, and transcript handling when core
  gains durable video.
- **Revisit long-thread folding after using summaries.** If agent-written summaries
  leave users struggling with long histories or oversized messages, follow the
  [Thread plan](notes/threads.md#later-long-thread-reading).

### Implementation candidates

- **Consider moving the before/after reading out of the core.** How
  `runtime/image-difference.js` reads a pair (blocks, moves, outlines) is
  experimental and about 500 lines in the core runtime, consumed by `lf-shot`,
  `lf-visual-review` and `leaf-dev stills`. A package could own it, so the core keeps
  only what every page needs. Try it on non-Leaf captures first (another site, a
  terminal, a plot); where the capture is a browser's, recording each element's box
  beside the PNG would read moves exactly, as Percy's and SmartUI's layout modes do.
  Known gaps: a pane that scrolled within itself reads as scattered changes and moves
  rather than one region, a border that changed length draws a thin outline, and a
  changed 1440x900 pair costs about 40–70 ms on the main thread (8 ms before), which
  a worker would take off it.
- **Reduce plugin-update downloads by cleaning Git history.** Remove historical
  images and obsolete large JavaScript bundles while preserving current files.
  A disposable full-history rewrite saved about 27 MiB. Coordinate the rewrite
  across remote refs and local worktrees, retaining the commit mapping and testing
  that updates preserve active work without restoring the removed history.
- **Consider dragging thread cards and comment boxes.** Once both share placement,
  try temporary, passage-relative movement from a handle. Keep it only if scrolling,
  typing, and resizing stay predictable and the implementation stays simple.
- **Calibrate agent-driven UI diagnosis.** Try one known miss and one intentional or
  invalid control with a bounded explorer and cold user. The
  [quality brief](notes/agent-driven-ui-quality.md) also proposes a Tend acceptance-policy
  change; review that proposal with its owner before changing the policy.
- **Set interaction-trace privacy before sharing pages.** Define who can inspect
  traces, consent or opt-out, sensitive-field redaction (including passwords,
  pasted text, and selection), and retention/deletion for page-local files and
  hosted Workers Logs. Page-local traces currently record raw input for this
  single-user stage; the public site keeps interaction metadata only.
- **#6 — Codex supervision:** separate hosted and local turn supervision only
  if hosted delivery becomes a product priority; the App Server protocol is
  already shared.
- **#7 — Runtime fold tests:** add focused Node tests as rules change; extend
  `tests/runtime/dom.mjs` only when a test needs another module.
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
- **MCP Apps:** rebuild inline hosting as the direct-resource design when a host
  the user runs renders MCP Apps. See [notes/mcp-apps/PROJECT.md](notes/mcp-apps/PROJECT.md).
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
