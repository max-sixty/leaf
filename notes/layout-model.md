# Layout model

A proposal to replace Leaf's document/workspace choice with shared layout primitives
composed into task components, with a strong document default. Nothing here has
shipped. Research at `f8660f72`, 22 September 2026, revised after four independent
reviews and two browser probes. Where a choice was close, this plan takes the one
with fewer states and elements, because that is the easier position to change from.

## The problem

Leaf offers two page layouts. A document flows: the page scrolls, prose sits in the
720px column, and blocks may widen with `data-width`. A root workspace is held to the
window: panes scroll independently, the page uses the whole width, and `lf-partition`
splits space into two equal halves. When a workspace does not fit, it falls back to
flow.

That dichotomy bundles choices that CSS keeps separate, and pages that need a
different combination have nowhere to go:

- **The fallback changes two things at once.** The `live-progress` monitor falls back
  to flow at 1100×700, 1100×800 and 1400×700, and flow puts it in the 768px column
  with checks and log stacked under the release panel. The width would have held its
  columns.
- **Two-dimensional arrangement exists only in bounded posture.** `lf-partition`'s
  column grid sits inside `@container style(--lf-reading-posture: bounded)`, so a
  partition in a document always stacks. Side-by-side layout in flow exists only
  inside `lf-compare` and `lf-metrics`, each with its own `auto-fit` grid.
- **Each two-dimensional shape is a new root.** `lf-monitor` and `lf-visual-review`
  share `arrangeReadingElement` with `lf-workspace`, but each hand-writes its minimum
  size and restates the bounded grid, heights and copy/print overrides in its package
  theme.
- **Dashboards fit neither form.** A status page wants page scroll, the full width,
  and a grid of short tiles that rewraps by width. `command-hub` renders at 720px on
  a 1600px window.
- **The page paints in one layout and then switches.** At 1600×900, `live-progress`
  first paints as a 768px column 2109px tall; after upgrade it becomes a 1600px
  bounded page 900px tall. Posture is measured after `leaf.js` runs.

## The model

**A containing frame allocates space, its children arrange themselves within it, and
each piece of content has one scroller.** The page, a root tab panel, a workspace, a
grid cell, and a pane are frames. What a block may take is what its frame gives it:
nothing inside a frame reaches past it.

Three questions follow from that rule:

| Question | Values | Owner |
|---|---|---|
| How much of the page's width does a block take? | column, wide, available | the block, `data-width`; only in the page's own flow, since a cell or pane allocates its own width |
| How are sibling blocks placed? | a sequence (default) or a grid | `lf-grid` owns the geometry |
| Who scrolls this content? | the page; a pane's body when its workspace is bounded; a block that declares its own bound | the page, `lf-workspace`'s posture, or the block |

Prose keeps the column measure inside every frame. A frame's width goes to the
surfaces it holds, such as charts, tables, logs and code, never to lines of text. A
two-column grid at 1600px therefore still sets its paragraphs at a readable length.

A block's own bound works like its width: a registry default for widgets that need
one (a log, a feed, a code listing), and an authored occurrence for anything else.
Today's scrolling `pre` and wide tables are instances of the same rule. A bounded
block may follow its newest entry, which a log in the first dashboard will need.

Two things that look like layout are relationships, and stay with the components that
own them:

- **What the siblings mean to each other.** "Independent status items" is a grid of
  tiles. "Alternatives to compare" is `lf-compare`, which keeps its variants paired
  however narrow the page gets. "Controls that operate a preview" is `lf-playground`.
  "Views the reader switches between" is `lf-tabs`, which carries selection,
  visibility and keyboard behaviour, not only geometry. A grid owns geometry; the
  component owns the relationship, so a narrower layout changes presentation without
  changing the task.
- **A margin note** is placed beside the line it annotates. Like `data-width`, that
  placement exists only in the page's own flow; inside another frame a margin note is
  an aside in place.

A **workspace** means "keep these task regions together when space permits". It stays
the same workspace when it flows. Its posture is the responsive policy:

- **`bounded`:** the workspace fills its frame, grid rows share that height, and each
  pane's body scrolls while its header and footer stay in view.
