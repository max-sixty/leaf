# Page layout

## Layouts

A Layout is a class that arranges the box it is on. Three set the page's shape. Each
goes on `main`, or on a child of a `main` that carries none, as each part's child does
in a page of parts ("A page of parts"):

| Class              | The page                                                            |
| ------------------ | ------------------------------------------------------------------- |
| `layout-column`    | the reading column, with wide blocks breaking out of it             |
| `layout-sidebar`   | a body beside its `aside`, with a `header` and `footer` across both |
| `layout-workspace` | a screen filling the window: `header`, one body, `footer`           |

`layout-tiles` arranges a block's children in equal cells, as many to a row as fit.

On a sidebar page, every block, the title included, starts at the same left edge and
fills its region. Text, an `lf-ask`, a callout and widgets read as text, such as an
option list, keep the reading measure there as in a column. A workspace has no reading
measure: every block fills its region, and `data-width` has no effect. Where a
workspace region would hold prose too wide to read, narrow its grid track or cap its
blocks in the page's `<style>`, such as
`#queue > lf-tab > * { max-inline-size: var(--wide); }`.

The page's own `<style>` comes after the Layout, so ordinary rules can change a track
share, a gap or an order. Where a Layout fits, adjust it rather than rebuilding it; a
page that no Layout fits writes its own grid or flex rules.

## A page of parts

Write one `lf-parts` in a `main` that carries no Layout, after a `header` holding the
page's title, and give each `lf-part` one child carrying that part's Layout:

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

The header and the list of parts share a column down the window's left edge, so keep
the header to the page's title. Each part takes the rest of the window, so give each
its own heading, and a column part its own contents outline.

## A sidebar page

`<main class="layout-sidebar">` keeps one region, the `aside`, in view while the reader
works through the body: a board's status, a release dashboard's log, or a review's
verdict and file list beside the code:

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

The body and `aside` sit side by side, two thirds and one third, while the window has
room for both, and stack in source order when it hasn't or when the body's content
needs the whole width. Write the `aside` first when the reader of the stacked page
reads it first, such as a verdict; it then sits on the left. Write it after the body
when it follows the work, such as a dashboard's log; it then sits on the right. Stack
the regions inside the body and inside the `aside` rather than splitting each row
anew, so every region shares the same two vertical edges.

Put everything the `aside` holds in one block, as the `div` above does, and keep it
short enough to fit the window. Leaf keeps that block in view as the body scrolls, so
write no `position`, `top`, height or overflow for it.

## A workspace

`<main class="layout-workspace">` fills the window above Leaf's panel, and the reader
works in its regions rather than scrolling the page. The `header` and `footer` take
their content's height and the body takes the rest. Keep the header to one row: the
title, `.tag` chips for the page's state, and an `lf-tally` for the obligations left.
Put what a lede would say at the top of the region it is about.

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
a pane or footer in view. Keep a region's decision in view with the content that
supports it, trimming or splitting a pane that overflows; a pane holding a long file or
log can scroll.

`density-working` is a style, not a Layout: smaller type, tighter spacing and options
as rows, for a surface the reader operates. A workspace usually takes it, and so can a
dense table on a column page.

For a queue of items decided one at a time, such as tickets or findings, make the body
one `lf-tabs list="side"` with an `lf-tab` per item, and put an `lf-tally` with `next`
in the header. The list marks each item's open obligations and the tally keeps count of
what is left, so write no script and state the count nowhere else. Each tab's `summary`
shows under its label, so the user can choose an item without opening it. Start the
summary with what the item is about, such as the problem a ticket reports, unless the
label already says so, then say what sets it apart from its neighbours, such as its age
or suggested outcome. Where items fall into kinds the user works through in turn, such
as merge, close and FYI, give each item its kind as `group` and place each kind's items
together in the order to take them. The group's heading names the kind, so leave it out
of the summary.

## Bounds and widths

