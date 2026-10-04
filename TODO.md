# TODO

Priority runs from **Now** to **Next** to **Etc**. Themes group related work within
each priority; bullets are outcomes, not implementation plans. Linked notes hold the
evidence and detailed briefs. Numbered items keep the ids shared with `notes/`.
Completed work and rejected ideas live in git history or the relevant research note.
An item marked **Unconfirmed** rests on a reading nobody has run or a design nobody
has tried; settle that before building it.

## Now

### User experience

- **Make complete reading journeys feel coherent.** Audit a document, workspace,
  board or table, and populated thread in light and dark at wide and narrow
  widths. Fix recurring gaps in type, spacing, framing, controls, and responsive
  behavior.
- **Keep the Thread hierarchy clear.** Check context, search, filters, agent
  activity, selection, and reply editing in the implemented accordion.
- **Name a new Thread promptly everywhere.** A Claude Code page and an App Server
  carrier (leaf.page and `leaf codex start`) title a thread from its opening
  message in about 3 s (`thread_titles`). A Codex task Leaf reaches through `codex
  queue` still titles on the agent's reply; give it the same request, through
  `codex exec`. Worktrunk's `codex exec` command took 3.7–5 s and about 13k input
  tokens per title here, and it leaves the user's MCP servers on, which the App
  Server request turns off by name. A request at admission, as Claude Code's is,
  would serve every harness once the page server can reach each one's model.