- **`flow`:** every cell takes its natural height and the page scrolls.

A workspace is bounded only when its host is a frame that does not scroll and has a
finite height. That one rule covers the page below the banner, a root tab panel, a
specimen in a sized frame, and an MCP host that fixes its iframe's height; a workspace
inside a document or inside a scrolling pane body flows. There is no state in which a
bounded workspace is taller than its host, so no content scrolls both inside a pane
and with the page.

Width and posture are independent. A grid's column count follows the width it is
given, in either posture; posture decides only heights and who scrolls.

A **view** is what a reader takes in as one part of the page: a section in flow, a
pane in a workspace, or a tab panel. A **region** is a view that can own its scroll: a
pane, a tab panel, or the page. Reading position is kept per region. Blocks with their
own bound stay keyboard-reachable through `reach.js` and are not regions.

## Design

1. **`lf-grid` places blocks in two dimensions.** Its one option, `columns`, takes a
   count (`columns="3"`, equal tracks that auto-fit with a shared minimum width) or a
   track template (`columns="1fr 2fr"`, which collapses to one column below the
   minimum). Queue beside detail, controls beside preview, and the monitor's release
   panel at `.72fr` all need unequal columns, which nesting cannot produce. Spans stay
   deferred: nesting covers them and keeps authored order, while a span wider than the
   narrow column count creates implicit columns. Cells keep authored order (no
   `grid-auto-flow: dense`) and default to `align-items: start`. This surface can
   grow, and a later task may justify a second primitive.
2. **Grid cells are frames.** A cell declares `--lf-block-frame`, the existing rule
   that withholds page room from what a box holds, so a chart in a tile uses the
   tile's width. Widgets declare a minimum size; the grid owns tracks and whether rows
   fill.
3. **Panes have a fixed grammar and no generated wrappers.** An `lf-pane` holds an
   optional `header`, exactly one body element, and an optional `footer`. In bounded
   posture the body scrolls and the header and footer stay in view; in flow the pane
   is an ordinary section. Styling the authored elements removes the focus transfer
   that moving nodes into wrappers forces today.
4. **`lf-workspace` chooses posture with a container query on its own allocation.** A
   workspace whose host gives it a finite height is a size container. Its descendants
   take bounded styles under one `@container` rule with global minimum width and
   height; below either, they take natural heights and the workspace lets its content
   overflow, so the page scrolls. A workspace with no finite height from its host is an
   inline-size container that always flows. The switch needs no script, happens at
   first paint, and answers the space the workspace actually has, which a window media
   query would miss. Bounded rules stay under `@media screen`, so copies and print
   flow.

   Opening Threads must not restructure the page the reader is commenting on. Where
   placing the panel beside a bounded workspace would take the workspace under its
   minimum, the panel covers instead. Today it covers only at windows of 840px or less
   (`COVERING` in `chrome-layout.js`), so between about 841px and the width where a
   bounded workspace and the panel fit side by side, a comment would otherwise flip a
   monitor to flow. The cost is the modal covering panel from PR #536 at those widths.

   A probe in Chrome (`frame-probe.html`: banner, `lf-workspace` as a size container,
   four panes with one long, columns `auto-fit minmax(360px, 1fr)`, bounded at
   720×560 or larger):

   | Window | Columns | Posture | Scrolls |
   |---|---|---|---|
   | 1600×1000 | 4 | bounded, panes 960px | only the long pane's body |
   | 1100×700 | 3 | bounded, panes 330px | only the long pane's body |
   | 1100×700, 420px panel | 1 | flow | the page |
   | 700×500 | 1 | flow | the page |
   | 390×844 | 1 | flow | the page |

5. **Reading continuity moves with posture.** Today a JS-driven posture change
   captures the reader's position before the mutation and restores it after
   (`version.js`). A CSS switch has no "before" moment, so the runtime records the
   reading landmark continuously and restores it when the box that scrolls a region
   changes. Every declared region, the page included, is read this way. This ships
   with design 4, or crossing the threshold or opening Threads loses the reader's
   place.