Prefer one page scroll: let content grow in place, with supporting detail in
disclosures. Bound a region's height only when the reader keeps it in view while its
content changes, as in a workspace or a live stream. For a live stream, set
`data-bound` to the end where new entries arrive: `end` for a list that grows downward,
which follows the last line while the user is at the bottom, and `start` for a
newest-first list. Don't make a box scroll vertically with page CSS: Leaf keeps no
reading position in a scroll box it didn't make.

On a column or sidebar page, a board or diagram declares its own width, and
`data-width` on any other block, such as a `table`, `lf-code` or `lf-diff`, widens it
while the prose stays in place. Write no CSS that copies its widths:

- `data-width="wide"` makes the block as wide as `--wide`, the shared width for
  evidence.
- `data-width="available"` takes all the width Leaf's chrome and the margin leave free.

A `table` with either value is only as wide as its columns need, up to that width. A
block breaks out only from a box that spans the column, such as a section or an
`lf-ask`. A block inside an `lf-ask` or callout needs its own `data-width`, while the
`lf-ask` keeps the column. A block inside a box that stands in from the column, such
as a list item, or a box the page lays out itself, such as a grid or flex item, stays
in that box, and a table there scrolls sideways.

A widget whose entry declares `x-height`, such as `lf-chart`, reserves that height
before it draws, and `data-height` on the element overrides it. A widget whose drawing
sets its own height, such as `lf-diagram` or `lf-diff`, reserves nothing, so content
below it moves when it draws unless you set `data-height`. `page check --render`
suggests the height wherever a drawing differs from what was reserved.

## The rail and the margin

Comment markers sit in a rail beside the column, or over their target where nothing
beside it is free. `data-rail="right"` on `body` gives a sidebar page a rail, and
`data-rail="none"` gives a column page's right margin to the page's own content. A
workspace has no rail; a comment there shows as a pin on its block.

With page tabs, each tab can start with its own `aside.sidebar` and empty `lf-toc`,
which stands below the tab strip and moves into the margin when there is room. A
sidebar written directly in the column keeps that place when there is one, and
sidebars in nested tabbed boxes stay in flow. Write short notes in `aside.sidenote`.

For CSS that depends on what is in the margin, read the tokens in the `data-lf-margin`
of the box carrying `layout-column` (`rail`, `map`, `sidebar`, `note`), such as
`.layout-column:not([data-lf-margin~="sidebar"]) #route { display: none }`, and check
the page at the widths where an item leaves the margin.

## Page-owned annotations

`data-annotations="page"` on `body` turns off the comment markers, passage highlights
and threads Leaf draws over the page, for a page that shows comments in its own layout.
Comments, On me obligations, Undo and live revisions still work, and comments open in
the Leaf panel. To show conversations in the page's own layout, register a
presentation (`module-annotations.md`, "Page annotation presentation") rather than
rebuilding the event log in page code.

## Page CSS and Leaf's controls

The page's CSS styles the page's content, not Leaf's panel, thread cards or the controls
widgets build: a rule for `button` styles only the page's own buttons. To style Leaf's
controls on purpose, put their rules in a separate `<style data-controls>` or
`<link rel="stylesheet" data-controls>` element, and set that marker before attaching a
dynamic sheet. Its rules and imports stand as written, so use selectors that reach only
the controls you intend to change. A token such as `--accent` on `:root` changes every
surface that reads it. For a page-specific inset, use the frame declaration in
`package-themes.md`, "A theme change".

To make a control you write match Leaf's, give it `class="button"`,
`class="button primary"` for the committing action, or `class="field"` for a text input
or select. Wrap a native radio or checkbox in a `label.choice`:
`<label class="choice"><input type="radio" name="view" value="summary">Summary</label>`.

Leaf's panel, thread cards and markers draw over everything in `main`, whatever its
`z-index`. Open a modal or menu of the page's own in the top layer: a `<dialog>` shown
with `showModal()`, or an element with `popover`.

## Activity from several contributors

Leaf's panel shows the agent's activity. When several workers report to one
orchestrator, write a page-owned adapter that declares their report verbs and reads
task and worker state from the public work projection. A page several people revisit,
such as a working board or long review, can show recent changes in an `lf-activity`
feed.
