# TODO

Priority runs from **Now** to **Next** to **Etc**. Themes group related work within
each priority; bullets are outcomes, not implementation plans. Linked notes hold the
evidence and detailed briefs. Numbered items keep the ids shared with `notes/`.
Completed work and rejected ideas live in git history or the relevant research note.
An item marked **Unconfirmed** rests on a reading nobody has run or a design nobody
has tried; settle that before building it.

## Now

### Reader experience

- **Make complete reading journeys feel coherent.** Audit a document, workspace,
  board or table, and populated conversation in light and dark at wide and narrow
  widths. Fix recurring gaps in type, spacing, framing, controls, and responsive
  behavior. Set one focus-ring weight for every keyboard target.
- **Give conversations a stable hierarchy.** Follow the separate
  [thread plans](notes/threads.md): make reader attention explicit, prototype compact
  navigation, then fold long histories. Keep thread context, search, filters, agent
  activity, selection, and reply editing clear.
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
  authoring guidance. Use observed failures to choose new reading interfaces;
  **#20** then [teaches the compositions that prove useful](notes/workspace-followups.md#item-20).
- **Keep agent activity intelligible throughout a task.** Run the
  [status evaluations](notes/reader-feedback-responsiveness.md) for delivery,
  multi-step work, and delegation. Show the plan as well as the current step;
  check that the hosted website agent's status is readable without delaying its
  reply. Keep delegated work visible while its watcher is live.
- **Settle who owes the next move.** Make the banner, margin, and Threads agree
  when several subject claims stand or an agent question is followed by another
  agent turn. Seed that thread shape before changing its projection; choose one
  colour scheme for reader, agent, and unclaimed work.

## Next

### Reader continuity and mobile access

- **#11 — [Let newer navigation win over revision restoration](notes/workspace-followups.md#item-11).**
  Preserve input made while a revision activates.
- **Verify the native phone reading journey.** Check the explicit selection-to-comment
  handoff and reproduce the interactive-reply crash on a real iPhone. Browser emulation
  covers element targeting, commenting, passage geometry, and viewport sizing, but cannot
  show the native selection menu or software keyboard.
- **Finish what a phone reader still cannot reach.** Give touch readers visible passage
  threads, and remove keyboard-only hints, hover-only reasons, clipped diagram content,
  and remaining undersized touch targets.
- **Give the thread panel's touch grip its own space.** Reserve room for the grip
  and collapse inactive reply controls if more thread cards should fit.
- **Keep wrapped inline code inside the column.** `theme.css` gives inline `code`
  `box-decoration-break: clone`, which pads every wrapped fragment and pushes it
  about 4px past the text column; `slice` keeps it inside, with a squared-off end
  where a code span breaks. A visual call.

### The agent's text interface

- **Send each `handling` clause once per batch.** Each delivered event carries its
  clauses' full text, so ten plain comments repeat one 493-character instruction
  ten times. List each distinct clause once per batch and have each event name the
  ones that apply. **Unconfirmed:** no agent run shows a clause named by reference
  is followed as reliably as one printed on its event.
- **Scale a drawing by the box it was drawn in.** On replay, scale the strokes by
  the anchored element's size over the recorded `box`, so a mark stays on its
  element in a narrower window; reflowed text still moves under it.
- **Record the reader's view beside `viewed`.** Add the window size, colour scheme
  and revision a visible tab reports to the presence reading, and document them.
  **Unconfirmed:** no agent failure yet shows the agent needs them; the
  agent-usability baseline above should.
- **Cut the Claude Code loop to one command per batch.** Advance the cursor when
  `leaf wait` prints, mark a delivered move Working when it enters the turn, and
  default the handoff banner to the page's open Ask, so `ack`, `delivery claim` and
  `status waiting` leave the ordinary batch. **Unconfirmed:** advancing on print
  gives up what `ack` guards today: a `leaf wait` output that was truncated or
  lost before it reached the agent is delivered again (`event-batches.md`).
- **Shorten the delivery id.** It is still a 36-character UUID, beside 8-character
  event ids. Codex names its queue files with it and `delivery_path` requires the
  UUID form, so both change together, with a collision check like event ids have.
  **Unconfirmed:** it saves under 30 characters a batch, which may not be worth it.

## Etc

Revisit these when their stated trigger becomes real; they are not an active queue.

### Product and host ideas

- **#23 — Workspace persistence:** use repeated real tasks to decide whether
  readers return and how much customization Leaf should own.
- **Visual review beside Leaf:** coordinate a real browser target through the host
  when review work needs it; expand inspection only when focused workspaces fail a
  real task.
- **Other hosts:** add a blocking `leaf wait` route when another agent host needs
  foreground handoff.
- **#22 — MCP workspace hosting:** compare an iframe, a constrained host, and
  browser handoff when an inline-hosting task calls for it. See the
  [research brief](notes/workspace-followups.md#item-22).
- **Favicon count:** keep a pending count only if it reads clearly at 16px.
- **Character bindings:** let readers disable them when real use calls for it.
- **Authoring vocabulary:** add tabbed sections only when root and embedded
  placement cannot express a real page.
- **Replacement diffs and visual masks:** add them when repeated reviews need
  more than plain replacement and focused inspection.
- **Motion evidence:** define video, caption, and transcript handling when core
  gains durable video.

### Implementation candidates

- **#6 — Codex supervision:** separate hosted and local turn supervision only
  if hosted delivery becomes a product priority; the App Server protocol is
  already shared.
- **#7 — Runtime fold tests:** add focused Node tests as rules change; extend
  `tests/runtime/dom.mjs` only when a test needs another module.
- **Claude Code tool observation:** consider a cheap hook for sessions holding
  pages if status evaluations show that agent declarations are insufficient.
- **#28 — Reading-column grid:** replace `main`'s `left` offset if panel
  movement causes scroll or maintenance trouble; current measured layouts held
  the reader's place.
- **CSS cascade layers:** isolate Leaf chrome from page CSS before reconsidering
  `@layer`; the earlier trial changed chrome styling. See the
  [dependency survey](notes/dependency-survey.md).
- **Invoker commands:** revisit when the browser support Leaf needs can replace
  the current dialog and popover handlers. See the
  [dependency survey](notes/dependency-survey.md).
- **MCP page ports:** test wildcard-port `frame_domains` in a host before replacing
  `/p/<capability>` multiplexing. See the
  [dependency survey](notes/dependency-survey.md).
- **Direct MCP bundle:** make evaluation-order faults fail visibly if the
  experimental bundle becomes a supported path.
- **Release labels:** prefer an exact tag when Leaf adopts named releases.