6. **The page grid reserves space; it does not place blocks.** A grid on `body` holds
   the banner row, the Threads panel as a track when it sits beside the page, the
   left trays, and the bottom chrome. Only `main` is placed in it. This is TODO #28.
   Blocks still grow out of the column; sidenotes stay floats and margin rows stay
   positioned beside their lines.

Widgets never choose a posture. `lf-monitor`, `lf-visual-review`, the playground and
`lf-ask` compose `lf-grid` and `lf-pane` instead of calling `arrangeReadingElement`.
Agents keep full CSS freedom inside a block; page CSS that changes scrolling or
placement across Leaf's boundaries is outside the contract.

Unchanged: authored order in every posture, stable region ids, registry-declared
roles, the event log and state model, anchors, Asks, and Threads.

## Authoring: recipes over primitives

Agents do not design a page by answering the three questions above. They start from
a few task-shaped compositions, taught as package guidance and worked examples built
from the same primitives, never as separate layout engines or required templates:

- **A sequential explanation:** plans, reviews, write-ups. The default, with nothing
  declared.
- **Independent status tiles:** an `lf-grid` inside the explanation, at available
  width. Each tile holds a surface (a metric, chart, table, list or log, with at most
  a caption), not paragraphs. A row of headline numbers is this recipe applied to
  metrics, so `lf-metrics` becomes a grid of `lf-metric` tiles rather than a second
  way to lay out status.
- **A comparison:** `lf-compare`, which keeps alternatives paired.
- **Controls beside evidence:** a playground, which is a workspace with the
  relationship between its controls and its preview declared. Plain panes in an
  `lf-workspace` are for regions with no such relationship.

An agent starts from the explanation and inserts the others where they help, keeping
the surrounding prose. A report that gains live status gains a grid; it is not
converted into another page type.

Behaviour enforces the rails that do not need judgment: readable prose measure in
every frame, content contained in its frame, authored reading order, reachable
actions, and anchors that survive rearrangement. Guidance covers what does: whether
information deserves a tile, whether a comparison needs both sides visible at once,
or whether tabs would hide something the reader needs.

Validation can flag the structural shadow of two failures without judging relevance:
a grid whose cells hold only prose (over-tiling), and page CSS that sets scrolling or
placement on a Leaf layout element (fighting the rails).

## How the reader's experience changes

- **Wide windows get used.** Status sections, dashboards and monitors spread across
  the width as tiles; plans and reviews keep the prose column.
- **Short windows degrade gradually.** A workspace that cannot hold the window keeps
  the columns its width allows and scrolls as one page, instead of dropping into the
  prose column.
- **The first paint is the final layout.** A workspace no longer appears as a long
  column and then snaps to the window.
- **Commenting never restructures a workspace.** Where Threads beside a bounded
  workspace would push it under its minimum, the panel covers it instead. On flow
  pages a narrower content area still rewraps tiles, and the reader's place is
  restored across it (design 5).
- **Long logs stop growing the page.** A log or feed in a dashboard bounds itself and
  can stay on its newest entry.
- **Phones get the right height.** The workspace's height follows the visible
  viewport; today's `calc(100vh - …)` overshoots under a mobile browser's address
  bar.
- **The switch is not content-aware.** One global minimum decides every workspace,
  so a page whose panes could have worked slightly smaller flows, and one whose panes
  need more scrolls inside them.

## How the agent's experience changes

- **Pages start from recipes.** An agent picks the composition that matches the task
  and inserts others where they help, instead of choosing a page form with its own
  grammar (sole child of `main`, one body element, nested binary partitions).
- **Pages grow without restructuring.** Adding status, a comparison or a tool to an
  explanation is an insertion, so existing comments and anchors stay put.
- **Less page-local layout CSS.** A dashboard needs no hand-written grid.
- **Package authors compose instead of computing minimums.** A monitoring or review
  package ships guidance and an example built from `lf-grid` and `lf-pane`.
- **More freedom means more ways to misjudge a page.** An agent can put a three-point
  plan into tiles. The recipes keep the explanation as the default, and the
  evaluation below is where misuse would show.

## Advantages and disadvantages

Advantages:

- Dashboards, status sections and in-document tiles need no page CSS or new roots.
- One allocation rule explains every frame, from the page to a tile.
- Two posture states, one grid element, and no layout script.
- The fallback keeps columns, answers the space a workspace really has, and paints
  correctly first time.
