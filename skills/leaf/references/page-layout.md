# Page layout

Read this before giving a page a Layout other than the reading column, widening or
bounding a block, putting contents or notes in the margin, styling Leaf's controls, or
showing several contributors' activity. `page-authoring.md`, "Composing a page", says
which shape fits which subject.

## Layouts

A Layout is a class that arranges the box it is on. Three set the page's shape. Each
goes on `main`, or on a child of a `main` that carries none, which the page then lays
out as it would `main` while that child is shown, as each part of a page of parts
does ("A page of parts"):

| Class              | The page                                                            |
| ------------------ | ------------------------------------------------------------------- |
| `layout-column`    | the reading column, with wide blocks breaking out of it             |
| `layout-sidebar`   | a body beside its `aside`, with a `header` and `footer` across both |
| `layout-workspace` | a screen filling the window: `header`, one body, `footer`           |

One arranges a block's children:

| Class          | Arranges                             |
| -------------- | ------------------------------------ |
| `layout-tiles` | equal cells, as many to a row as fit |

On a column page, a board or diagram declares its own width, and any other block, such
as a table, a trace or a playground, can ask for one with `data-width` ("Bounds and
widths"). The block breaks out of the column and the prose stays centred.

On a sidebar page, every block, the title included, starts at the same left edge and
fills its region. Text, an `lf-ask`, a callout, and widgets read as text such as an
option list keep the reading measure, on a column page too. Give a table, chart or
playground inside an `lf-ask` or callout its own `data-width`.

A workspace fills the window. It has no reading measure, every block fills its region,
and `data-width` has no effect. Where a region would hold prose too wide to read,
narrow its grid track or cap its blocks in the page's `<style>`, such as
`#queue > lf-tab > * { max-inline-size: var(--wide); }`.

The page's own `<style>` comes after the Layout, so ordinary rules can change a track
share, a gap or an order. Where a Layout fits, use it rather than rebuilding it; a page
that no Layout fits writes its own grid or flex rules.

## A page of parts

A page whose subject has parts of different shapes, such as a playground to try, the
proposal it argues for and the reasoning behind it, puts each in a part of its own with
the Layout that suits it. Write one `lf-parts` in a `main` that carries no Layout, and
give each `lf-part` one child carrying that part's Layout:

```html
<main>
  <header>
    <h1>Floating comment panel</h1>
  </header>
  <lf-parts id="parts">
    <lf-part id="try" label="Try" summary="The panel, live">
      <div class="layout-workspace">…</div>
    </lf-part>
    <lf-part id="proposal" label="Proposal" summary="What changes and why">
      <article class="layout-column">…</article>
    </lf-part>
  </lf-parts>
</main>
```

The page's `header`, the one element to write before the parts, heads a column down the
window's left edge, and the list of parts stands under it, with each part's `summary`
under its label. Both stay in view while a long part scrolls. Each part takes the rest of
the width from the top of the window, so a workspace part fills the window. Keep the
header to the page's title, since it shares the column's width, and give each part its
own heading, and a column part its own contents outline. On a phone the title stands
over the list, which becomes a row that sticks over the part. Each part opens where the
user last read it. The parts share the
page's history, Threads panel and On me list.

Where the views share one Layout and the page's header runs across the top, as a site's
pages that share one header do, use page tabs instead (the `lf-tabs` entry).

## A sidebar page

Use `<main class="layout-sidebar">` when the reader works through one region while
keeping another in view: a board with its status, a release dashboard, or a review whose
verdict and file list stay beside the code. The region kept in view is the `aside`:

```html
<main class="layout-sidebar">
  <header>
    <h1>…</h1>
    <p class="lede">…</p>
  </header>
  <aside id="status">
    <div class="overview">
      <lf-toc id="contents"></lf-toc>
      <p>…</p>
      <!-- short verdict or status -->
    </div>
  </aside>
  <div id="body">…</div>
  <!-- document and supporting evidence -->
</main>
```

The body and `aside` sit side by side, two thirds and one third, down to about 870px,
and stack in source order below that or when the body's content needs the whole width.
Write the `aside` first when the reader of the stacked page reads it first, such as a
verdict; it then sits on the left. Write it after the body when it follows the work,
such as a dashboard's log; it then sits on the right. Stack the regions inside the body
and inside the `aside`, so every region shares the same two vertical edges, rather than
splitting each row anew.

A long page read top to bottom is a column page with its contents in the margin, not a
sidebar page, unless the reader also keeps a panel of its own in view, such as a
verdict and its questions beside the document it judges; that panel is the `aside`.

Put everything the `aside` holds in one block, as the `div` above does. While the two
sit side by side, Leaf keeps that block in view at the window's top as the body scrolls.
Write no `position`, `top`, height or overflow for it.

Draw each region as a `section.panel` with a short heading. Use one `.callout` with a
status tone (`warn`, `danger`, `ok`) for the thing the reader must act on, and `.tag`
chips under the lede for the page's state.

## A workspace

`<main class="layout-workspace">` fills the window above Leaf's panel, and the reader
works in its regions rather than scrolling the page. The `header` and `footer` take
their content's height and the body takes the rest. Keep the header to one row: the
title, `.tag` chips for the page's state, and an `lf-tally` for the obligations left. Put what
a lede would say at the top of the region it is about.

The body is one `lf-pane`, a widget that lays out its own regions, or the page's own
grid of panes:

```html
<main class="layout-workspace density-working">
  <header>
    <h1>…</h1>
    <p><span class="tag warn">…</span></p>
  </header>
  <div id="regions">
    <lf-pane id="log" label="Log">…</lf-pane>
    <lf-pane id="chart" label="Chart">…</lf-pane>
  </div>
</main>
```

```css
#regions {
  display: grid;
  grid-template-columns: minmax(16rem, 1fr) 2fr;
}
@media (width < 720px) {
  #regions {
    grid-template-columns: 1fr;
  }
}
```

Stack the panes below 720px, where the page can scroll; above that, stacked panes share
one window height. Each pane's body scrolls on its own, so write no positioning to keep
a pane or footer in view. Keep a region's decision in view with its supporting content,
trimming or splitting a pane that overflows; a pane holding a long file or log can
scroll.

`density-working` is a style, not a Layout. It sets smaller type, tighter spacing and
options as rows on any block, for a surface the reader operates. A workspace usually
takes it, and so can a dense table on a column page.

For a queue of items decided one at a time, such as tickets or findings, make the body
one `lf-tabs list="side"` with an `lf-tab` per item, and put an `lf-tally` with `next`
in the header. The list marks each tab's open obligations and the tally counts what is left,
so write no script or count of your own. The `lf-tab` and `lf-tally` entries cover
grouping and counting.

## Bounds and widths

Prefer one page scroll: let content grow in place, with supporting detail in
disclosures. Bound a region's height only when the reader keeps it in view while its
content changes, as in a workspace or a live stream. Length alone is no reason.

For a live stream, set `data-bound` to the end where new entries arrive:
`data-bound="end"` for a list that grows downward, which follows the last line while
the user is at the bottom, and `data-bound="start"` for a newest-first list. Don't make
a box scroll vertically with page CSS: Leaf keeps no reading position in a scroll box
it didn't make.

`data-width` widens one block, overriding its widget's default. Put it on the block
itself, such as a `table`, `lf-code` or `lf-diff`, and write no CSS that copies its
widths. It works on column and sidebar pages:

- `data-width="wide"` makes the block as wide as `--wide`, the shared width for
  evidence, growing past the column where the column is narrower than that.
- `data-width="available"` takes all the width Leaf's chrome and the margin leave free,
  stopping short of a margin sidebar or the contents map.

A `table` with either value is only as wide as its columns need, up to that width. A
block inside an `lf-ask` or callout breaks out only with its own `data-width`; the
`lf-ask` keeps the column. A block breaks out only from a box that spans the column,
such as a section or an `lf-ask`. One inside a box standing in from the column, such as
a list item, or a box the page lays out itself, such as a grid or flex item, stays in
that box, and a table there scrolls sideways.

A widget whose entry declares `x-height`, such as `lf-chart`, reserves that height
before it draws; `data-height` on the element overrides it. A widget whose drawing sets
its own height, such as `lf-diagram` or `lf-diff`, reserves nothing, so content below it
moves when it draws unless you set `data-height`. `page check --render` suggests the
height wherever a drawing differs from what was reserved.

Show evidence at the scale needed to judge it: an aligned detail view of a local
change with the whole object available for context, or whole frames when their
composition is the point.

## The rail and the margin

Leaf places comment markers in a rail beside the column, or over their target where
nothing beside it is free. Don't pad a heading to make room for its marker; the reader
hides markers with `o`, or the leaf's menu → Annotations → Hide annotations, to read
what's under one.

On a column page, write the contents outline in the first `aside.sidebar` and short
notes in `aside.sidenote`. Leaf moves them into the margin when they fit and leaves
them where you wrote them in a narrow window. For CSS that depends on what is in the
margin, read the tokens in the `data-lf-margin` of the box carrying `layout-column`
(`rail`, `map`, `sidebar`, `note`), such as
`.layout-column:not([data-lf-margin~="sidebar"]) #route { display: none }`, and check
the page at the widths where an item leaves the margin.

`data-rail="right"` on `body` gives a sidebar page a rail, and `data-rail="none"` gives
a column page's right margin to the page's own content. A workspace has no rail; a
comment there shows as a pin on its block.

## Page-owned annotations

By default Leaf draws comment markers, passage highlights and threads over the page.
`data-annotations="page"` on `body` turns these off for a page that shows comments in
its own layout; comments, On me obligations, Undo and live revisions still work, and comments open
in the Leaf panel. To show conversations in the page's own layout, register a
presentation as `module-annotations.md`, "Page annotation presentation", describes,
rather than rebuilding the event log in page code.

## Page CSS and Leaf's controls

The page's CSS styles the page's content, not Leaf's panel, thread cards or the controls
widgets build: a rule for `button` styles only the page's own buttons. To style Leaf's
controls on purpose, put their rules in a separate `<style data-controls>` or
`<link rel="stylesheet" data-controls>` element. Its rules and imports stand as
written; use selectors that reach only the controls you intend to change. Set the marker
before attaching a dynamic sheet. Theme packages use `controls.css` (`packages.md`,
"Styles and composition"). A token such as `--accent` on `:root` changes every surface that reads it. For
a page-specific inset, use the frame declaration in `package-themes.md`, "A theme
change".

To make a control you write match Leaf's, give it `class="button"`,
`class="button primary"` for the committing action, or `class="field"` for a text
input or select.

Leaf's panel, thread cards and markers draw over everything in `main`, whatever its
`z-index`. Open a modal or menu of the page's own in the top layer: a `<dialog>` shown
with `showModal()`, or an element with `popover`.

`conversation-loop.md`, "The On lists", says what belongs in the On lists. A
package can lay out conversations and obligations itself with the APIs in
`module-annotations.md`, "Owning the primary conversation presentation", and
`module-reading.md`, "Reading obligations and the On lists".

## Activity from several contributors

On a one-agent page, Leaf's panel shows the agent's activity. When several workers report
to one orchestrator, write a page-owned adapter that declares their report verbs and
reads task and worker state from the public work projection. A page several people
revisit, such as a working board or long review, can show recent changes in an
`lf-activity` feed.
