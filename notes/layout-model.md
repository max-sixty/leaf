# Layout model

A proposal to replace Leaf's document/workspace choice with independent layout axes.
Nothing here has shipped. Research at `f8660f72`, 22 September 2026, with an
adversarial review whose measurements are folded in below.

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

| Axis | Question | Values | Where it is declared |
|---|---|---|---|
| Posture | Does the page scroll, or is it held to the window? | `flow` (default), `bounded` | the page root |
| Measure | How wide is a block? | column, wide, available, margin | any block, `data-width` |
| Arrangement | How are siblings placed? | sequence (default), grid, tabs | structural elements |
| Height | Does a cell keep its natural height or fill its track? | natural (default), fill | a grid row; takes effect only in bounded posture |

A **region** is a declared, id-bearing reading place, and the page is one too. Its
current scroller is read from computed style. Scrolling boxes without an id, such as a
wide table or `pre`, stay keyboard-reachable through `reach.js` and are not regions.

"Posture" and "workspace" are the glossary's existing words: posture is the axis, and
a workspace is a page in bounded posture. A plan or review is the page with nothing
declared. A dashboard is a flow page with a grid at available width. A split is a
two-track grid. A margin note is a block at margin measure in a sequence.

Two rules connect the axes:

- In flow, an arrangement changes form only when width runs out: a grid rewraps, a
  split stacks, tabs stay tabs. A bounded page that loses its posture keeps its
  columns and scrolls as a page.
- In bounded posture, height and width interact, because a grid that rewraps into
  more rows gives each row less height. The browser's grid sizing already accounts
  for both, so Leaf states minimums and lets the browser fit them (design 3).

## Design

1. **`lf-grid` places blocks in two dimensions, in either posture.** Column tracks are
   an auto-fit minimum or fixed ratios with a count shorthand (`columns="2"`), and
   cells can span rows and columns. It keeps authored order (never
   `grid-auto-flow: dense`, which would reorder cells away from reading and Ask
   order) and defaults to `align-items: start`, stretching only in fill rows. It
   inherits today's growth from the column, so `data-width="available"` works at any
   depth, including inside sections, tabs, and `details`.
2. **Panes have a fixed grammar and no generated wrappers.** An `lf-pane` holds an
   optional `header`, exactly one body element, and an optional `footer`. In bounded
   posture the body scrolls and the header and footer stay in view; in flow the pane
   is an ordinary section. Validation already checks header-first and footer-last.
   Styling the authored elements removes the focus transfer that moving nodes into
   wrappers forces today.
3. **CSS grid sizing does the fitting.** A bounded root is at least the window's
   height (`min-height` from its grid cell), its rows are `minmax(<minimum>, 1fr)`,
   and each pane body has `contain: size; overflow: auto`, so its content scrolls
   inside the pane instead of growing the row. When the minimums fit, the rows share
   the window and the page does not scroll. When they do not, the rows sit at their
   minimums and the page scrolls. Minimums are CSS: a theme default on the grid, raised
   by a cell's own `min-height` in its package theme. One global media query switches
   to natural heights when the window is too small for inner scrolling at all. No
   script and no stored number decides posture, so the first paint is final. This
   replaces `readBoundedFit`, the JS minimum-size readers, and the `leaf.js` decision.
   `lf-tabs` needs nothing extra, because a document panel has no bounded root to
   size. Bounded rules stay under `@media screen`, so copies and print flow.

   A probe in Chrome (`fit-probe.html`: banner, four panes, one with long content,
   rows `minmax(220px, 1fr)`, columns `auto-fit minmax(360px, 1fr)`, natural heights
   under 640px wide or 420px tall):

   | Window | Columns | Page height | Panes |
   |---|---|---|---|
   | 1600×1000 | 4 | 1000, no page scroll | 960px each; the long one scrolls inside |
   | 1100×700 | 3 | 700 | two rows of 330px |
   | 800×700 | 2 | 700 | two rows of 330px |
   | 700×500 | 1 | 923, page scrolls | 220px minimum each; the long one scrolls inside |
   | 1100×400 | natural heights | 2712 | the long pane is 2096px tall, no inner scroll |
   | 390×844 | natural heights | 2712 | as above |
4. **Every declared region reads the same way, the page included.** Reading-position
   capture and restore, comment jumps, and Ask travel treat the page and each pane
   alike, which removes `version.js`'s bounded-only case. Today this reading lives
   only in the browser's `sessionStorage`; giving it to the agent would be a new
   contract with its own consumer, and is out of scope here.
5. **The page grid reserves space; it does not place blocks.** A grid on `body`
   holds the banner row, the Threads panel as a track when it sits beside the page,
   the left trays, and the bottom chrome. Only `main` is placed in it. This is TODO
   #28, and it changes the claims (`--strip-l/r`, `--claim-note`, `--claim-rail`)
   into tracks. Blocks still grow out of the column. Sidenotes stay floats and
   margin rows stay positioned beside their lines, because a track cannot hold a note
   level with a particular line, and a grid on `main` would reach only its direct
   children while nearly all wide blocks are nested. `clear` and `data-lf-yield` still
   settle collisions.

Widgets declare needs in the registry: width tier, fill or natural height, and a
minimum cell size. None chooses a posture. `lf-monitor`, `lf-visual-review`, the
playground, and `lf-ask` (which uses the layout helper for a heading and one body)
compose `lf-grid` and `lf-pane` instead of calling `arrangeReadingElement`. Agents
keep full CSS freedom inside a block; page CSS that changes scrolling or placement
across Leaf's boundaries is outside the contract.

Unchanged: authored order in every posture, stable region ids, registry-declared
roles, the event log and state model, anchors, Asks, and Threads.