- Package roots stop hand-writing minimums and restating bounded, copy and print
  rules.

Disadvantages and risks:

- **Global thresholds.** Every workspace switches at the same size, whatever its
  panes hold.
- **No spans yet.** Layouts where one cell spans rows nest grids, which is more
  markup than a span.
- **A covering panel at middle widths.** Threads covers a bounded workspace wherever
  beside would not fit, so commenting there is modal.
- **Pane markup gets stricter.** Every pane needs one body element.
- **Continuity has to be rebuilt,** from JS-announced transitions to continuous
  landmark recording.
- **Contract churn.** Registry entries, `page-authoring.md`, the glossary,
  validation, export, and 23 test files that name workspace, partition, posture or
  bounded change together.
- **Embedding follows the host rule, unmeasured.** Leaf's MCP shell fixes its
  page-mode height, which would make an embedded workspace bounded; that reading comes
  from `mcp-app/page-app.html` and has not been run (#22).

## Evaluation

The open question is agent usability, not whether the layout works. Give fresh agents
a few tasks across the recipes, then ask them to revise the results: for example, turn
a report into a report with live status while keeping its existing comments. The
foundation holds if the revisions happen by ordinary composition, with no page-wide
CSS and no wholesale restructuring. Include a cold agent asked for "a dashboard",
since that word is the likeliest trigger for over-tiling. Run it with the
agent-usability baseline (#19) after #29 and #32 land.

## Later values

These fit the model and wait for a task that needs them: row and column spans with a
narrow-width rule; a selection-and-detail component whose phone form shows one side
at a time; canvas regions, whose reading position is two-dimensional; slides, as a
presentation of `lf-tabs`.

## Decisions

- **Foundation:** frames allocate, children arrange within them, each piece of
  content has one scroller; posture is a workspace's responsive policy; prose keeps
  its measure in every frame.
- **Posture:** two states, chosen by a container query on `lf-workspace`'s own
  allocation with global thresholds; bounded only where the host gives a finite
  height, and Threads covers rather than push it under its minimum. JS measurement
  causes the post-upgrade snap, a per-page threshold computed
  at save time would reimplement layout and go stale, and pure grid fitting produced
  a third state where the page and a pane both scroll.
- **Frame element:** keep `lf-workspace` as a local frame rather than an attribute on
  `main`, so tabs and embeds carry their own posture.
- **Geometry and relationships:** `lf-grid` owns geometry and replaces `lf-partition`
  and `lf-monitor-grid`, and `columns` takes a count or a track template;
  `lf-compare`, `lf-tabs` and the playground own their relationships; `lf-metrics`
  becomes tiles in the grid.
- **Authoring:** recipes in guidance and examples, not an axis questionnaire or
  mandatory templates.
- **Names:** posture for the policy, workspace for the frame element.

## Slices

Each slice replaces its old path completely.

- **#29** `lf-grid` in flow, with cells as frames, prose measure inside frames, and
  blocks that declare their own bound (including following the newest entry). Rebuild
  `live-progress` as a document with grids and a bounded log, `command-hub`'s status
  and fleet sections as tiles, and `lf-metrics` as metric tiles.
- **#32** Rewrite "Document, page tabs, or workspace" in `page-authoring.md` as the
  four recipes, and the glossary's workspace terms around frames and posture; land
  with #29.
- **#30** `lf-workspace` as a size container where its host gives finite height, the
  pane grammar, and continuous reading continuity for every region, the page
  included, and Threads covering a bounded workspace it would squeeze. Compare the
  monitor, a comparison and a queue beside its detail before and
  after; delete `readBoundedFit`, `lf-partition`, and the JS minimum-size readers.
- **#31** Move `lf-monitor`, `lf-visual-review`, the playground and `lf-ask` onto the
  grid; delete `arrangeReadingElement` and the package copies of bounded rules.
- **#28** The page grid for chrome reservation, separately and last. Its acceptance
  test is `test_taking_the_panels_strip_leaves_the_reader_on_the_same_words` in
  `tests/test_render_controls.py`.
