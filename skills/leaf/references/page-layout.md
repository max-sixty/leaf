# Page layout

Read this before giving a page a Layout other than the reading column, widening or
bounding a block, placing its contents or notes in the margin, styling Leaf's
controls, or showing several contributors' activity. `page-authoring.md`,
"Composing a page", says which shape fits which subject.

## Layouts

A Layout is a class that arranges the box it is on. Three set the page's shape, on
`main` alone:

| Class | The page |
| --- | --- |
| `layout-column` | the reading column, and a block's breakout beside it |
| `layout-sidebar` | a body beside its `aside`, with a `header` and `footer` across both |
| `layout-workspace` | a screen filling the window: `header`, one body, `footer` |

One arranges a block's children:

| Class | Arranges |
| --- | --- |
| `layout-tiles` | equal cells, as many to a row as fit |

Wide content on a column page breaks out of the column by its own declaration: a board
or a diagram declares its width, and `data-width` asks for one on any other block, such
as a table, a trace or a playground ("Bounds and widths"). The
prose keeps its axis around it.

On a sidebar page, every block, the title included, starts at one left edge and takes
its region's width, while text keeps the reading measure, as does a widget read as
text, such as an option list or a draft. A sidebar page is capped at the widest page
and sets its title larger.

On a column or sidebar page, an `lf-ask` and a callout keep the reading measure. Give
the chart, table, playground or other surface inside one that needs more room its own
`data-width`.

A workspace takes the whole window and leaves its title to the theme. It sets no
reading measure and no `wide` width, so every block, text included, fills the region it
stands in, and `data-width` changes nothing. The page's grid sizes the regions: where
one would hold prose wider than it reads well, narrow its track, or cap its blocks in
the page's `<style>`, such as `#queue > lf-tab > * { max-inline-size: var(--wide); }`
for a queue whose items each read top to bottom.

A Layout is a starting point. The page's own `<style>` comes after it in the cascade, so
an ordinary rule adjusts it — a different track share, a gap, an order — and a page
whose arrangement no Layout fits writes its own grid or flex rules on its own boxes.
Where a Layout fits, use it rather than rebuilding it, since its tracks already hold
the widths and wrapping every page needs.

## A sidebar page

When the regions are the page rather than exhibits in an argument — a board with its
status, a release dashboard, a long review whose contents and verdict stay beside the
code — widen the page itself. `<main class="layout-sidebar">` sets what the reader
works through beside what they keep an eye on — status, counts, the verdict's
follow-ups, the contents — which is the Layout's `aside`, with the page's `header` above
both:

```html
<main class="layout-sidebar">
  <header><h1>…</h1><p class="lede">…</p></header>
  <aside id="status">
    <div class="overview">
      <lf-toc id="contents"></lf-toc>
      <p>…</p>                 <!-- short verdict or status -->
    </div>
  </aside>
  <div id="body">…</div>        <!-- document and supporting evidence -->
</main>
```

The body takes two parts of the row and the track one. They stand side by side in a
window down to about 870px, and below that, as on a phone, they stack in the order they
are written. They stack in a wider window too where the body could not keep the width its
content declares: a board whose columns need the room gets the page's whole width rather
than clipping. So write the `aside` where a reader of the stacked page needs it: before
the body when it is what they read first, such as a code review's verdict and the list of
files it covers, where it also stands on the left; after it when it follows the work, such
as a dashboard's checks and log, where it stands on the right. A page read in order is not
one of these for its length alone: its contents stand in the margin beside the column
("The rail and the margin"), and its figures keep the column's measure. It is one when
the reader keeps a panel of its own in view while reading, such as a verdict with the
changes and questions it asks beside the document it judges; that panel is the
`aside`, and sticks (below). Stack each
track's regions inside it, so every region stands on the same two vertical lines, rather
than a new split per row whose edges land somewhere new each time.

`page-authoring.md`, "Contents navigation", sets where the overview's outline goes at
each width.

To keep the track in view while the body scrolls beside it, put everything the track
holds in one block, as the `div` in the example above does. While the track stands
beside the body, the Layout sticks that block just below Leaf's banner and any page tab
strip, and a block taller than the window scrolls on its own, so its end stays
reachable. Where the two stack, the block scrolls with the page, and a track of several
blocks always does. Write no `position`, `top`, height or overflow for the track or the
blocks in it.

Draw each region the same way, as a `section.panel` with a short heading, and keep a
`.callout` with a status tone (`warn`, `danger`, `ok`) for the one thing the reader must
act on; a row of `.tag` chips in the same tones under the lede says the page's state at a
glance.

## A workspace

