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
  behavior. Set one focus-ring weight for every keyboard target.
- **Keep the Thread hierarchy clear.** Check context, search, filters, agent
  activity, selection, and reply editing in the implemented accordion.
- **Name a new Thread promptly.** Generate a short title from the first user
  message with a lightweight model request that excludes the full agent context.
  Measure the request's input tokens and latency; keep the subdued pulsing ellipsis
  until the title arrives.
- **Keep a long Thread's standing visible.** Let the agent maintain one line at the
  head of a Thread saying what is decided and what remains open, so a user
  returning to a long discussion knows where it stands before reading it. Decide
  whether this is a summary checkpoint that covers the whole Thread or a separate
  reading, and how it goes stale.
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
  cycle with plain HTML before improving Leaf's authoring guidance;
  **#20** then [teaches the compositions that prove useful](notes/workspace-followups.md#item-20),
  including how authors discover diagram comparison suggestions.
- **Keep agent activity intelligible throughout a task.** Run the
  [status evaluations](notes/user-feedback-responsiveness.md) for delivery,
  multi-step work, and delegation. Show the plan as well as the current step;
  check that the hosted website agent's status is readable without delaying its
  reply. Keep delegated work visible while its watcher is live.

## Next

### User continuity and mobile access

- **Verify the native phone reading journey.** Check the explicit selection-to-comment
  handoff and reproduce the interactive-reply crash on a real iPhone. Browser emulation
  covers element targeting, commenting, passage geometry, and viewport sizing, but cannot
  show the native selection menu or software keyboard.
- **Finish what a phone user still cannot reach.** Give touch users visible passage
  threads, and remove keyboard-only hints, hover-only reasons, clipped diagram content,
  and remaining undersized touch targets. Undo (`z`) and Draw mode (`w`) have no route
  under a finger; `o` and `s` have one in the banner's More.
- **Take the layout readings across widths.** The render check renders each page at
  1200px and 540px and sweeps sideways overflow from 360px to 1200px, but it reads a
  drawing's label size on the settled 1200px page only, and nothing yet reads an Ask
  below its pane's first screen ([#19](notes/workspace-followups.md#item-19)). The
  arrangement eval's pages failed at 900px and on a phone in both ways. Take both
  readings across widths, phones included.
- **Give the thread panel's touch grip its own space.** Reserve room for the grip
  and collapse inactive reply controls if more thread cards should fit.

### Layout

The page arranges itself in CSS, starting from the Layout classes
(`skills/leaf/assets/layouts.css`), and Leaf keeps the contracts where pages, widgets
and its chrome coordinate.

- **Let a page restyle Leaf's chrome on purpose.** A page's rules reach a widget's
  controls when they name the widget (`runtime/page-sheets.js`), but `chrome.css` is
  unlayered and adopted after the page's sheets, so a page rule naming a chrome class
  wins only by out-weighing the chrome's own selector. Choose the deliberate route for
  the chrome — tokens it reads, named parts, or a layer the page ranks above — so a page
  can change the thread panel's format or hide one surface where it needs to.
- **Give the workspace Layout a column setting.** Each workspace page writes the same
  four-declaration pane grid that `columns="3fr 2fr"` used to say; a token such as
  `--layout-columns: 3fr 2fr`, stacking below 720px, would carry it. A bounded box of
  panes outside a workspace also restates the Layout's pane scrolling (the feature
  gallery), which could key on `--lf-held` instead.
