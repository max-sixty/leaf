# How Leaf should do layout

Research at `1e6249881`, 24 September 2026. The question: if Leaf's layout were designed
again, would a page be plain HTML with widgets, or would Leaf supply more structure?

A few theme words recur below. The **measure** is the width prose is set to (720px). A
**gutter** is the space between the page and the window's edge. A **strip** is room a
resident of the margin claims beside the page: a sidebar, a note, the column of thread
cards Leaf calls the **rail**, or the open Threads panel. A **container query** is CSS
that asks the size of an enclosing box rather than the window's, so it sees room a strip
took, where a `@media` query sees only the window.

## Why this is open

HTML and CSS are already a layout language, and models write both fluently. On top of
them Leaf has built a layout vocabulary: a width for the page (`main[data-width]`, which
the docs call three "forms": document, sheet, workspace), a width for each block
(`column` / `wide` / `available`), `lf-grid`, `lf-workspace` and `lf-pane`, and the
`section.panel`, `aside.sidebar` and `aside.sidenote` idioms.

That vocabulary has been expensive to hold still. Since 1 September, 190 of main's 998
commits changed the two theme files or `margin-projection.js`, which together run to
7,400 lines. The same distinction has been redrawn several times: #1088 let a page be a
sheet, #1113 made workspaces sheets, and #1119 put column pages and sheets on one margin
formula, after which a document and a sheet are the same layout at two measures.
Nothing has measured whether the vocabulary helps an author: the backlog's comparison of
Leaf authoring against plain HTML (`notes/workspace-followups.md`, #19 there) has not
run.

## What Leaf has to own whatever it chooses

AGENTS.md's test for a primitive is that it gives the user something a bespoke site
would not. Applied to layout, it splits the work in two.

Leaf has to own anything that depends on facts the agent cannot see while it writes:

- **The frame.** The page shares the window with Leaf's chrome: the banner, the Threads
  panel, the Asks tray, and the bottom shortcut bar, each opened and closed after the
  page is written. Leaf decides what box the page gets. It also has to know how the page
  uses that box: the Threads panel takes a strip from a page that runs to the window's
  edge, and stands over a centred column instead (`theme.css:636-645`).
- **The margin.** Thread cards stand beside the passage they anchor. Leaf reserves their
  rail, docks and packs the cards (`margin-layout.js`), and narrows the page to leave
  them room (the strip terms in `main`'s formula, `theme.css:695-735`).
- **Scrolling.** Leaf restores the reader's position, keeps them on the same words across
  a revision, and lands anchors. It can do that only in scroll containers it knows about,
  which is why the guidance says not to make one in page CSS and `version check` advises
  against it.
- **What a block may take.** How much room is free beside the prose depends on which
  margin residents stand at that moment. `main` resolves it (`--lf-free-l`, `--lf-free-r`),
  and a block that asks for `wide` or `available` spends it (`theme.css:812-850`).
- **Preferences and unseen conditions.** A phone, a window 1261px wide with Threads open,
  print, export, and the user's own standing preferences, such as denser dashboards.

The rest is composition: which regions sit side by side, how tiles wrap, what a panel
looks like. Composition is the agent's under the AGENTS.md principle ("what a page says
and how it is composed is the agent's"). A Leaf primitive there competes with CSS the
agent already knows.

Several current primitives are both at once. `lf-grid` places tracks and stacks them
(composition), but it also marks each cell as a frame of its own, so a wide widget fills
the cell rather than breaking out of it, and gives each cell the prose measure
(`default/theme.css:25-60`). The held-workspace rules and the `misalignedSplits` check
recognise only an `lf-grid` or a box declaring `data-lf-reading-role="grid"`. So an
agent that writes its own grid has to make the same declaration by hand:
`examples/notification-playground.html:75` sets `--lf-block-frame: 1`, a property only
the package reference documents.

## Options

Every option keeps the frame, margin, and scrolling above. They differ in how much
composition Leaf supplies, from least to most.

- **#27 A bare frame.** Leaf supplies the frame and publishes its facts to page CSS as
  custom properties: room, measure, gutters, spacing, gap. A page with no CSS reads as a
  document in the reading column. Any other arrangement is the agent's own CSS, written
  with container queries against a named box (`lf-shell`, or the agent's own wrapper) so
  it responds to an open panel. `lf-grid`, the width names, and `section.panel` go.
  - Least vocabulary and least code for Leaf to maintain.
  - Everything in the "what a block may take" and `lf-grid` paragraphs above has to be
    rewritten per page or lost: a wide table beside a sidenote no longer knows its room.
    A preference like "denser dashboards" reaches only pages whose CSS happens to use
    the published gap. Models reach for `@media` by habit, which misses the panel.
- **#28 A bare frame with outcome checks.** #27, with the render gate as the contract.
  `version check --render` lays the page out at a phone width, a laptop width, and a
  laptop width with Threads open, and fails on what the user would suffer: horizontal
  overflow, content under chrome or a margin card, prose longer than the measure, an
  undeclared scroller, clipped controls, phone reading order that differs from source
  order, and a width `@media` rule in page CSS. Most checks exist (`render-checks/
  layout.js`, `reachability.js`); today the gate runs once, at 1200×900 with no panel
  open. Worked examples teach composition.
  - Makes "presentation holds" and "self-checks" true for free-form CSS, not only for
    pages that use the vocabulary.
  - Checks catch breakage, not ugliness, and not a preference left unapplied. More
    authoring iterations, since the agent learns the rules by failing them.
- **#31 Agent CSS with declared roles.** #28, plus a small set of declarations that tell
  Leaf what a box is, with no say over how it is arranged. The page declares its width
  (column or window) because the frame and the panel behave differently for each. A
  block declares the room it asks for (`data-width`), which also overrides a widget's
  default. A box the agent lays out declares that it is a grid or a pane
  (`data-lf-reading-role`, which the theme already accepts), and Leaf then gives its
  cells their own frame and measure, holds its height in a workspace, and checks its
  alignment. Tracks, gaps, and panels are the agent's CSS, taught by examples, using
  published tokens so preferences land.
  - Keeps every frame fact and check the vocabulary provides, with composition left to
    the agent. It is where the code has been heading: `data-lf-reading-role` exists
    because packages needed exactly this.
  - Still a vocabulary to learn, though one of meanings rather than arrangements, and
    consistency across pages still rests on examples.
- **#29 Today's approach, consolidated.** One layout; the page's width as the one
  page-level choice; `lf-grid` for tracks; `lf-workspace` and `lf-pane` for held regions;
  `section.panel` to draw them. The "three forms" become one width choice plus the
  workspace element.
  - Most consistent across pages, and a preference reaches every page through the
    theme.
  - Keeps the cost of the last month. Each primitive has edges (a wide block in a column
    page, a workspace among other blocks, a grid per row) needing rules, checks, and
    docs, and the agent has to learn when each applies.
- **#30 Templates.** Leaf ships a handful of shapes with named slots (report, dashboard,
  queue and detail, review, playground). A lighter variant keeps title, status and rail as
  chrome slots and leaves the body free.
  - Strongest consistency, and a weak model still produces a good page.
  - The long tail falls outside every template, and choosing the shape moves composition
    from the agent to Leaf, which the AGENTS.md principle rules out as a default.
    Templates fit better as examples to copy and change.

## Recommendation

Adopt #31. Keep every declaration that exists because of the frame, the margin, or
scrolling: the page width, block widths, the grid and pane roles, `lf-workspace`,
`data-bound`, margin residents, and `lf-tabs` for page views. Replace the arrangement
vocabulary (`lf-grid`'s `columns`, `section.panel`, the tracks recipe) with worked
examples and published tokens, and extend the gate to #28's three frames.

The "three forms" wording goes in any case: a sheet is a page width and a workspace is
an element.

The case for #31 over #29 is a hypothesis: that the recurring rules have been about
arrangement, which models already write well, while the fixes that lasted were to the
frame (#1119) and to scrolling (#1065). Several of the cited PRs changed both, so this
needs the comparison below rather than the commit count. The case against is
consistency and preferences, which #31 leaves to examples and tokens.

## How to decide

Run the backlog's authoring comparison with #31 and #29 as the arms, and plain HTML as
the control. Give the same subjects (a document, a dashboard, a queue with its detail)
to fresh agents under each set of guidance. Judge each page at the three check frames,
with a standing preference applied, and after one round of user comments. Record what
fails the gate, how many iterations each takes, how much page CSS it writes, and which
page a reviewer who has not seen the guidance prefers. `notes/agent-usability-evals.md`
has the harness.