`<main class="layout-workspace">` is a screen: it fills the window's height below the
banner, and the reader moves through it, choosing what its regions show, rather than
scrolling it. Its `header` and `footer` take what they hold, and its one body between
them takes the rest. The header is one row, the title with the page's state beside it,
so the regions keep the window: `.tag` chips for what you state, such as how the items
divide, and an `lf-tally` for how many of the page's asks are left, which the page
counts as the user answers. Write no lede, eyebrow or legend there, and put what a
lede would say at the top of the region it is about, or in a footer of a line or two.
The body is one `lf-pane`, a
widget that composes its own regions, or the page's own grid of panes, such as a run's
log beside the chart it explains, which the page's `<style>` places:

```html
<main class="layout-workspace density-working">
  <header><h1>…</h1><p><span class="tag warn">…</span></p></header>
  <div id="regions">
    <lf-pane id="log" label="Log">…</lf-pane>
    <lf-pane id="chart" label="Chart">…</lf-pane>
  </div>
</main>
```

```css
#regions { display: grid; grid-template-columns: minmax(16rem, 1fr) 2fr; }
@media (width < 720px) { #regions { grid-template-columns: 1fr; } }
```

Stack the panes below 720px, where the Layout lets the page scroll: panes stacked in a
wider window still share its one height.

`density-working` is a style, not a Layout: on any block it sets smaller type, tighter
spacing and options as rows, for a surface the reader operates rather than reads down.
A workspace usually takes it, and so can a dense pane or table on a column page.

A queue whose items open one at a time beside it, such as tickets, cases or findings to
decide, is one `lf-tabs list="side"` as the body: its list is the queue and each item an
`lf-tab`, so one opens beside the list and a link or an ask opens its own, and each
row marks its item's asks: open until they are all answered, then a check, with the
picked answer beside it where the item holds one ask. Write no script to select, hide
or mark an item; the tab set does all three. Say how much of the queue is left with an
`lf-tally` naming it in the header, with `next` for a control to the next open ask: it
counts the asks as the user answers them, where a count written into a chip or the
prose is wrong after the first answer. Where the items fall into kinds the user works
through in turn, such as merge, close and FYI, give each `lf-tab` its kind as `group`
and keep each kind's items together: the list sets each run under a heading of its
group.

The page itself does not scroll; a region does, where what it holds runs past it. Each
pane's body scrolls on its own, and a widget that fills the body, such as a playground's
stage, grows to the window's height. The `lf-pane` entry says what a pane holds. Let the
Layout allocate the height: page-specific positioning should not be needed to keep a
pane or footer reachable. Where the window is too small to hold the regions, they take
their natural height and the page scrolls.

Keep a region's decision visible with its supporting content: trim or split a pane
whose body runs past its region. A region for reading long content, such as a source
file or log, can keep its scrolling.

## Bounds and widths

Prefer one document scroll: let reading content and evidence grow in flow, with
disclosures for supporting detail. Internal vertical scrolling needs a task that
benefits from keeping a region in view while its contents move, as in a workspace,
or a live stream whose newest entry the reader follows. Length alone is no reason
to bound a listing or an inspection widget.

For a live stream that needs a bounded reading region, use `data-bound`, naming
the end its newest entry is at. A list that grows downward takes
`data-bound="end"`, which follows its last line while the user is at the end and
leaves them where they scrolled back to otherwise. A newest-first list takes
`data-bound="start"`, which opens at the top, as the page's activity feed does.
Don't make a box scroll vertically with page CSS: Leaf keeps no reading position
in a scroller it did not make.

An individual block or section may request a responsive allocation with
`data-width="wide"` or `data-width="available"`, which overrides a widget's or idiom's
default. On a column or sidebar page, `wide` uses the shared evidence width, `--wide`:
past a column it grows to that width, and in a wider body it holds to it at its start.
A narrower frame still bounds it. `available` uses all room left by the page
shell, frames, chrome, and a margin resident that takes its side, such as a sidebar
standing in the margin or the contents map's spine; the markers beside it then stand as
pins on it, and it moves below a note hanging level with it. A native `table` given
either takes its columns' natural width up to that room: one that fits where it stands
starts where the text around it starts, and a wider one grows evenly about the prose
axis, or to the right where a sidebar stands in the left margin. A block in a list item
or another indented block takes its room from the column, so it stands where the same
block in the page's flow would, however deep the indent. A block the page places
itself, as an item of its own grid or flex row, in an inline block, or inside one,
keeps to the box it is given, since the room beside that box is the page's: a table
there scrolls its columns inside it.
An `lf-ask` or a callout keeps the column: a block of its own that declares a width
breaks out of it on a column page, and widens it in a wider flow.
Use these names on the semantic block itself, including a native `table`, `lf-code`, or
`lf-diff`; do not reproduce their responsive widths in page CSS.

