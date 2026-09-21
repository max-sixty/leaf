# TODO

Priority runs from **Now** to **Next** to **Etc**. Themes group related work within
each priority; bullets are outcomes, not implementation plans. Linked notes hold the
evidence and detailed briefs. Numbered items keep the ids shared with `notes/`.
Completed work and rejected ideas live in git history or the relevant research note.

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
- **Make a phone reading journey complete.** Give touch readers an element-target
  route and visible passage threads; supply the document viewport at delivery.
  Check the selection-menu collision and interactive-reply crash on a real iPhone
  before choosing those fixes. Then remove keyboard-only hints, hover-only reasons,
  clipped diagram and diff content, and undersized touch targets.
- **Give the thread panel's touch grip its own space.** Reserve room for the grip
  and collapse inactive reply controls if more thread cards should fit.

### Architecture and verification

- **#5 — Separate the margin model from presentation.** Derive clusters and Page
  Map entries as immutable data, then let placement and retained controls consume
  them. This removes semantic identity from DOM attributes and lets model rules be
  tested without Chrome.
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
