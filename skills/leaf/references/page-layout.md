# Page layout

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

On a column page, a board, diagram or diff declares its own width, and any other block,
such as a table, a trace or a playground, can ask for one with `data-width` ("Bounds and
widths"). The block breaks out of the column and the prose stays where it is.

On a sidebar page, every block, the title included, starts at the same left edge and
fills its region. Text, an `lf-ask`, a callout, and widgets read as text such as an
option list keep the reading measure, on a column page too.

A workspace fills the window. It has no reading measure, every block fills its region,
and `data-width` has no effect. Where a region would hold prose too wide to read,
narrow its grid track or cap its blocks in the page's `<style>`, such as
`#queue > lf-tab > * { max-inline-size: var(--wide); }`.

The page's own `<style>` comes after the Layout, so ordinary rules can change a track
share, a gap or an order. Where a Layout fits, use it rather than rebuilding it; a page
that no Layout fits writes its own grid or flex rules.

## A page of parts

Write one `lf-parts` in a `main` that carries no Layout, and give each `lf-part` one
child carrying that part's Layout:

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

The page's `header` is the only element written before the parts. It appears at the
top of a column along the window's left edge, followed by the list of parts, with each part's `summary`
under its label. Each part takes the rest of the width from the top of the window, so
a workspace part fills the window. Keep the header to the page's title, since it shares
the column's width. Give each part its own heading, and a column part its own contents
outline.

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
    <lf-toc id="contents"></lf-toc>
    <p>…</p>
    <!-- short verdict or status -->
  </aside>
  <div id="body">…</div>
  <!-- document and supporting evidence -->
</main>
```

The body and `aside` sit side by side, two thirds and one third, while the page has
room for both, and stack in source order when it hasn't or when the body's content needs
the whole width. To give the `aside` another width, set `--aside` on the `main` to a
length or a share of the row, such as `main { --aside: 20rem; }`. The `aside` uses
that width, the body takes the rest, and the two stack when the body no longer fits
beside it.
Write the `aside` first when the reader of the stacked page reads it first, such as a
verdict; it then sits on the left. Write it after the body when it follows the work,
such as a dashboard's log; it then sits on the right. Stack the regions inside the body
and inside the `aside`, so every region shares the same two vertical edges, rather than
splitting each row anew.

While the two sit side by side, Leaf keeps everything the `aside` holds in view at the
window's top as the body scrolls, however many blocks it is, and scrolls it within the
window when it is taller. Write no `position`, `top`, height or overflow for the `aside`
or its blocks. Leaf does this by gathering the blocks into a box of its own inside the
`aside`, so a rule that names the `aside`'s children, such as `aside > p`, no longer
reaches them: write `aside p`, or name the block by its class or id.

## A workspace

`<main class="layout-workspace">` fills the window behind Leaf's floating panel, and the reader
works in its regions rather than scrolling the page. Pane scrollers leave room at their
ends so the panel does not cover their last lines. The `header` and `footer` take
their content's height and the body takes the rest. Keep shared context concise enough
to leave the working regions usable; place region-specific explanation with its subject.

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

Keep enough space to read each region's evidence and reach its decision. Readers often
open a workspace on a laptop, in a window about 720px tall, so aim to keep each
region's decision in view at that height. Stacked panes share the remaining height
while the workspace is bounded; in a flowing layout they can grow with their content.
Each pane's body can scroll on its own, which helps with a long file or log but cannot
make a cramped working region usable.

`density-working` is a style, not a Layout. It sets smaller type, tighter spacing and
options as rows on any block, for a surface the reader operates. A workspace usually
takes it, and so can a dense table on a column page. On the `main` of a column or
sidebar page, such as a dashboard, it also sets the title at working size and starts
the page nearer the window's top.

For a queue of items decided one at a time, such as tickets or findings, make the body
one `lf-tabs list="side"` with an `lf-tab` per item, and put an `lf-tally` with `next`
in the header. The list marks each tab's open obligations and the tally counts what is
left, so write no script or count of your own, and don't state the count in prose or
chips. Each item's `summary` shows under its label, so the user can choose an item
without opening it. Start the summary with what the item is about, such as the problem
a ticket reports, unless the label already says so, then what sets it apart from its
neighbours, such as its age or suggested outcome. Leave out the item's group, which its
heading shows. Where items fall into kinds the user works through in turn, such as
merge, close and FYI, give each item its kind as `group` and place each kind's items
together in the order to take them; adjacent tabs with the same group share one
heading.

## Bounds and widths

Keep related content easy to read and compare without managing several scroll
positions. A shared page scroll lets content grow together; separate regions help
when the task needs independent positions kept in view. Live updates should preserve
the reader's place and input as content grows.

Make a box scroll vertically with `data-bound` rather than `overflow` alone: Leaf
keeps the reader's place in a bounded box across revisions, and in no other scroller.
`data-bound="start"` opens at the top, and `data-bound="end"`, for a stream that grows
downward, follows the newest entry while the user is at the end. The box takes the
height page CSS gives it, as `max-block-size` or `--lf-bound`, and 28rem otherwise.

`data-width` widens one block, overriding its widget's default. Put it on the block
itself, such as a `table` or `lf-code`, and write no CSS that copies its widths. It
works on column and sidebar pages:

- `data-width="wide"` is for a block slightly wider than the column, such as code up
  to 100 columns, a diff or a table of a few more columns. The block starts at the
  prose's start edge, the left in a left-to-right page, and extends toward its end
  edge to `--wide`, as far as the window allows.
- `data-width="available"` is for a surface that uses every pixel, such as a board, a
  large drawing or a playground. It takes all the width Leaf's chrome and the margin
  leave free, into both margins.

A `table` with either value is only as wide as its columns need, up to that width. A
block inside an `lf-ask` or callout breaks out only with its own `data-width`; the
`lf-ask` keeps the column. A block breaks out only from a box that spans the column,
such as a section or an `lf-ask`. A block inside an indented box, such as a list item,
or a box the page lays out itself, such as a grid or flex item, stays within that box.
A table there scrolls sideways.

A widget whose entry declares `x-height`, such as `lf-chart`, reserves that height
before it draws; `data-height` on the element overrides it. A widget whose drawing sets
its own height, such as `lf-diagram` or an `lf-diff` bound with `source`, reserves
nothing, so content below it moves when it draws unless you set `data-height`. An
`lf-diff` with its patch inline sizes itself from the patch, so leave `data-height` off
it. `page check --render` suggests the height wherever a drawing differs from what was
reserved.

## The rail and the margin

With page tabs, each tab can start with its own `aside.sidebar` and empty `lf-toc`:
the tab's outline appears below its tab strip in flow and becomes its spine when the margin
has room. A sidebar directly in the column keeps that slot if one is present; nested
tabbed boxes keep their sidebars in flow. Write short notes in `aside.sidenote`. For
CSS that depends on what is in the
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

The page's CSS is ordinary CSS over the whole document: a rule for `button` styles the
buttons widgets build as well as the page's own. Give each rule a selector that names
what it means to style, such as a class on your own controls or a widget's id before
its controls (`#triage button`). Leaf's panel and thread cards keep their own look
against a page rule as light as one class (`button`, `.card`); a heavier selector such
as `button:hover`, an `!important` declaration or a rule in the page's own `@layer`
reaches them too, so name your own content in it. A token such as `--accent` on `:root` changes every surface that reads it. For
a page-specific inset, use the frame declaration in `package-themes.md`, "A theme
change".

To make a control you write match Leaf's, give it `class="button"`,
`class="button primary"` for the committing action, or `class="field"` for a text
input or select. A native radio or checkbox uses
`<label class="choice"><input type="radio" name="view" value="summary">Summary</label>`
(or `type="checkbox"`).

Leaf's panel, thread cards and markers draw over everything in `main`, whatever its
`z-index`. Open a modal or menu of the page's own in the top layer: a `<dialog>` shown
with `showModal()`, or an element with `popover`.

### Space for changing text

Keep the controls and content the reader is using in place and the same size while
text changes. Reserve space independently of the current words or value. When the
text states are known, ordinary CSS Grid can size their shared cell for all of them,
including their wrapped height at the current width:

```html
<style>
  .text-states {
    display: inline-grid;
    grid-template-columns: minmax(0, 1fr);
  }
  .text-states > * {
    grid-area: 1 / 1;
    visibility: hidden;
  }
  .text-states > .current {
    visibility: visible;
  }
</style>
<span class="text-states" role="status">
  <span class="current">Ready</span>
  <span>Saving changes…</span>
  <span>Saved. You can close this page.</span>
</span>
```

Move `current` between the existing children. `visibility: hidden` keeps inactive
text in layout but out of sight and accessibility; `display: none` or removing it
would lose that reservation. Use `display: grid` for a full-width message. For a
counter, an invisible representative widest value can share the cell with the
changing value; `font-variant-numeric: tabular-nums` equalizes digit widths but does
not reserve space for additional digits.

For concise, one-line text, Leaf's `data-room` shorthand holds representative widest
strings, separated by newlines; its only child holds the current text. Its CSS reserves
that space from first paint:

```html
<span role="status" data-room="Ready&#10;Saving changes…&#10;Saved"
  ><span>Ready</span></span
>
```

Change the child's text, keeping the wrapper. The wrapper fits its container; text
past that width is ellipsized, while its DOM text and accessible name stay whole.
Use this for short feedback, with longer results and error details in readable content
outside the controls' changing labels. Such content can grow; arrange it so the controls
the reader needs next remain reachable.

## Activity from several contributors

When several workers report to one orchestrator, write a page-owned adapter that declares their report verbs and
reads task and worker state from the public work projection. A page several people
revisit, such as a working board or long review, can show recent changes in an
`lf-activity` feed.
