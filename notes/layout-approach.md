# How Leaf should do layout

Research at `1e6249881`, 24 September 2026. The question: if Leaf's layout were designed
again, would a page be plain HTML with widgets, or would Leaf supply more structure?

This revision assumes two changes in flight have landed: the Asks tray and the Threads
panel draw over the page instead of taking room from it (branch `asks-tray-overlay`), and
the rail where thread cards stand is a fixed reservation that never widens (branch
`fixed-rail`).

## Terms

- The **measure** is the width prose is set to (720px).
- The **rail** is the strip beside the page where thread cards stand.
- Leaf takes room from the page in two ways. A **surface strip** is taken from the whole
  page by an open surface, today the Asks tray (a border on `body`). A **margin
  reservation** is kept inside `main` for something standing in the margin: the rail, or
  an agent's margin note (`--strip-r`, `theme.css:698-700`).
- A **wide block** is a block in a centred column that grows out of the column into the
  free room beside the prose (`--lf-free-l`, `--lf-free-r`), by negative margins. This is
  the familiar "figure wider than the text" layout (`theme.css:786-830`).
- A **frame** is a box that says "not past me": inside it, a wide block fills the box
  instead of growing out of it (`--lf-block-frame`, `theme.css:880-903`). A grid cell
  and a `<details>` are frames.

## Why this is open

HTML and CSS are already a layout language, and models write both fluently. On top of
them Leaf has built a layout vocabulary: a width for the page (`main[data-width]`, which
the docs call three "forms": document, sheet, workspace), a width for each block
(`column` / `wide` / `available`), `lf-grid`, `lf-workspace` and `lf-pane`, and the
idioms in `$idioms` (`section.panel`, `aside.sidebar`, `aside.sidenote`, `.callout` and
others). Since 1 September, 191 of the 993 commits on main changed the two theme files or
`margin-projection.js`, which together run to 7,400 lines.

## What the overlays settle

With the tray and panel covering and the rail fixed, surface strips are gone and the
margin reservations are known when the page is written: the rail is a constant, and a
margin note is the agent's own. The page's width then depends only on the window and a
few numbers the agent can be told. That is the knowledge the agent was missing.

Several run-time geometry sources survive both branches, and each needs a decision:

- **A comment narrows a wide block.** When a thread card lands level with a wide block,
  `margin-layout.js` marks the block (`data-lf-yield`) and the theme removes its growth
  toward the rail (`theme.css:1957-1960`). With a fixed rail the collision is known in
  advance, so every wide block can stop short of the rail whenever the rail is shown, and
  the mark can go.
- **Two chrome heights are measured, not constant.** The bottom bar's clearance
  (`--lf-bottom-chrome-clear`) is read from the bar's rendered box on each layout pass
  (`chrome-layout.js:137-184`), and the root tab strip's clearance (`--lf-root-tab-clear`,
  `lf-tabs.js:318-330`) likewise. Both set a workspace's height
  (`default/theme.css:239-250`). The banner's height is already a theme constant
  (`theme.css:131`); these two can be too.
- **Opening a surface can lengthen the page.** An open surface sets a minimum height on
  `body` (`theme.css:538-543`), which the overlay branch keeps.
- **Docked cards add height.** Below 840px, and in `fixed-rail` for a card wider than
  the rail at any width, cards dock into the text flow. A comment arriving then pushes
  the text below it down. This is vertical only, and inherent to showing a card inline.

So the accurate claim is that the page's width becomes the agent's to know. The height
stays open to comments docked inline, which is acceptable, and to the three items above
it, which can be fixed.

## What the vocabulary is for, once the width is settled

The overlays remove the reason for less of the vocabulary than it first appears. Wide
blocks and frames never existed because of surface strips: they are how a centred
column lets a figure outgrow the text (the Tufte and Distill layout), and they compute
the free room from the margin reservations. With fixed reservations they need no run-time
state, but they are still real layout machinery, and dropping them means giving up
figures wider than the column.

The pieces sort into three groups.

**Interaction primitives**, which exist because of how the user reads, comments, and
acts, which AGENTS.md makes Leaf's:

- `lf-pane` registers its body as a reading region, so reading keys, travel, and
  continuity find the place whichever box scrolls it (`lf-pane.js:1-5`).
- `lf-workspace` holds panes to the window's height so each pane can be a reading region.
- `lf-tabs` gives a page several views that share one history, one Threads panel, and
  one revision sequence.
- The rail, thread cards, and docking them.

