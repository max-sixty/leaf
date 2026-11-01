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
that no Layout fits writes its own grid or flex rules. For a row of side-by-side blocks
inside a card or a playground's preview, follow `package-themes.md`, "A theme change",
so its items keep their top margins level.

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

## Document flow

A `layout-column` is a native grid with a centered prose track and the space on
both sides available to exhibits. Group a nested section with `class="layout-flow"`
when its children should share those tracks. Ordinary wrappers contain their
children: a list, callout or custom grid does not grant a nested exhibit room outside
its own box. The same `data-width` contract applies at every level.

Direct children of `layout-column` and `layout-flow` are grid items: their vertical
margins add rather than collapse, and `float` does not place them beside prose.
Automatic inline margins make an unsized item shrink to its content; give it
`inline-size: 100%` when it should fill its track, up to any `max-inline-size`.
An item that opens with a heading, or with an eyebrow over one, takes the heading's
gap as its own top margin, so its box starts at the heading. Set that gap with the
theme's `--h2-start` and `--h3-start` on `:root`. A top margin page CSS gives the item
replaces the gap, and one it gives the heading adds to it.

```html
<main class="layout-column">
  <h1>…</h1>
  <section id="evidence" class="layout-flow">
    <h2>…</h2>
    <p>…</p>
    <lf-diff id="changes">…</lf-diff>
  </section>
</main>
```

Give a tab set `class="layout-flow"` when it should share the document's tracks
without a frame. Each panel is either another `layout-flow` or its own Layout.
Omit the class for a framed tab set inside a section or another panel; its panels
stay ordinary boxes too. Placement alone never chooses a set's visual flow.

## A sidebar page

Use `<main class="layout-sidebar">` when the reader works through one region while
keeping another in view. The sidebar and body are authored siblings; the sidebar's
`layout-track` holds everything that should stick and scroll together.

```html
<main class="layout-sidebar">
  <aside id="status">
    <div class="layout-track">
      <lf-toc id="contents"></lf-toc>
      <p>…</p>
    </div>
  </aside>
  <article id="evidence" class="layout-column">
    <h1>…</h1>
    <p>…</p>
    <!-- document and supporting evidence -->
  </article>
</main>
```

Use a `layout-column` body for a reading document with wider exhibits. Its prose
starts beside the sidebar, and exhibits use the remaining body width. For a board or
dashboard, the body can instead be an ordinary `div` with the page's own layout; a
`header` and `footer` on the outer Layout span both regions.

The browser wraps the regions in source order when they no longer fit. Put the
`aside` before the body when its contents should be read first on a narrow screen,
and after it when they should follow the body. Set `--aside` on the Layout to a
length or share, such as `20rem` or `25%`, to choose its width; its contents fit that
width. The default dashboard shares are two thirds body and one third sidebar.
A document sidebar takes the shared sidebar measure, leaving prose its own measure.

Beside the body, `layout-track` sticks within its sidebar and scrolls within the
window when tall. Stacked, it flows whole with the page. The authored wrapper is the
same node from the first paint through revisions: Leaf inserts no body around it.
Style its blocks by their classes or ids, or as `.layout-track > p`.

Add `layout-notes` to the `layout-column` that should leave room beside its
prose for notes, such as `<main class="layout-column layout-notes">`. This is an
optional arrangement: an unmarked column stays centered, and its notes wrap
within the room it has. An independent nested column chooses its own arrangement.

Group a short note with the passage it accompanies in `layout-note`:

```html
<div class="layout-note">
  <p>…</p>
  <aside class="note" id="qualification">…</aside>
</div>
```

The note stands beside the passage when the row has room, then follows it when
narrow. The next exhibit follows the whole row, so it cannot cover the note.

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
where the reader looks for the queue's state, such as the header. The list marks each
tab's open obligations and the tally counts what is left, so write no script or count
of your own, and don't state the count in prose or chips. Each item's `summary` shows under its label, so the user can choose an item
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

A `table` with either value is only as wide as its columns need, up to that width.
A block takes a wider track when it is a child of `layout-column` or `layout-flow`.
A framed holder, such as an `lf-ask` or callout, needs its own `data-width` to widen;
its children use the room inside it. A wide child alone does not widen its holder,
and a table scrolls sideways when needed. Use `layout-flow` on unframed section
wrappers that should share the document's tracks, not on boxes that arrange their
own contents.

A widget whose entry declares `x-height`, such as `lf-chart`, reserves that height
before it draws; `data-height` on the element overrides it. A widget whose drawing sets
its own height, such as `lf-diagram`, reserves nothing, so content below it moves
when it draws unless you set `data-height`. `lf-diff` sizes textual patches from
inline content or available source data; its package author instructions own the
limits. `page check --render` suggests the height wherever a drawing differs from
what was reserved.

## The rail and the margin

A document's explicit sidebar keeps its route beside the body. A contents map there
uses the quiet spine on a wide fine-pointer screen; stacked, it returns to its native
outline. A dashboard sidebar keeps its outline open beside the body. These placements
are CSS layout, present before widgets load. Page CSS does not read runtime placement
attributes. To change where a route stands, compose its sidebar and body explicitly.

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
reaches them too, so name your own content in it. A token such as `--accent` on `:root` changes every surface that reads it, and a token
on one of the chrome's parts, such as `--paper` on `[part~="card"]`, changes only that
surface (`package-themes.md`, "Leaf's chrome"). For
a page-specific inset, use the frame declaration in `package-themes.md`, "A theme
change".

A native control you write keeps the browser's default face until it takes Leaf's:
`class="button"`, `class="button primary"` for the committing action, `class="field"`
for a text input or select, and
`<label class="choice"><input type="radio" name="view" value="summary">Summary</label>`
(or `type="checkbox"`) for a radio or checkbox. A control drawn for the task, such as
a stack of layer tiles or a curve's handles, is the page's own design
(`page-authoring.md`, "Style the page").

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
