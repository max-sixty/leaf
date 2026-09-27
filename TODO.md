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

- **Run the first agent-usability baseline, including #19.** Execute the
  [cold-authoring, reading-parity, and resume cases](notes/agent-usability-evals.md#first-executable-slice).
  Compare authoring and a feedback cycle with plain HTML before improving Leaf's
  authoring guidance. Include the simplified delivery-receipt loop; the focused
  receipt tests do not replace this baseline. Use observed failures to choose
  new reading interfaces;
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
  and remaining undersized touch targets.
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
- **Cap a widget's minimum by the box that holds it.** lf-board's `min-inline-size` is
  capped by the shell (`100cqi`), so inside a framed specimen or a column on a phone it
  runs past its holder: the feature gallery and how-it-works each zero it by hand.
  Leaf's framed holders (specimen, pane, tab, card) could become inline-size
  containers.
- **Give the workspace Layout a column setting.** Each workspace page writes the same
  four-declaration pane grid that `columns="3fr 2fr"` used to say; a token such as
  `--layout-columns: 3fr 2fr`, stacking below 720px, would carry it. A bounded box of
  panes outside a workspace also restates the Layout's pane scrolling (the feature
  gallery), which could key on `--lf-held` instead.
- **Keep a held workspace's panes, not its header, in the window.** At 1000×800
  alert-review's header and footer leave its detail pane about 370px, so the first Ask
  option is cut by the footer; rust-sort's film controls fall under the fold at 1200px.
- **Give a held workspace's overflow its end room.** A held workspace is exactly the
  window's height, and only its body's direct cells pass that height on: a pane inside a
  section cell flows, overflows `main`, and its end scrolls under the bottom band with no
  end room after it (`test_a_held_workspace_that_overflows_scrolls_its_end_clear_of_the_band`
  is xfail on it). The body could scroll as a whole where a cell does not bound itself.
- **Finish contract 8's margins.** A declared rail (`data-rail`) has no floor, so on a
  phone it leaves a 295px column. The contents map and other sidebars switch into the
  margin at different widths (848px against 1296px), which leaves an empty in-flow
  sidebar and a gap under the header between them (the docs package carries a
  workaround). Without the default rail, markers pin between 880px and 959px where they
  used to stand in the rail. The render gate reads the wide page at 1200px, below the
  1296px and 1536px a sidebar and a sidenote now need, so it never sees either in the
  margin (`test_the_render_viewport_is_wide_enough_to_have_margins` is xfail on it).
  With nothing claiming the rail's room, a centred column at 1200px leaves 216px on its
  right, too little for the comment bar, so it drops below the passage on every column
  page; there its width depends on what the field held when the room was measured
  (`composing/surface.js`, `setWidth`), so one draft is laid out differently in two tabs.
- **Make the outcome checks the gate.** `version check` passed a page that scrolled
  sideways at 520px. Check sideways scroll and leaking minimums (a box whose content,
  not its declared minimum, sets its holder's floor) across swept widths. The corpus
  (`scripts/corpus.py`) sets every example's body in one column page, so its sweeps
  never read a sidebar, workspace or wide example in its own Layout.
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
- **Unconfirmed: scrolling a live specimen sometimes sticks.** A user reported it
  while a specimen still scrolled inside a fixed-height frame, with no reproduction.
  The frame now takes its page's height, so nothing scrolls inside it; check that the
  report no longer reproduces once the scrolling changes land.

### The agent's text interface

- **Read the render checks after handover.** `version check --render` blocks the
  agent for the whole browser pass, so quick pages skip it and get none of its
  advice. Run the render readings on the server when a version goes live and
  deliver the findings through `leaf wait`: the agent hands the page over at once
  and refines it if a reading warrants, while a failure still blocks a record's
  stamp. **Unconfirmed:** measure how long the pass takes on a typical page, and
  whether agents act on findings that arrive after handover, before building it.
- **Scale a drawing by the box it was drawn in.** On replay, scale the strokes by
  the anchored element's size over the recorded `box`, so a mark stays on its
  element in a narrower window; reflowed text still moves under it. Verify replay
  at different widths and keep that limitation explicit.
- **Record the user's view beside `viewed`.** Add the window size, colour scheme
  and revision a visible tab reports to the presence reading, and document them.
  **Unconfirmed:** establish whether the missing view causes an agent failure in
  the agent-usability baseline above before adding fields to the interface.
- **Derive the waiting banner from the page's open Ask.** Consider using the Ask's
  words when no explicit waiting detail is needed. **Unconfirmed:** try pages with
  several open Asks and an informational page before choosing how the banner
  explains who owes the next move. Keep explicit agent status available when the
  Ask alone does not explain the wait.
- **Decide whether requests earn their weight.** A request (`x-request`, `leaf
  receipt`) is a non-undoable one-shot operation the user asks the host to run, with
  one pending attempt per control and a `succeeded`/`failed` receipt. Leaf never
  runs it, and a receipt carries no structured result. Its users are Command Hub's
  `lf-operations`, monitoring's `lf-release-actions` and the developer gallery's
  `lf-job-requests`, none backed by a real integration, while the lifecycle reaches
  `requests.py`, workflows, Asks, admission, the runtime's pending model and margin,
  and the Codex adapter's failure receipts. Once the Command Hub redesign settles
  whether its operations stay, either remove requests and recast the remaining
  operations as Asks, or keep them and cut what only the gallery uses: projected
  holders (`records`, one seat per data row). Kept requests also need one owner for
  whether a seat is open, which `application.ts`, `widget-controller.js`,
  `application.js` and `request-elements.js` each restate.

### Shared definitions

- **Re-address resource references in one pass.** Capture, delivery and export share
  one CSS reference walker (#1217), but `http.py` still rescopes delivered bytes with
  regexes, `media.js` spells a constant in pieces to get past that pass, and a page's
  head is composed in three places. One `rebase_document(source, address)`, with an
  import map for layer JavaScript, would delete the regex scopers.
- **Ask once whether the page has caught up with a reading.** `tests/render_harness.py`
  `told()` waits for `data-lf-reading` to match the server's reading, and the `data`
  and `log` stages of the runtime's `pageReadiness` (#1250) answer the same question.
- **Call a thread's identity its id in Python.** The runtime keys threads on the
  served `id` (#1260), but Python still names that identity a root (`thread_roots`,
  `FrozenThreadReading.roots`), though a thread that lost its opening message has a
  root that differs from its id.

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
- **Decide whether an exported page carries its threads.** `leaf version
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

- **Write the unresolved-gesture ledger as one state machine.** `application.ts`
  (`accept`, `accountPresented`), `application.js` (`releasableEntries`) and
  `pending/model.js` track a gesture through five flags, and each writes its own rule
  for when an action leaves the ledger. Nothing
  has drifted and this is the hottest race path, so take it when a change has to touch
  the ledger anyway.
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
