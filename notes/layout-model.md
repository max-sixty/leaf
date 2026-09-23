# Layout model

A proposal to replace Leaf's document/workspace choice with independent layout axes.
Nothing here has shipped. Research at `f8660f72`, 22 September 2026, revised after two
independent reviews and two browser probes. Where a choice was close, this plan takes
the one with fewer states and elements, because that is the easier position to change
from.

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

| Axis | Question | Values | Owner |
|---|---|---|---|
| Measure | How wide is a block on the page? | column, wide, available, margin | the block, `data-width` |
| Arrangement | How are siblings placed? | sequence (default), grid, tabs | structural elements |
| Posture | Is the page held to the window? | `flow` (default), `bounded` | `lf-workspace`, from its own allocated size |

A plan or review is the page with nothing declared. A dashboard is a flow page with a
grid at available width. A workspace is an `lf-workspace` holding a grid of panes. A
margin note is a block at margin measure.

Posture has exactly two states. In `bounded`, the workspace fills its allocation, grid
rows share that height, and each pane's body scrolls while its header and footer stay
in view. In `flow`, every cell takes its natural height and the page scrolls. There is
no state in which the page and a pane both scroll.

Width and posture are independent. A grid's column count follows the width it is
given, in either posture; posture decides only heights and who scrolls. A workspace
that drops to flow keeps whatever columns its width allows.

A **region** is a declared, id-bearing reading place, and the page is one too.
Scrolling boxes without an id, such as a wide table or `pre`, stay keyboard-reachable
through `reach.js` and are not regions.

## Design

1. **One grid primitive: `lf-grid`.** Its one option is `columns`, the maximum
   column count; tracks auto-fit with a shared minimum width, so a narrow window gets
   fewer columns and a phone gets one. No spans and no ratio tracks: a span wider than
   the narrow column count creates implicit columns, so spans wait until an example
   needs them and comes with a narrow-width rule. An asymmetric layout, such as the
   monitor's release panel beside checks over log, nests one grid in a cell of
   another. Cells keep authored order (no `grid-auto-flow: dense`) and default to
   `align-items: start`.
2. **Grid cells are allocation boundaries.** A cell declares `--lf-block-frame`, the
   existing rule that withholds page room from what a box holds, so a chart in a tile
   uses the tile's width and never grows across neighbours. `data-width` measures a
   block against the page only outside cells. Widgets declare a minimum size; the
   grid owns tracks and whether rows fill. Other structural pairings stay with their
   widgets: `lf-compare` keeps variants paired, and a queue beside its detail waits
   for a task that needs one side at a time on a phone.
3. **Panes have a fixed grammar and no generated wrappers.** An `lf-pane` holds an
   optional `header`, exactly one body element, and an optional `footer`. In bounded
   posture the body scrolls and the header and footer stay in view; in flow the pane
   is an ordinary section. Styling the authored elements removes the focus transfer
   that moving nodes into wrappers forces today.
4. **`lf-workspace` decides posture with a container query on its own allocation.**
   The workspace is a size container whose height is the space the page gives it (the
   window below the banner, less any Threads panel beside it), never its content. Its
   descendants take bounded styles under one `@container` rule with global minimum
   width and height; below either, they take natural heights and the workspace lets
   its content overflow, so the page scrolls. The switch needs no script, happens at
   first paint, and answers the Threads panel taking space, which a window media query
   would miss. Because the frame is a local element, a workspace inside a root tab
   carries its own posture, and a document tab beside it is untouched. Bounded rules
   stay under `@media screen`, so copies and print flow.

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
   changes. Every declared region, the page included, is read this way. This must
   ship with design 4, or crossing the threshold or opening Threads loses the
   reader's place.
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

## How the reader's experience changes

- **Wide windows get used.** Status sections, dashboards and monitors spread across
  the width as tiles; plans and reviews keep the prose column.
- **Short windows degrade gradually.** A workspace that cannot hold the window keeps
  the columns its width allows and scrolls as one page, instead of dropping into the
  prose column.
- **The first paint is the final layout.** A workspace no longer appears as a long
  column and then snaps to the window.
