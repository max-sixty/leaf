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

Content standing beside `main` in `body`, such as a site-wide header or footer, takes
no Layout: no gutter or column, and `data-width` does nothing there. A workspace's
`main` still fills the window, so anything beside it scrolls the page. A page of parts
holds its title and list fixed at the window's top, so it takes nothing beside `main`.
Keep the page's
title, and a Layout's `header` and `footer`, inside `main`, and lay out what stands
beside it with the page's own CSS, such as a grid on `body`.

A site header the page fixes or makes sticky at the window's top covers what scrolls
under it, and Leaf doesn't look for it. So give every element with an `id` a
`scroll-margin-top` a little taller than the header, such as
`[id] { scroll-margin-top: 4.5rem; }`, so a link or a walk lands its target below the
header. A `scroll-padding-top` on the page's root has no effect.

On a column page, a board, diagram or diff declares its own width, and any other block,
such as a table, a trace or a playground, can ask for one with `data-width` ("Bounds and
widths"). The block breaks out of the column and the prose stays where it is.

On a sidebar page, every block, the title included, starts at the same left edge and
fills its region. Text, a callout, and widgets read as text such as an option list keep
the reading measure, on a column page too.

A workspace fills the window. It has no reading measure, every block fills its region,
and `data-width` has no effect. Where a region would hold prose too wide to read,
narrow its grid track or cap its blocks in the page's `<style>`, such as
`#queue > lf-tab > * { max-inline-size: var(--lf-wide); }`.

The page's own `<style>` comes after the Layout, so ordinary rules can change a track
share, a gap or an order. Where a Layout fits, use it rather than rebuilding it; a page
that no Layout fits writes its own grid or flex rules. For a row of side-by-side blocks
inside a card or a playground's preview, follow `package-themes.md`, "A theme change",
so its items keep their top margins level.

## A page of parts

Write one set of parts, such as `lf-parts`, in a `main` that carries no Layout, and give
each part one child carrying that part's Layout:

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

The page's `header` is the only element in `main` besides the parts. It appears at the
top of a column along the window's left edge, followed by the list of parts, with each part's `summary`
under its label and the state of the obligations it holds under that, as a queue's list
marks them. Each part takes the rest of the width from the top of the window, so
a workspace part fills the window. Keep the header to the page's title, since it shares
the column's width. Give each part its own heading, and a column part its own contents
outline.

Where text can't say what a list entry should show, such as a file's name in code type
over a coloured diffstat, open the part, or a tab in any list, with a `<template>`
holding that markup. The list shows it in place of the label and summary, which stay
the name and description everything else reads. Keep links and controls out of it,
since the entry is itself a control.

## Document flow

A `layout-column` is ordinary block flow at the reading measure, centered, with the
space on both sides available to exhibits. Its blocks' margins collapse and a float
stands beside the prose, as on any page. A `section`, `article` or `details` shares
that space with what it holds, at any depth, so an exhibit in it breaks out as one
standing in the column does, unless it carries a Layout, such as `layout-tiles`, which
arranges what it holds. Other wrappers contain their children: a `div`, list,
callout or custom grid does not grant a nested exhibit room outside its own box. The
same `data-width` contract applies at every level.

```html
<main class="layout-column">
  <h1>…</h1>
  <section id="evidence">
    <h2>…</h2>
    <p>…</p>
    <lf-diff id="changes">…</lf-diff>
  </section>
</main>
```

A section that draws a frame of its own, such as a border or a tint, still shares the
space: its frame widens with a wide block in it, which runs over the frame's border
and padding. To keep the block inside the frame, draw the frame on a `div`; to widen
the frame and keep its padding, put `data-width` on the frame.

Give a tab set `flow="page"` when it should share the document's space without a
frame; its panels share it too. Omit it for a framed tab set inside a section or
another panel, whose panels use the room inside the frame. Placement alone never
chooses a set's visual flow.

To hang a short note in the margin beside the passage it qualifies, float it there
with the page's own CSS, as Tufte CSS sets sidenotes, and write it just before that
passage so their tops line up. Below the window width at which the margin holds it,
the column's width plus twice the note's room, it stands in the column instead:

```css
.sidenote {
  float: inline-end;
  clear: inline-end;
  inline-size: 12rem;
  margin-inline-end: -14rem;
}
@media (width < 75rem) {
  .sidenote {
    float: none;
    inline-size: auto;
    margin-inline-end: 0;
  }
}
```

Leaf's comment markers stand in the same margin and don't avoid a note. Where notes
fill it, give the margin to them with `data-rail="none"` on `body`, so each marker
stands on its passage instead.

## A sidebar page

Use `<main class="layout-sidebar">` when the reader works through one region while
keeping another in view. The sidebar and body are authored siblings; the sidebar's
`layout-track` holds everything that should stick and scroll together.

```html
<main class="layout-sidebar">
  <aside id="route">
    <div class="layout-track"><lf-toc id="contents"></lf-toc></div>
  </aside>
  <article id="evidence" class="layout-column">
    <h1>…</h1>
    <p>…</p>
    <!-- document and supporting evidence -->
  </article>
</main>
```

Use a `layout-column` body for a reading document with wider exhibits. Its prose
stands where a column page's would, moving toward the end only as far as the sidebar
needs, and exhibits use the body's width on either side of it. Where its
sidebar comes before the body and its track holds only the contents map, under a mouse
the sidebar narrows to the map's spine, which draws the document's sections to scale,
and the map shows its labels over the page when the reader points at it. Under touch,
after the body, or with anything else in the track, the sidebar keeps a column's room
and the map stands open as an outline. So put a status the reader should see at once at
the top of the body rather than beside the map. A sidebar that has wrapped above or
below the body shows the map as a disclosure. For a board or dashboard, the body can
instead be an ordinary `div` with the page's own layout, beside which a sidebar keeps
its outline open; a `header` and `footer` on the outer Layout span both regions.

The browser wraps the regions in source order when they no longer fit. Put the
`aside` before the body when its contents should be read first on a narrow screen,
and after it when they should follow the body. Set `--lf-aside` on the Layout to a
length or share, such as `20rem` or `25%`, to choose its width; its contents fit that
width. The default dashboard shares are two thirds body and one third sidebar.

Beside the body, `layout-track` sticks within its sidebar and scrolls within the
window when tall. Stacked, it flows whole with the page. The authored wrapper is the
same node from the first paint through revisions: Leaf inserts no body around it.
Style its blocks by their classes or ids, or as `.layout-track > p`.

## A workspace

`<main class="layout-workspace">` fills the window behind Leaf's floating panel, and the reader
works in its regions rather than scrolling the page. The panel stands over the regions'
feet and the user folds it where it covers them. The `header` and `footer` take
their content's height and the body takes the rest. Keep shared context concise enough
to leave the working regions usable; place region-specific explanation with its subject.

The body is one pane, such as `lf-pane`, a widget that lays out its own regions, or
the page's own grid of panes:

```html
<main class="layout-workspace density-working">
  <header>
    <h1>…</h1>
    <p><span class="lf-tag warn">…</span></p>
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

Give material beside the regions' work, such as a list of open items or a report, a view
of its own, so the regions keep the room the reader works in. Make the body a tab set
with `flow="page"`, put the regions in its first tab, so the page still opens on them,
and add a tab for the material. A grid of panes that is a tab's one block fills the
window below the tab strip, as it does as the body. Written as a second block beside the
body, the material would split the window's height with it, and written as another
region, it would take room from the others.

A widget that asks, such as a playground, stands in its question's group
(`authoring-on-me.md`, "On the page"), and that group is the body. Where the header's
heading asks the question, the group's label asks it too:

```html
<main class="layout-workspace density-working">
  <header>
    <h1>Which latency window should checkout alert on?</h1>
    <p>…</p>
  </header>
  <lf-group id="tune" label="Which latency window should checkout alert on?">
    <lf-playground id="tune-config">…</lf-playground>
  </lf-group>
</main>
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
a list of the items beside the one it opens, such as one `lf-tabs list="side"` with an
`lf-tab` per item, and put a tally of what is left, such as an `lf-tally` with `next`,
where the reader looks for the queue's state, such as the header. The list marks each
tab's open obligations and the tally counts what is left, so write no script or count
of your own, and don't state the count in prose or chips. Each item's `summary` shows under its label, so the user can choose an item
without opening it. Start the summary with what the item is about, such as the problem
a ticket reports, unless the label already says so, then what sets it apart from its
neighbours, such as its age or suggested outcome. Leave out the item's group, which its
heading shows. Where items fall into kinds the user works through in turn, such as
merge, close and FYI, give each item its kind as `group` and place each kind's items
together in the order to take them; adjacent tabs with the same group share one
heading. Where the user would rather take the items one at a time than see the list,
make the body a pile of cards that shows one at a time and counts what is left, such
as a deck.

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
itself, such as a `table` or `lf-code`, and write no CSS that copies its widths or
sets its inline margins. An `available` block reaches past the prose by its own start
margin, so space it with `margin-block` rather than `margin`. `data-width` works on
column and sidebar pages:

- `data-width="wide"` is for a block slightly wider than the column, such as code up
  to 100 columns, a diff, a table of a few more columns or a row of three option
  cards. The block starts at the prose's start edge, the left in a left-to-right page,
  and extends toward its end edge to `--lf-wide`, as far as the window allows.
- `data-width="available"` is for a surface that uses every pixel, such as a board, a
  large drawing or a playground. It takes all the width Leaf's chrome and the margin
  leave free, into both margins. A `figure` with it keeps its `figcaption` under the
  prose by the caption's inline margins, so space the caption with `margin-block`.

A `table` with either value is only as wide as its columns need, up to that width.
A block widens when it is a child of the `layout-column`, or of a `section`,
`article` or `details` in its flow, whose blocks stand in the flow around it,
so its words stay on the column beside a wider one. A framed holder, such as a
callout, needs its own `data-width` to widen; its children use the room inside it. A
wide child alone does not widen its holder. Write a box that arranges its own
contents, such as a grid of cards, as a `div`, which keeps them inside it.
`page-authoring.md`, "Markup", says how a table that outgrows its box scrolls sideways,
with the reading face and without it.

A widget whose entry declares `height`, such as `lf-chart`, reserves that height
before it draws; `data-height` on the element overrides it. A widget whose drawing sets
its own height, such as `lf-diagram`, reserves nothing, so content below it moves
when it draws unless you set `data-height`. A diagram lays itself out for its width,
so the height to state is the one `page check --render` reports at the user's window;
a phone may draw it taller. `lf-diff` shows an inline patch as its
source text until it draws, so its height changes as it draws; its package author
instructions say when to set `data-height`. Wherever a drawing's height differs from
the box it showed before drawing, `page check --render` gives that height as advice,
whether `data-height` was missing, too small or too large.

## The rail and the margin

A document's explicit sidebar keeps its route beside the body, narrowed to the contents
map's spine or at a column's width as "A sidebar page" says. Both are CSS layout,
present before widgets load. Page CSS does not read runtime placement
attributes. To change where a route stands, compose its sidebar and body explicitly.

`data-rail="right"` on `body` gives a sidebar page a rail, and `data-rail="none"` gives
a column page's right margin to the page's own content. A workspace has no rail; a
comment there shows as a pin on its block.

## Page-owned annotations

By default Leaf draws comment markers and threads over the page.
`data-annotations="page"` on `body` turns these off for a page that shows comments in
its own layout; comments, On Me obligations, Undo and live revisions still work, and comments open
in the Leaf panel. Leaf still marks commented words on such a page: pointing at them
previews their thread, and a press opens it. To show conversations in the page's own layout, register a
presentation as `module-annotations.md`, "Page annotation presentation", describes,
rather than rebuilding the event log in page code.

## Page CSS and Leaf's controls

The page's CSS is ordinary CSS over the whole document. Its unlayered rules outrank
Leaf's, so a rule for `button` styles the buttons widgets build as well as the page's
own. Give each rule a selector that names what it means to style, such as a class on
your own controls or a widget's id before its controls (`#triage button`). Leaf's panel
and thread cards keep their own look against a page rule as light as one class
(`button`, `.card`); a heavier selector such as `button:hover` or an `!important`
declaration reaches them too, so name your own content in it.

Two layer names rank among Leaf's own. A rule in `@layer reset` ranks below every rule
of Leaf's and of the page's theme, so it applies wherever neither says anything. A rule
in `@layer base`, where Tailwind keeps its reset and the element rules its author
writes, outranks the page's theme and ranks below Leaf's rules for what Leaf draws: its
widgets, idioms, controls, panel, thread cards and messages. So a framework such as
Tailwind needs no change to leave them their faces. Every other layer the page names
outranks Leaf's rules, as unlayered CSS does, so a utility class on a widget, such as
Tailwind's `mt-0`, restyles it. To restyle what Leaf draws, write the rule in such a
layer or unlayered, not in `base`.

A reset in `base` also outranks the theme's look, on the page's own markup and on the
code a widget such as `lf-code` shows in that look: lists lose their bullets and code
blocks their frames. A page that wants the theme's look imports the reset into `reset`
instead, as Tailwind 4 allows:

```css
@import "tailwindcss/theme.css" layer(theme);
@import "tailwindcss/preflight.css" layer(reset);
@import "tailwindcss/utilities.css" layer(utilities);
```

A page whose framework has design tokens hands Leaf three of them, so
what Leaf draws takes the framework's colours:

```css
:root {
  --lf-paper: var(--background);
  --lf-ink: var(--foreground);
  --lf-accent: var(--primary);
}
```

Every custom property of Leaf's starts with `--lf-`, so a framework's own `--accent`
or `--muted` changes nothing Leaf draws.

A token such as `--lf-accent` on `:root` changes every surface that reads it, and a token
on one of the chrome's parts, such as `--lf-paper` on `[part~="card"]`, changes only that
surface (`package-themes.md`, "Leaf's chrome"). For
a page-specific inset, use the frame declaration in `package-themes.md`, "A theme
change".

On a page that takes a theme, the buttons, fields and choices you write in plain HTML
wear the faces of Leaf's own controls; the vocabulary's `button` and `input, select`
entries say how to write each. Any rule of yours outranks that face, so a
control drawn for the task, such as a stack of layer tiles or a curve's handles, takes
the page's own design. `page-authoring.md`, "Style the page", says how to leave the
controls in one box with the browser's look.

Leaf's panel, thread cards and markers draw over everything in `body`, whatever its
`z-index`. Open a modal or menu of the page's own in the top layer: a `<dialog>` shown
with `showModal()`, or an element with `popover`. To show the page full screen, call
`requestFullscreen()` on `document.documentElement`; a full-screen `body` leaves Leaf's
panel and threads out.

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

## Activity from several contributors

When several workers report to one orchestrator, write a page-owned adapter that declares their report verbs and
reads task and worker state from the public work projection. A page several people
revisit, such as a working board or long review, can show recent changes in an
`lf-activity` feed.