## How the reader's experience changes

- **Wide windows get used.** Status sections, dashboards and monitors spread across
  the width as tiles; plans and reviews keep the prose column.
- **Short windows degrade gradually.** A workspace that loses bounded posture keeps
  its columns and scrolls as one page instead of dropping into the prose column.
  Tiles rewrap as the window narrows, and a phone gets one column without a special
  case.
- **The first paint is the final layout.** CSS alone decides the fit, so a workspace
  no longer appears as a long column and then snaps to the window.
- **Phones get the right height.** A bounded page sized from its grid cell follows the
  visible viewport; today's `calc(100vh - …)` overshoots under a mobile browser's
  address bar.
- **Navigation reads the same everywhere.** Reading-position recovery, comment jumps
  and Ask travel behave the same on a flow page as in a bounded pane.
- **A middle state appears.** Between "fits the window" and the global small-window
  switch, the page scrolls and each pane also scrolls inside at its minimum height
  (700×500 in the probe). Today that range shows flow instead. Nested scrolling is
  worse than either extreme, so the minimums and the switch should keep the range
  narrow.
- **Opening Threads reflows grids.** A narrower content area rewraps tiles, which
  moves more than a narrowing column does.

## How the agent's experience changes

- **Layout becomes a few small questions.** Instead of choosing a page form and
  following its grammar (a root workspace as the sole child of `main`, exactly one
  body element, nested binary partitions), the agent writes blocks, marks the wide
  ones, wraps tiles in `lf-grid`, and asks for bounded posture only for tool-like
  tasks.
- **Mixed pages need no restructuring.** A plan that grows a status section adds a
  grid to the document instead of converting to a workspace or tabs.
- **Less page-local layout CSS.** A dashboard needs no hand-written grid.
- **Package authors compose instead of computing minimums.** A monitoring or review
  package ships guidance and an example built from `lf-grid` and `lf-pane`.
- **More freedom means more ways to misjudge a page.** An agent can put a
  three-point plan into tiles or set every block to available width. Guidance has to
  keep the document the default, and the agent-usability baseline (#19) is where
  misuse would show.

## Advantages and disadvantages

Advantages:

- Dashboards, status sections and in-document comparisons become expressible without
  page CSS or new roots.
- The fallback degrades by one axis, which keeps wide-but-short windows usable.
- CSS decides the fit at first paint, removing the column-to-window snap and the
  trial-layout measurement.
- Package roots stop hand-writing minimums and restating bounded, copy and print
  rules.
- Bounded height follows the visible viewport on phones.

Disadvantages and risks:

- **The small-window switch is global.** One media query chooses natural heights for
  every page, whatever its panes need, and between that switch and a comfortable fit
  the page scrolls around panes that also scroll.
- **Pane markup gets stricter.** Every pane needs one body element, so pages that put
  several blocks directly in a pane must wrap them.
- **A grid is a larger authoring surface than a binary split.** Keep its options to
  tracks and spans.
- **Contract churn.** Registry entries, `page-authoring.md`, the glossary, validation,
  export, and 23 test files that name workspace, partition, posture or bounded change
  together.
- **Root tabs must key on the visible panel.** The rule that stops the page scrolling
  has to match only while the shown `lf-tab` holds a bounded root, or a document tab
  renders inside a page that cannot scroll.
- **MCP embedding is unverified.** A bounded page whose height is its iframe's, inside
  an iframe whose height follows content, is a feedback loop to check (#22).

## Later values

These fit the model and should wait for a task that needs them:

- **Two-track narrow forms:** stacking suits a comparison; a queue beside its detail
  should show one side at a time on a phone.
- **A region that follows its end,** for a live log or thread list that should stay
  on the newest entry.
- **Sticky furniture** as a region property beyond pane headers and the tab strip.
- **Canvas regions** (reading position in two dimensions) and **slides** (one screen
  at a time), both close to tabs.

## Decisions

- **Fitting:** CSS grid sizing with minimums in the themes (design 3). Measuring in
  JS causes the post-upgrade snap. A per-page threshold computed elsewhere, such as in
  Python at save time, would reimplement the browser's layout arithmetic and go stale
  when a page changed without being recomputed.
- **Split:** merge `lf-partition` into `lf-grid`. The claim that agents write a
  binary split more reliably is unmeasured; the two-track case goes first in
  `lf-grid`'s example.
- **Names:** posture for the axis, workspace for a page in bounded posture.
- **Open:** whether a bounded root needs its own element, or whether
  `<main data-posture="bounded">` with a header, one body and a footer carries the one
  fact. The attribute would retire the "sole content element directly inside `main`"
  rule.

## Slices

Each slice replaces its old path completely.

- **#29** `lf-grid` in flow on today's growth mechanism. Rebuild `live-progress` as a
  document with a grid, and `command-hub`'s status and fleet sections as tiles.
- **#30** CSS fitting for bounded roots and the pane grammar; choose the minimums and
  the small-window switch against the corpus, then delete `readBoundedFit`, the JS
  minimum-size readers, and `lf-partition`.
- **#34** Every declared region reads the same way, the page included; unify
  `version.js` and `reading-regions.js`.
- **#31** Move `lf-monitor`, `lf-visual-review`, the playground and `lf-ask` onto the
  grid; delete `arrangeReadingElement` and the package copies of bounded rules.
- **#32** Rewrite "Document, page tabs, or workspace" in `page-authoring.md` and the
  glossary's workspace terms around the axes; land with #29.
- **#28** The page grid for chrome reservation, separately and last. Its acceptance
  test is `test_taking_the_panels_strip_leaves_the_reader_on_the_same_words` in
  `tests/test_render_controls.py`; the panel track must toggle through attributes or
  container state, never an inline width.