- **Opening Threads can switch a workspace to flow.** The switch answers the space
  the workspace actually has, and the reader's place is restored across it (design
  5). A narrower grid also rewraps tiles.
- **Phones get the right height.** The workspace's height follows the visible
  viewport; today's `calc(100vh - …)` overshoots under a mobile browser's address
  bar.
- **The switch is not content-aware.** One global minimum decides every workspace,
  so a page whose panes could have worked slightly smaller flows, and one whose panes
  need more scrolls inside them.

## How the agent's experience changes

- **Layout becomes a few small questions.** The agent writes blocks, marks the wide
  ones, wraps tiles in `lf-grid` with a column count, and wraps the page in
  `lf-workspace` only for tool-like tasks. That replaces a page form with its own
  grammar (sole child of `main`, one body element, nested binary partitions).
- **Mixed pages need no restructuring.** A plan that grows a status section adds a
  grid to the document.
- **Less page-local layout CSS.** A dashboard needs no hand-written grid.
- **Package authors compose instead of computing minimums.** A monitoring or review
  package ships guidance and an example built from `lf-grid` and `lf-pane`.
- **More freedom means more ways to misjudge a page.** An agent can put a three-point
  plan into tiles. Guidance has to keep the document the default, and the
  agent-usability baseline (#19) is where misuse would show.

## Advantages and disadvantages

Advantages:

- Dashboards, status sections and in-document tiles need no page CSS or new roots.
- Two posture states, one grid element with one option, and no layout script.
- The fallback keeps columns, answers the space a workspace really has, and paints
  correctly first time.
- Package roots stop hand-writing minimums and restating bounded, copy and print
  rules.

Disadvantages and risks:

- **Global thresholds.** Every workspace switches at the same size, whatever its
  panes hold.
- **No spans or ratios yet.** Asymmetric layouts nest grids, which is more markup
  than a span.
- **Pane markup gets stricter.** Every pane needs one body element.
- **Continuity has to be rebuilt,** from JS-announced transitions to continuous
  landmark recording.
- **Contract churn.** Registry entries, `page-authoring.md`, the glossary,
  validation, export, and 23 test files that name workspace, partition, posture or
  bounded change together.
- **MCP embedding is unverified.** The workspace's height inside a host iframe whose
  height follows content is a feedback loop to check (#22).

## Later values

These fit the model and wait for a task that needs them: row and column spans with a
narrow-width rule; ratio tracks; a paired or one-side-at-a-time narrow form for a
queue beside its detail; a region that stays on its newest entry; canvas regions;
slides.

## Decisions

- **Posture:** two states, chosen by a container query on `lf-workspace`'s own
  allocation with global thresholds. JS measurement causes the post-upgrade snap; a
  per-page threshold computed at save time would reimplement layout and go stale; and
  pure grid fitting produced a third state where the page and a pane both scroll.
- **Frame element:** keep `lf-workspace` as a local frame rather than an attribute on
  `main`, so tabs and embeds carry their own posture.
- **Arrangement:** one `lf-grid` replaces `lf-partition` and `lf-monitor-grid`;
  pairing stays in `lf-compare`.
- **Names:** posture for the axis, workspace for the frame element.

## Slices

Each slice replaces its old path completely.

- **#29** `lf-grid` in flow, with cells as allocation boundaries. Rebuild
  `live-progress` as a document with nested grids, and `command-hub`'s status and
  fleet sections as tiles.
- **#30** `lf-workspace` as a size container, the pane grammar, and continuous reading
  continuity for every region, the page included. Compare the monitor, a comparison
  and a queue beside its detail before and after; delete `readBoundedFit`,
  `lf-partition`, and the JS minimum-size readers.
- **#31** Move `lf-monitor`, `lf-visual-review`, the playground and `lf-ask` onto the
  grid; delete `arrangeReadingElement` and the package copies of bounded rules.
- **#32** Rewrite "Document, page tabs, or workspace" in `page-authoring.md` and the
  glossary's workspace terms around the axes; land with #29.
- **#28** The page grid for chrome reservation, separately and last. Its acceptance
  test is `test_taking_the_panels_strip_leaves_the_reader_on_the_same_words` in
  `tests/test_render_controls.py`.
