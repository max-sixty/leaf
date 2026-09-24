# How Leaf should do layout

Research at `1e6249881`, 24 September 2026. The question: if Leaf's layout were designed
again, would a page be plain HTML with widgets, or would Leaf supply more structure?

A few theme words recur below. The **measure** is the width prose is set to (720px). A
**strip** is room something beside the page takes from it: a margin note, the **rail**
where thread cards stand, the open Threads panel, or the Asks tray. A **container query**
is CSS that asks the size of an enclosing box rather than the window's.

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
formula. Nothing has measured whether the vocabulary helps an author: the backlog's
comparison of Leaf authoring against plain HTML (`notes/workspace-followups.md`, #19
there) has not run.

## What the agent cannot know

Most of what Leaf draws is known when the page is written. The banner's height, the
Threads panel's width (420px), the Asks tray's (300px), and the rail are constants, and
the rail is already reserved on every live page from the start and never given back
(`margin-layout.js:19-23`). An agent told those numbers could lay out around them.

Three things are unknown when the page is written:

- **Which surfaces the user opens.** Threads and the Asks tray open and close while the
  page is read.
- **Where the user comments.** A thread can anchor to any passage, so a card can be
  wanted beside any line.
- **The window.** Its width and the user's standing preferences. CSS already handles the
  window for any page.

Today Leaf answers the first two by changing the page's dimensions. The Asks tray, where the
window has room for it beside the page, takes a strip from every page. The Threads panel takes one from a page that runs to the window's
edge (`theme.css:636-645`). Margin residents narrow `main`, and the room left beside the
prose (`--lf-free-l`, `--lf-free-r`) is what a wide block may spend (`theme.css:695-735`,
`812-850`). That is why an author has to declare the page's width and each block's: the
page's geometry depends on runtime state, and only Leaf's vocabulary is wired to it.
Most of the layout vocabulary exists to handle strips.

## Leaf as overlays

Leaf could instead never change the page's dimensions. The page gets the window below the
banner, and everything Leaf adds draws over it:

- **Threads and the Asks tray** open over the page, as Threads already does on a column
  page.
- **Thread cards** stand in the rail when the page leaves one. Leaf publishes the rail's
  width as a token, a page with no CSS leaves it free, and an agent composing a
  full-width page decides whether to leave it. Where no rail is free, a card docks into
  the text, as it does below the margin breakpoint now.
- **Scroll areas** are the agent's. Leaf restores a position in a scroller it finds at run
  time rather than one the author declared, given a stable id to key on
  (`reading-regions.js` already tracks the scroller a region currently has).

The page's geometry is then exactly what its HTML and CSS say. Strip arithmetic, the page
and block width declarations, and the rules for wide blocks beside margin notes all go,
along with the scroll-anchoring care the strips need (`theme.css:576-600`).

The cost is occlusion. On a centred column the panel covers mostly empty window. On a
full-width dashboard it covers the right 420px, and the passage the user is discussing
may be under it. Leaf can scroll an anchored passage into view vertically, but not out
from under the panel sideways. The remedies are to open the panel on the side away from
the anchor, to let the user resize or close it, or to have agents that expect heavy
commenting leave the rail. The width the panel took is what the strip was buying, and
overlays trade it for a page the agent fully controls.

## Options

Every option keeps Leaf's chrome, thread anchoring, and reading-place mechanics. They
differ in how much layout Leaf supplies. #33 is the one this revision adds.

- **#33 Overlays over agent CSS.** Leaf draws over the page and never resizes it. Leaf
  supplies theme defaults for plain HTML (a page with no CSS is a document in the
  reading column), publishes tokens (measure, spacing, gap, rail width) so preferences
  reach agent CSS, and checks outcomes. `version check --render` lays the page out at a
  phone width and a laptop width, with Threads open and closed, and fails on horizontal
  overflow, clipped controls, prose longer than the measure, and phone reading order
  that differs from source order. Most of those checks exist (`render-checks/layout.js`,
  `reachability.js`); today the gate runs once, at 1200×900, with no panel open.
  `lf-workspace`, `lf-grid`, the width names and `section.panel` become worked examples.
  - The page is what the agent wrote, at every moment. Leaf's layout code shrinks to
    chrome and card placement.
  - Occlusion as above. Consistency across pages rests on examples and tokens.
- **#28 A frame with outcome checks.** As #33, but Leaf keeps taking strips, so it
  publishes the room it leaves and agent CSS must answer it with container queries.
  - Nothing is covered.
  - The agent writes against dimensions that change under it, which is the source of
    today's vocabulary.
- **#31 Agent CSS with declared roles.** As #28, plus declarations telling Leaf what a
  box is (page width, block width, `data-lf-reading-role` grid or pane) so Leaf can give
  it room from the strips. Under overlays these declarations lose their reason.
- **#29 Today's approach, consolidated.** Leaf's own grid, panes and panels, with the
  "three forms" as one width choice plus the workspace element. Most consistent across
  pages; keeps the cost of the last month.
- **#30 Templates.** Named page shapes with slots. Strongest consistency; the long tail
  falls outside them, and the choice of arrangement moves from the agent to Leaf.
- **#27 A bare frame** is #28 without the checks, and is dropped.

## Recommendation

Adopt #33. The strips are the one reason the page's geometry depends on runtime state,
and that dependence is what the layout vocabulary exists to manage. Covering instead
leaves the agent with plain HTML and CSS over a known window, which is what models write
best, and it leaves Leaf the parts only Leaf can do: chrome, anchoring, reading place,
tokens for preferences, and checks.

Whether occlusion is acceptable is the open question. Test it on the pages where it
bites: a full-width dashboard and a queue with its detail, each with Threads open on a
passage in the right third of the window.

## How to decide

Run the backlog's authoring comparison with #33 and #29 as the arms, and plain HTML as
the control. Give the same subjects (a document, a dashboard, a queue with its detail)
to fresh agents under each set of guidance. Judge each page at the check frames, with a
standing preference applied, and after one round of user comments made with Threads
open. Record what fails the gate, how many iterations each takes, how much page CSS it
writes, and which page a reviewer who has not seen the guidance prefers.
`notes/agent-usability-evals.md` has the harness.
