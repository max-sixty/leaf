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
  and remaining undersized touch targets. Hover-only today: why Approve version is
  disabled, and "Press z" once approved; a reaction's word before it is sent; a margin
  marker's label and its status (Sent, Stalled); the diff's line "+"; and the
  latest-edit error, a dead passage's reason, a disabled More entry's reason, and the
  compare state. A finger also lacks exits a key has: a mode's or search's steps take
  Threads and Approve off the row until it ends, Android's back gesture closes nothing
  (the Escape ladder could answer it), Draw mode blocks scrolling and zoom, and an
  `lf-draft` has no close that keeps the edit.
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

- **Stack covers of stated height, and keep Layouts out of widgets.** Give the banner a
  height CSS computes, give every sticky cover a stated height added into `--lf-top`,
  delete the measured-header machinery, and state the hit floor as padding. Then decide
  whether a workspace keeps panes that scroll on their own or its regions stick to the
  root scroller, and drop the bottom bar ([plan](notes/chrome-and-covers.md)).
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
  needs it; a workspace page's own pane grid stays plain CSS. Option E of the
  [chrome plan](notes/chrome-and-covers.md) settles it, since a sticky region works at
  any depth with no scrolling ancestor.
- **Seat a suggestion's pair of pins on a phone.** A pin now takes room beside its
  target that covers no words (`pinSpot`), which clears single markers on most pages,
  but under a finger Accept and Reject together are a 96×44px pair: that needs a line
  ending 100px short on the run's last line, 44px from that line to the next block, or
  the empty end of a neighbouring block's line within reach, such as a short heading
  just above. At 390px, 3 of the 7 shipped suggestions find no such room and stay over
  their words (the feature gallery's replace and insert, release-notes' API
  deletion). Folding the pair into one marker that opens Accept and Reject, only where
  the pair has no room, is the nearest design; it costs a second tap. Hiding the annotations (`o`, or Hide annotations in More under
  a finger) stays the escape.
- **Make the outcome checks the gate.** `page check` passed a page that scrolled
  sideways at 520px. Check sideways scroll and leaking minimums (a box whose content,
  not its declared minimum, sets its holder's floor) across swept widths. The corpus
  (`leaf-dev corpus`) sets every example's body in one column page, so only the
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

### The agent's text interface

- **Wake the agent only for input that changes what it owes.** `leaf wait` ends
  on every event `requires_agent_attention` admits, so input that asks nothing
  still costs the agent a turn. Comments, replies and a move that finishes an Ask
  owe an answer; `done`, `report` and `error` owe work; a move that answers no Ask
  owes nothing but carries a receipt that reads Sent until it is picked up. Only
  `resolve`, `unresolve` and `undo` owe nothing and carry no receipt, and each can
  still change what the agent owes: a resolve withdraws a pending answer and the
  work begun on it, an unresolve can reopen an unanswered message, and an undo can
  withdraw a Done or a pick the agent is acting on. So the test is whether the
  event changes the page's obligations or claims, not its kind. In this machine's
  page logs from the last 30 days, 40 of 204 deliveries held only resolves, and
  32 of those resolves closed a thread whose last word was already the agent's.
- **Take every render-check reading at every width the check renders.** The check
  lays the page out at 1200px and 540px and sweeps it from 360px to 1920px
  (`render_gate/version.py`, `readings.py`), but reads drawing label size only at
  the desktop width (`shrunk_label_advice`), though a narrower window scales a
  drawing further still. Tiny text at 900px and on a phone recurs in the judge's
  reasons in the arrangement eval (`notes/arrangement-eval/`, `r3-main-0feb`). Take
  each reading the sweep can take at every swept
  width, and report each fault at the narrowest width it starts, as
  `swept_overflow` does for sideways overflow. The readings stay advice: which
  widths a page answers for is the author's call.
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
  `triage-board` and 12.6 s on the corpus, measured by tracing the check's passes.
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
  and the host waits for it. In a session holding no page it costs about 50ms
  warm on an idle machine (2.5s cold, after a plugin update leaves uv to sync):
  uv adds about 15ms, Python startup about 10ms, and importing the CLI about
  15ms. A session holding a page adds about 0.1s to import page reading and
  read each page's state, so its prompt and Stop hooks cost about 0.15s. That cost is why the `PostToolUse`
  registration keeps its `if` prefilter, and it limits what else hooks can
  carry. Consider a `leaf` filter in front of every tool-result hook, so Leaf
  can answer more events itself. Rewriting the hook path in a compiled language
  is the further step if that is not enough.
- **Invoker commands:** revisit when the browser support Leaf needs can replace
  the current dialog and popover handlers. See the
  [dependency survey](notes/dependency-survey.md).
- **MCP Apps:** rebuild inline hosting as the direct-resource design when a host
  the user runs renders MCP Apps. See [notes/mcp-apps/PROJECT.md](notes/mcp-apps/PROJECT.md).
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
