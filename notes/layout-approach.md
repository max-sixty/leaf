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

The rule the overlays point to is that nothing Leaf draws at run time moves the page's
content. Everything Leaf adds is an overlay, with one exception fixed before the page is
written: the rail's reservation. Held to that rule, the page's geometry depends only on
the window and a few constants the agent can be told, which is the knowledge the agent
was missing.

With the tray and panel covering and the rail fixed, these still move content and would
change under the rule:

- **Thread cards.** A card moves text in two ways today. When one lands level with a wide
  block, `margin-layout.js` marks the block (`data-lf-yield`) and the theme pulls the
  block back from the rail (`theme.css:1957-1960`). And where a card cannot stand in
  the rail (below 840px, or in `fixed-rail` a card wider than the rail) it docks into the
  text as a line of its own (`theme.css:1649`), pushing everything below it down. Under
  the rule, a card stands in the rail when the rail is shown and otherwise overlays: a
  marker at the passage's edge, with the card opening over the page when pressed. Wide
  blocks stop short of the rail whenever it is shown, so no card can collide with one.
  Docking and the yield mark both go.
- **The bottom bar and the page-tab strip.** The bottom bar is the keyboard-shortcut
  line and the status notices in the window's bottom corners; the page-tab strip is
  stuck under the banner on a page with page tabs. Both already float over the page, but
  Leaf measures each and moves content to clear them: room added at the page's end, and
  a workspace shortened by their heights (`chrome-layout.js:137-184`,
  `lf-tabs.js:318-330`, `default/theme.css:239-250`). Under the rule they only cover. A
  pane footer at the window's foot then sits under the shortcut line, which takes no
  presses, so the footer's controls still work. A scroll stop that lands a jump below
  the tab strip moves no content and stays.
- **Opening a surface.** An open surface sets a minimum height on `body`
  (`theme.css:538-543`), which the overlay branch keeps. Under the rule it goes.

What is left is the margin and the bottom bar.

### The bottom bar as a band

The banner is already the model. It is fixed at the top at a height the theme states per
breakpoint (`theme.css:131, 396-399`), content scrolls under it, and the page starts
below it. A bottom bar held to one stated height works the same way: the page ends that
far above the window's foot, a workspace is the window less the banner and the band, and
nothing is measured. What makes the bar measured today is that its height varies: the
status stacks above the shortcut line when the two would collide
(`chrome-layout.js:130-141`), and the line wraps when the complete reference is shown
(`shortcut-bar.js:428`). In a band, the status shares the row, taking the line's place
while it shows. The complete reference, which the user asks for with `?`, opens upward
over the page as a temporary overlay, like Threads. On a touch screen, where there are no
keys to hint, the band holds only the status.

### The margin as a rail or pins

The rail today is narrow: a column of 32px markers, one per annotated target, reserved
at about 60px (`theme.css:1886`). A marker gathers everything anchored to its target:
threads, Asks, version changes, delivery receipts, work claims, and package controls
(`margin-projection.js:1-10`). The thread card is already an overlay. It opens when the
user arrives at a target, beside the marker when the rail has room and over the column
otherwise (`margin-projection.js:23-33`). What moves text is where a marker goes when
there is no rail: it docks into the flow as a line of its own.

So the margin needs two homes for markers, and neither should move content:

- **The rail**, a reserved column at the page's right edge, where markers never cover
  anything. A page with no layout CSS has one, since a document read top to bottom is
  where a marker beside each passage reads best and a centred column leaves the room. A
  page that composes its own layout declares whether it has one, as it declares any other
  part of its arrangement. Its width is a constant, so the agent knows exactly what it
  costs.
- **Pins**, where there is no rail: on a page that declared none, below the width where
  a rail fits, or inside a pane that scrolls on its own. A pin is the same marker drawn
  over the content at the right edge of its target's block, as Figma draws comment pins
  on the canvas. Pressing it opens the same card. Pins replace docking.

One key, `o` (unbound today), shows or hides the annotation layer: markers, pins, and
the marks on anchored passages. It changes no geometry, since a rail stays reserved
while its markers are hidden, so it works the same way in both homes. Hiding them is
view state, like scroll position, and is not written to the log. While they are hidden,
the banner's count still says when something new arrives.

This also settles who owns the right margin. The rail is a reservation the page declares,
so an agent that wants margin notes beside its prose places them itself and leaves the
rail out, or puts its notes on the left.

The costs: pins cover up to 32px of content at a block's right edge, which on a dense
dashboard can be a number; `o` answers it. And a reader loses the at-a-glance column of
markers on pages without a rail, keeping the Threads panel as the full index.

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

Adopt #36, after holding Leaf to the rule that nothing it draws moves the page's content.

First, finish what the overlays start. Markers stand in a rail the page declares, or
as pins over the content, and never dock; `o` shows and hides them. Wide blocks stop short
of the rail whenever it is shown, replacing `data-lf-yield`. The bottom bar becomes a band
of one stated height, like the banner. An open surface sets no minimum height. Then the
page's geometry is the agent's to know, which was the goal.

Then move arrangement into `$idioms`. The case for it is that Leaf's job for
presentation is to help without constraining. An idiom gives a good default that carries
the user's preferences, and stepping outside it costs the agent nothing, provided the
gate judges the result rather than the vocabulary. The "three forms" wording goes in the
same change: a wide page is an idiom, and a workspace is an interaction element that
holds the window when it is the page's only content.

Keep wide blocks. Figures wider than the text are a layout agents and readers both use,
and widget sizing depends on them.

## How to decide

The overlays, the fixed rail, and the fixes above are worth landing on
their own. For arrangement, run the backlog's authoring comparison
(`notes/workspace-followups.md`, #19 there) with #36 and #35 as the arms. Give fresh
agents the same subjects (a document, a dashboard, a queue with its detail), and compare
gate failures at a phone and a laptop width, iterations, page CSS written, how a
standing preference lands, and which page a reviewer who has not seen the guidance
prefers. `notes/agent-usability-evals.md` has the harness.