A widget whose entry declares `x-height`, such as `lf-chart` or `lf-diagram`, is drawn
by its module at a height the page holds before the drawing arrives: the entry's
number, or an occurrence's `data-height`, in CSS pixels. `lf-chart` draws at that
height. A widget whose drawing has a height of its own, such as `lf-diagram` or
`lf-diff`, has no number, so what follows it moves when it is drawn unless the
occurrence states that height. `page check --render` advises the height to state
wherever a drawing differs from what the page held.

Show evidence at the scale needed to judge it. For a local change, supply an aligned
detail view with the complete object available for context; use whole frames when their
composition is the subject. A fitted thumbnail is an overview, not a substitute for
readable detail. Let the package provide inspection controls and Leaf allocate space and
scrolling; page-local width overrides and wheel handlers should not be needed.

## The rail and the margin

Leaf seats annotation markers in a rail beside the column or by their targets, over
the target itself where nothing beside it is clear; the reader hides annotations to
see beneath. User-opened controls and threads can overlay content. Padding a heading
for its pin leaves unused space when the marker is in the rail.

On a column page, write its contents outline in the first `aside.sidebar` and
short notes in `aside.sidenote`. Leaf moves them into the margin when they fit;
in a narrow window they stay where you authored them. A `layout-sidebar` page
instead has an authored body and `aside` region ("A sidebar page").

For CSS that depends on a margin resident, use `main`'s `data-lf-margin` tokens
(`rail`, `map`, `sidebar`, `note`), such as
`main:not([data-lf-margin~="sidebar"]) #route { display: none }`. Verify the
page at the widths where a resident returns to the document flow.

`data-rail="right"` on `body` keeps a rail on a sidebar page. A workspace has none,
since its panes scroll on their own: a comment there stands on its block as a pin.
`data-rail="none"` gives a column page's right margin to the page's own content.
A marker beside a hanging `aside.sidenote` already appears as a pin, so notes
need neither override.

## Page-owned annotations

Leaf's default draws markers, passage marks and contextual replies over the page.
For an arrangement that places annotations in the document instead, select
`data-annotations="page"` on `body`. This choice omits the overlay's modules,
styles and geometry. Exact comments, asks, decisions, Undo, live revisions and
drawing capture still use the shared Leaf mechanisms. Changing the selection
replaces the document through the ordinary revision lifetime.

With nothing more, comments open in Threads, which remains the complete
conversation index, and selection offers the banner's Comment on selection control.
A page or package that shows conversations and actions in its own layout registers
a presentation through "Page annotation presentation" in `module-annotations.md`; do
not reconstruct the event log or annotation inventory in page code.

## Page CSS and Leaf's controls

For a page-specific inset, use the frame declaration in `references/package-themes.md`,
"A theme change".

The page's own CSS reaches the page's content and leaves Leaf's apparatus alone: the
banner, the thread panel, and the controls a widget builds. A rule for `button` or
`input` dresses the page's own buttons and fields, and a face set on `body` stops at
those controls. To change them on purpose, name the widget they stand in or Leaf's
class for them: `lf-options button`, `lf-board .lf-grip`, or, for controls a page
module builds with `offer`, the page's own element (`my-explorer .toolbar`). A token
such as `--accent` on `:root` changes every surface that reads it.

A control the page writes itself matches Leaf's own when it carries Leaf's class:
`class="button"` on a button, `class="button primary"` on the committing action, and
`class="field"` on a text input or select. Without one, a control in `main` takes
Leaf's type and keeps the browser's frame.

Leaf's banner, panels, highlights and markers paint over everything in `main`,
whatever `z-index` the page gives it. A box of the page's that must stand over them,
such as its own modal or menu, opens in the top layer: a `<dialog>` shown with
`showModal()`, an element with `popover`, or fullscreen. Since `main` is a stacking
context, a box in it with `mix-blend-mode` blends only with what `main` paints, not with
`body`'s background behind it.

The runtime injects the status banner, thread panel, Versions menu, keyboard
shortcuts, live-leaves drawer, and On panel. `conversation-loop.md`,
"The On lists", owns what belongs in those lists and how to inspect them.
Readers can turn off **Quick keyboard shortcuts** under **More → Keyboard shortcuts**.
This preference persists across pages on the same origin and removes Leaf's character
shortcuts and their hints; commands and ordinary control navigation remain available.
A package can arrange conversations and obligations with the canonical APIs in
`module-annotations.md`, "Owning the primary conversation presentation", and
`module-reading.md`, "Reading asks and obligation queues". Leaf owns their state, rendering, and activation;
page composition can choose their layout.

## Activity from several contributors

Compose worker readings with a page-owned adapter when multiple workers report
to one orchestrator. Declare their report verbs and use the public work projection
for task and worker state. On a one-agent page, the banner carries that activity. A revisited
page with several contributors, such as a working board, command hub, or long
review, can use `lf-activity` to show recent changes; a read-once page needs no
activity feed.