- **Place markers so they cover less without losing what they track.** Where no rail
  stands, a marker pins inside its block's top-right corner and covers the end of the
  block's first line. On a 390px phone an Ask's pin covers the end of its question's
  heading, and a blind judge named that in 24 of 34 arrangement-eval judgments. A
  marker is an overlay, so the answer cannot reserve room, pad a block, or move text
  when a marker comes or goes (`skills/leaf/assets/AGENTS.md`, "Space and
  scrolling"). A better place must still sit at its own target and not a neighbour's,
  hold still as the page scrolls and reflows, stay off the block's controls, and work
  where the target is inside a pane that scrolls on its own. Hiding the annotations
  (`o`, or Hide annotations in More under a finger) stays the escape.
- **Give a declared rail a floor.** `data-rail="right"` makes the shell give up the
  rail's width at every width, so on a phone it leaves a 295px column. The margin pass
  admits residents by measuring the room they leave (`settleResidency`), which a rail
  the shell has already reserved never fails.
- **Make the outcome checks the gate.** `page check` passed a page that scrolled
  sideways at 520px. Check sideways scroll and leaking minimums (a box whose content,
  not its declared minimum, sets its holder's floor) across swept widths. The corpus
  (`scripts/corpus.py`) sets every example's body in one column page, so only the
  nightly `test_page_fixture_renders` reads a sidebar, workspace or wide example in its
  own Layout.
- **Offer the Page Map with the first paint.** The margin pass marks where markers are
  pins (`data-lf-pins`), and the banner's Map toggle follows it, so on a phone the
  toggle appears one pass after the banner rather than with it.
- **Test the Layouts on agents.** Give fresh agents tasks across the Layouts, then ask
  them to revise the results: turn a report into a report with live status while
  keeping its comments. They hold if revisions happen by ordinary composition. Include
  a cold agent asked for "a dashboard", the likeliest trigger for over-tiling. Run it
  with the agent-usability baseline (#19), by extending the
  [arrangement eval](notes/arrangement-eval/README.md).
- **Balance a tile row.** `.layout-tiles` wraps four metrics 3 + 1 where four don't
  fit (live-progress at 480–647px), as `lf-grid` did.
- **Layout values that wait for a task:** a selection-and-detail component whose phone
  form shows one side at a time; canvas regions, whose reading position is
  two-dimensional; slides as a presentation of `lf-tabs`.
- **Place the comment composer correctly on a page that sets a margin on `html`.**
  With `html { margin-left: 40px }` the floating composer lands 40px left of its lane
  and overlaps the element it comments on, on any page wide enough to place it
  beside its target. The reference rect handed to Floating UI (`composing/surface.js`,
  `placeFab`) and the fixed bar disagree by the root's margin.
  `test_an_aimed_comment_keeps_its_place_with_the_asks_tray_open` reproduces it at
  1200px with the tray closed and runs at 900px, where the composer goes above or
  below, until this is fixed.
- **Decide whether the shortcut line should wrap on a narrow window.** Below about
  390px with a fine pointer, the resting line wraps to a second row
  (`keyboard/shortcut-bar.js`, `chrome.css`), which stands about 31px over the page
  beyond the band the page reserves. The alternative is truncating the resting line
  to one row. A key sequence and the shelf must still wrap, so truncating brings back
  a one-row mode beside them, and it has to keep More, which sits last, from being
  cut first.
- **Unconfirmed: scrolling a live sample sometimes sticks.** A user reported it
  while a sample still scrolled inside a fixed-height frame, with no reproduction.
  The frame now takes its page's height, so nothing scrolls inside it; check that the
  report no longer reproduces once the scrolling changes land.

### The agent's text interface

- **Read the render checks after handover.** `page check --render` blocks the
  agent for the whole browser pass, so quick pages skip it and get none of its
  advice. Run the render readings on the server when a version goes live and
  deliver the findings through `leaf wait`: the agent hands the page over at once
  and refines it if a reading warrants, while a failure still blocks a record's
  stamp. **Unconfirmed:** measure how long the pass takes on a typical page, and
  whether agents act on findings that arrive after handover, before building it.
- **Consider loading a page once per render check.** `page check --render` loads
  the page afresh for each of its four passes, including dark mode and the narrow
  viewport. Switching those in place would save at most about 1.4 s on
  `triage-board` and 12.6 s on the corpus, measured with `leaf-dev bench-check`.
  The price is that dark mode and the narrow width would no longer be checked from
  a fresh start. Decide whether that coverage is worth the time before building it.
- **Scale a drawing by the box it was drawn in.** On replay, scale the strokes by
  the anchored element's size over the recorded `box`, so a mark stays on its
  element in a narrower window; reflowed text still moves under it. Verify replay
  at different widths and keep that limitation explicit.
- **Record the user's view beside `viewed`.** Add the window size, colour scheme
  and revision a visible tab reports to the presence reading, and document them.
  **Unconfirmed:** in the first agent-usability baseline the missing view caused no
  failure: asked which tab the user had open, every agent said the page files don't
  record it. Build this when a task needs the user's view.
- **Derive the waiting banner from the page's open Ask.** Consider using the Ask's
  words when no explicit waiting detail is needed. **Unconfirmed:** try pages with
  several open Asks and an informational page before choosing how the banner
  explains who owes the next move. Keep explicit agent status available when the
  Ask alone does not explain the wait.

### Shared definitions

- **Keep the rest of the runtime's apparatus out of authored structure.** Two
  generated elements still stand among the page's own: `anchor-controls.js` puts a
  `span.lf-visual-actions` after each drawing that takes visual comments, and
  `presentation.js` puts a hidden `span.lf-external-note` after each external link.
  Each changes which of its parent's children is last and what follows the drawing
  or link, so page rules such as `:last-child` or `svg + p` stop matching. The
  external note can move to the chrome and be named through
  `ariaDescribedByElements`, as the comment note is named through
  `ariaDetailsElements`. The visual actions are Tab stops placed after their drawing
  so Tab reaches them there, so they need a keyboard route that does not depend on
  where they stand in the document.

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
- **#22 — MCP workspace hosting:** compare an iframe, a constrained host, and
  browser handoff when an inline-hosting task calls for it. See the
  [research brief](notes/workspace-followups.md#item-22).
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
- **A cheap `leaf hook`:** every hook Leaf registers pays `uv run leaf hook`,
  about 0.3–0.5s warm and 2.5s cold, and the host waits for it. That cost is why
  the `PostToolUse` registration keeps its `if` prefilter, and it limits what
  else hooks can carry. Most of the warm time is Python startup and imports:
  `leaf.hooks` alone pulls in `delivery`, `event_contracts` and
  `anchor_capture`, about 120ms. Get the hook path off those imports, then consider a `leaf` filter in
  front of every tool-result hook, so Leaf can answer more events itself.
  Rewriting the hook path in a compiled language is the further step if that
  is not enough.
- **Invoker commands:** revisit when the browser support Leaf needs can replace
  the current dialog and popover handlers. See the
  [dependency survey](notes/dependency-survey.md).
- **MCP page ports:** test wildcard-port `frame_domains` in a host before replacing
  `/p/<capability>` multiplexing. See the
  [dependency survey](notes/dependency-survey.md).
- **Direct MCP bundle:** make evaluation-order faults fail visibly if the
  experimental bundle becomes a supported path.
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