- **Keep a long Thread's standing visible.** Summary checkpoints already condense
  older messages. Test a current one-line reading of what is decided and what remains
  open, distinct from a historical summary, and decide how a revision invalidates it.
  See the [Thread plan](notes/threads.md#current-standing).
- **Test annotation placement in context.** Compare a pinned marker card with a
  sparse left-comment layout on a document and a workspace. Keep full history and
  search in Threads and use Page Map on narrow pages; show only one margin treatment
  at a time.
- **Make the next move and its result apparent.** Play through `review-a-plan`,
  `triage-board`, `pr-walkthrough`, and `ship-review`; fix dead ends and moves whose
  result is hidden. Decide whether a page needs one progress reading across Asks,
  board work, and version approval. Test a concrete first task before changing the
  public home page's prompt.
- **#14 — [Verify the complete workspace keyboard and accessibility route](notes/workspace-followups.md#item-14).**
  Follow one task through reading, panes, comments, and Threads.

### Agent and author experience

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
- **#24 — Measure the fresh-reader review across pages.** The catalog's
  `dashboard/reader` context gives a fixed reader only the request and screenshots
  of a seeded count defect and a corrected count control. The narrow calibration
  scores count detection and false alarms separately from other page defects;
  it does not establish overall page acceptance. Measure
  whether authors invoke the review, its cost and what it catches across actual
  pages. Author delegation traces and independent judge cost are separate evidence.

### Prose

- **[Rewrite Leaf's prose for its readers](notes/prose-review.md).** The maintainer
  rewrite is written and awaits independent review and landing. Agent instructions are
  the next phase, scored with `evals/`. Site structure, UI vocabulary and example
  selection wait on the five decisions in the note. Judge each rewrite by reader
  usefulness and preserved behavior; word counts describe the cut, not its quality.

## Next

### User continuity and mobile access

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
  Threads and Approve off the row until it ends, Android's back gesture closes nothing
  (the Escape ladder could answer it), Draw mode blocks scrolling and zoom, and an
  `lf-draft` has no close that keeps the edit.
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
- **Decide whether a thread card may cover the margin rail.** A card beside its
  target starts right of the target's margin marker whenever the room past the marker
  still holds the card's minimum width (`comment-placement.js`, where `options` reads
  `margin`), so the marker stays visible. The card therefore opens well right of the
  text and narrower than it could be; starting it beside the text would cover the
  rail's markers for as long as it is open. Weigh that trade, then settle how Leaf
  states which elements a floating surface may cover. Today each placement names the
  boxes it keeps clear of (`clear`, `margin`) in its own code, so no element can declare
  that it may be covered, or must never be.

- **Give the phone banner one row.** Decided, not built
  ([plan](notes/chrome-and-covers.md)): one 53px row holding the status in words, cut
  short with an ellipsis, with a passing notice taking that slot for a few seconds;
  then Threads as an icon with its count; then More. Approve moves into More, which
  wears a dot while approval is open.
- **Recompose `alert-review` as a screen.** It is the worked workspace example, and at
  1200×900 `page check --render` advises that its detail pane runs 6890px past its
  region (nine Asks stacked in one scroller) and its queue 104px. A page a reader moves
  through rather than scrolls shows one alert's decision at a time; the shipped
  workspace examples are then held to the advice in `test_page_fixture_renders`, with
  `rust-sort`'s source pane the one reader allowed to scroll
  ([plan](notes/chrome-and-covers.md)).
- **Decide whether the desktop bottom bar goes.** Its key hints would move behind `?`
  and its status into the banner; the bar is how a desktop user learns the keys
  without asking, which is the trade to weigh ([plan](notes/chrome-and-covers.md)).
- **Align a widget's column with the text's measure.** `lf-options` cards run 1294px
  beside 720px paragraphs in a wide panel, because text keeps the measure (`theme.css`,
  `:where(p, li, …) { max-inline-size: var(--col) }`) and a widget without `x-space`
  takes the whole flow. Declaring the existing column allocation on `lf-options` is not
  enough on its own: `schema.py` allows `x-space` only `wide` and `available`, and
  `[data-lf-space="column"]` centres its box (`margin-inline: auto`) while text in a
  wide flow starts at the left edge. The column allocation and the text measure have to
  align the same way first; start-aligned in any flow wider than the column is the
  reading that matches the prose.
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
  with the agent-usability baseline (#19), by extending the
  [arrangement eval](notes/arrangement-eval/README.md).
- **Fit an Ask and what it turns on into one window.** `a` puts an Ask's heading at
  the top, and `authoring-asks.md` has the `lf-ask` hold its premise and evidence,
  but stacked they often outrun the window: on a findings page one Ask with its
  claim, figure and options took 760px of a 900px window, and `alert-review`'s 466px option lists
  leave no room for the facts and evidence each one turns on, which that example
  still keeps above its Asks. A page-CSS prototype that set the options in a sticky
  14–18rem track beside the premise and figure showed the question, claim, figure
  and every option in one window at 900 and 1200px, and kept the options in view
  while the user scrolled a 700px demo below. Unsettled: a breakout block (a
  `data-width="available"` specimen) runs under the sticky track, the focus ring
  spans the whole Ask, a figure in the narrower track shrinks its text, and the
  width at which it stacks. A further step is selection and detail, where the
  focused option chooses which evidence the wide track shows; focus rather than
  hover, so it has a keyboard route. Try both as playground presets over
  `alert-review` and a findings page before making either the wide-window form of
  `lf-ask`, which admits no class today, so a page can only opt in by id. Extending
  `arrivalRegion`'s widening to declared Asks helps only where the run-up above an
  Ask already fits.
- **Layout values that wait for a task:** a selection-and-detail component whose phone
  form shows one side at a time; canvas regions, whose reading position is
  two-dimensional; slides as a presentation of `lf-tabs`.
- **Place the comment composer correctly on a page that sets a margin on `html`.**
  With `html { margin-left: 40px }` the floating composer lands 40px left of its lane
  and overlaps the element it comments on, on any page wide enough to place it
  beside its target. The reference rect handed to Floating UI (`composing/surface.js`,
  `placeFab`) and the fixed bar disagree by the root's margin.
  `test_an_aimed_comment_keeps_its_place_with_the_asks_drawer_open` reproduces it at
  1200px with the drawer closed and runs at 900px, where the composer goes above or
  below, until this is fixed.
- **Land a sent comment's thread where its comment box stood.** A comment typed beside
  an option near the top of the window (the box standing just under the banner) came
  back as a margin card level with the option, about 330px lower, so the words the
  user just wrote jump across the page on send. The send's carry transition
  (`composing/surface.js`, the card placement in `margin-projection.js`) animates the
  jump rather than avoiding it. The card and the box choose their places by different
  rules: the box from the target and the room at the moment it opened, the card from the
  margin's own layout. Either the card opens where the box stood, or the box opens where
  the card will stand.
- **Unconfirmed: scrolling a live sample sometimes sticks.** A user reported it
  while a sample still scrolled inside a fixed-height frame, with no reproduction.
  The frame now takes its page's height, so nothing scrolls inside it; check that the
  report no longer reproduces once the scrolling changes land.

### Layout stability

Boxes that still move without input, which the "Stability" rule in
`skills/leaf/assets/AGENTS.md` forbids. `tests/known_widget_findings.py` lists each widget
that changes size after first paint, with its cause.

- **Draw the playground at its final size from first paint.** `lf-playground`,
  `lf-playground-control`, `-output`, `-preview` and `-value` are `keeps-first-box`
  findings: the module builds each control's inputs and the words of the instruction it
  copies after first paint. Put each control's initial value and text in the authored markup, so
  the module fills in what is there rather than adding it. Check first how values a
  viewer restores from the tab's storage change the size, since markup carries only
  the authored defaults.
- **Size the activity feed and text documents at first paint.** `lf-activity` draws the
  log's history and `lf-text-document` its bound source's value, and both arrive with
  the first state answer, after first paint. Serving that state inside the page does
  not work: modules run after first paint, and a page revision is immutable while the
  log keeps changing. Follow #1566's Command Hub pattern instead: draw a summary whose
  size is known at first paint, open the rows from it, and hold later growth with
  `HeldReading` (`runtime/thread/held-news.js`) while it would be seen. Check first
  whether a text document, which the reader came to read, can stand behind a summary.
- **Decide the contents' form before first paint.** `lf-toc` changes size because the
  margin pass decides after first paint whether it is the fixed map in the margin or
  the outline in the flow (`data-lf-margin`, `margin-layout.js`), from the room
  it measures at that point. A held summary does not answer that cause. Check first whether a
  container or media query on the space beside the column can make the same decision
  in CSS.
- **Find a first-paint fix for the gallery's margin entry and for targeting.**
  `lf-margin-entry-gallery` wraps words whose height follows the viewer's fonts (22px
  to 45px taller on CI's Linux than on macOS), so no height its examples state holds
  everywhere. `lf-targeting` has no recorded cause; read `lf-targeting.js` for what it
  builds after first paint before choosing an approach.
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
- **Let a queue group its items.** The author sorted the items into merge, close,
  design and FYI, but `lf-tabs` takes only `lf-tab` members, so the page showed 21
  undifferentiated rows. A side list could take group headings between its items,
  skipped by the arrow walk.
- **Put the open item first on a phone.** At 390px the stacked list comes before any
  item, so 20 rows fill two screens before the first one.

### Recorded interaction review

- **Bring richer trace inspection into Leaf's commentable timeline.** Review a
  recording through its actual actions, timestamps and captured frames, with
  playback, scrubbing, Before/Action/After snapshots, source, console and network
  context. Keep comments attached to the immutable recording and action or frame;
  opening a thread restores that moment. Reuse Playwright's capture and inspection
  capabilities, and keep a direct link to its full viewer beside the Leaf timeline.

### The agent's text interface

- **Keep a blocked stop from hiding the agent's answer.** When Leaf's Stop hook blocks
  a stop, the agent writes one more message, and where the host shows only the last
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
  than adding readings or widths to the check. In `r3-main-0feb` every one of the 36
  runs passed the gate, yet the judge still found tiny text at 900px and phone
  defects (`notes/arrangement-eval/`).
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

## Etc

Revisit these when their stated trigger becomes real; they are not an active queue.

### Product and host ideas

- **Revisit a pin's icons if they read unclearly.** A pin shows the rail's outline
  icon in white on its fill, at 26px. A filled icon reads more clearly at that size,
  and needs no second copy — the same SVG with its fill set — but only an icon whose
  outline is a closed shape fills cleanly. Trigger: a user misreads what a pin holds.
- **Explore independent jobs.** Work out their identity, observer, continuation
  owner, and outcomes across background commands, delegates, and external waits.
  See the [Thread plan](notes/threads.md#independent-jobs-delegation-and-continuation).
- **Multiplayer:** let several users share a page, each recorded as themselves.
  Every browser event is `author: "user"` today, so the log cannot say who moved,
  commented or voted, and nothing records who has the page open. Claude Code
  Artifacts store a viewer id on each row and resolve names, faces and presence
  from the host. Settle user identity and how it reaches the append door before
  building a feed or presence on it.
- **#23 — Workspace persistence:** use repeated real tasks to decide whether
  users return and how much customization Leaf should own.
- **Visual review beside Leaf:** coordinate a real browser target through the host
  when review work needs it; expand inspection only when focused workspaces fail a
  real task.
- **Other hosts:** add a blocking `leaf wait` route when another agent host needs
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
  the current dialog and popover handlers. See the
  [dependency survey](notes/dependency-survey.md).
- **MCP Apps:** rebuild inline hosting as the direct-resource design when a host
  the user runs renders MCP Apps. See [notes/mcp-apps/PROJECT.md](notes/mcp-apps/PROJECT.md).
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