**Widget sizing.** A widget states its natural width in the registry (`x-space`), such as
a diagram or a diff wanting the wide width, and the runtime paints it as `data-lf-space`
(`presentation.js:539-552`). That is how widgets from several packages size themselves,
so the wide-block rules stay whatever authors write.

**Arrangement**: a wide page, grids, panels, margin notes, sidebars, and whether a given
block is wide. These are presentation. The remaining question is whether Leaf offering
them makes pages better than an agent's own CSS, and whether they carry the user's
preferences.

Two of these are wired into other machinery, so moving them is more than a rename:

- The held workspace is keyed on `main[data-width]` and on `lf-grid`
  (`default/theme.css:186-190, 229-250, 283-286`). "A workspace holds the window when it
  is the page's only content" means rewriting those selectors to
  `main:has(> lf-workspace:only-child)` and keying the hold chain on grids generally.
- The render gate only sees Leaf's own grids: `misalignedSplits` walks `lf-grid` and
  boxes declaring the grid role (`render-checks/layout.js:407-412`), and `withheldRoom`
  reads `data-lf-space` (`layout.js:478-503`). An agent's own CSS grid is invisible to
  it.

## Options for arrangement

The interaction primitives, widget sizing, and the rail stay under every option.

- **#35 Plain CSS with tokens.** Leaf styles plain elements, so a page with no CSS
  reads as a document in the reading column, and publishes tokens: the measure, spacing,
  gap, the rail, and the chrome heights. Everything else is the agent's CSS.
  - Nothing to learn, and least for Leaf to maintain.
  - No figures wider than the column unless the agent rebuilds the breakout. A
    preference such as "denser dashboards" reaches only CSS that uses the published gap.
- **#36 Arrangement as idioms.** Leaf already has the mechanism: `$idioms` is a catalog
  of "recurring shapes the theme styles directly — no element declaration, no JS"
  (`assets/registry.json:1036-1037`), and it holds the panel, sidebar, and margin note
  today. Move the grid, the wide block, and the wide page into it, and make the render
  gate read computed layout (any element laid out as a multi-column grid) rather than
  Leaf's element names, so it judges an agent's own grid the same way.
  - An agent uses an idiom or writes its own CSS, and gets the same checks either way.
    Idioms carry preferences through tokens and can change without touching anything
    else.
  - `lf-grid`'s script computes how far a track template can shrink before it stacks
    (`lf-grid.js:36-40`), which CSS cannot read from an attribute. Either the grid
    idiom takes a column count and a minimum track width instead of a template, or the
    author states the stacking width.
- **#37 Layout elements, as today.** `lf-grid` and the width attributes stay registered
  vocabulary with their own rules and checks. With the run-time coupling fixed they cost
  less than before, but they remain rules the agent learns and Leaf keeps consistent,
  and the gate stays blind to an agent's own layout.
- **#30 Templates.** Named page shapes with slots. Strongest consistency, but the long
  tail falls outside them, and choosing the arrangement moves from the agent to Leaf,
  which the AGENTS.md principle rules out as a default. Better as examples to copy.

## Recommendation

Adopt #36, after making the width fully static.

First, finish what the overlays start: stop wide blocks at the rail statically instead
of through `data-lf-yield`, make the bottom bar's and the tab strip's clearances
constants, and drop the surface minimum height. Then the page's width is the agent's to
know, which was the goal.

Then move arrangement into `$idioms`. The case for it is that Leaf's job for
presentation is to help without constraining. An idiom gives a good default that carries
the user's preferences, and stepping outside it costs the agent nothing, provided the
gate judges the result rather than the vocabulary. The "three forms" wording goes in the
same change: a wide page is an idiom, and a workspace is an interaction element that
holds the window when it is the page's only content.

Keep wide blocks. Figures wider than the text are a layout agents and readers both use,
and widget sizing depends on them.

Decide one more thing alongside: margin notes and the rail share the right margin
(`theme.css:699`). Either the right margin is Leaf's alone and notes move to the left or
into flow, or Leaf places notes and cards together and keeps that layout job.

## How to decide

The overlays, the fixed rail, and the static-width fixes above are worth landing on
their own. For arrangement, run the backlog's authoring comparison
(`notes/workspace-followups.md`, #19 there) with #36 and #35 as the arms. Give fresh
agents the same subjects (a document, a dashboard, a queue with its detail), and compare
gate failures at a phone and a laptop width, iterations, page CSS written, how a
standing preference lands, and which page a reviewer who has not seen the guidance
prefers. `notes/agent-usability-evals.md` has the harness.
