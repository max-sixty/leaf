# Page authoring

- [Read the registry](#read-the-registry)
- [Document scaffold](#document-scaffold)
- [Composing a page](#composing-a-page)
- [Draw the subject](#draw-the-subject)
- [Theme and vocabulary](#theme-and-vocabulary)
- [Page behavior](#page-behavior)
- [Live samples](#live-samples)
- [Stable anchors](#stable-anchors)
- [Reading cost](#reading-cost)
- [Pre-handover review](#pre-handover-review)

## Read the registry

Run `leaf page instructions <page>` and read the shared `author` instructions
when listed before choosing widgets. Shared composition rules guide that choice.

`<page>/registry.json` is the vocabulary `page init` vendored; a
`page/registry.json` the page writes adds to it or replaces its entries ("Page
behavior"). Discover widgets by their short purpose and use case:

```bash
registry="<page>/registry.json"
jq 'with_entries(select(.key | startswith("lf-")))
    | map_values(.description)' "$registry"
```

Once you select a widget, read its attribute schema and worked example. Ask for
a group's parent and child together, because the parent's example shows both:

```bash
registry="<page>/registry.json"
jq '{"lf-options": .["lf-options"], "lf-option": .["lf-option"]}
    | map_values({"x-example", properties, required})' "$registry"
```

Before writing the markup, list the selected widgets' instruction audiences and
read `author` when listed, including when you copy their examples:

```bash
leaf page instructions <page> --widget lf-options
leaf page instructions <page> author --widget lf-options
```

The command includes shared package instructions and the instructions for the
selected widgets, their required members, custom tags in their examples, and
declared data contracts. Select each additional widget the page uses with another
`--widget`. A widget's `x-instructions` guides how to use it after selection.

Read the complete entry wherever the page does more than the example shows, and
for every `$` fact:

```bash
registry="<page>/registry.json"
jq '{"lf-chart": .["lf-chart"], "$series": .["$series"]}' "$registry"
```

`description` identifies a widget's purpose and when it helps. The schema and
`x-example` state its form; `x-instructions` carries authoring choices and
obligations the schema cannot express. Implementation contracts live beside
their owning modules. Package-defined tags and `$` facts join the same registry.
`leaf page instructions <page>` lists available audiences; read the assigned
audience before acting in another role, selecting the widgets or data contracts
that work uses. "Package contract" in `packages.md` defines the command.

## Document scaffold

Write a complete HTML document. The authored head names and describes the page;
Leaf adds the encoding, identity, theme, runtime, and canonical address when it
delivers the document. Omit `<meta charset>`: delivery declares UTF-8 before
authored head content. Put page-specific CSS in `<style>` and JavaScript in
`<script>` ("Page behavior"). Every `lf-*` element has an explicit end tag.

Delivery also supplies `width=device-width, initial-scale=1, viewport-fit=cover`
when the head has no viewport meta. This lets Leaf's chrome use the device's
safe-area insets. An authored viewport is preserved and replaces that policy.

The title and description are what the page says it is anywhere outside itself: a
tab, a search result, a link someone pastes into a chat. Write a description that
stands alone, since whoever reads it there has none of the page around it.

```html
<!doctype html>
<html lang="en">
<head>
  <title>…</title>
  <meta name="description" content="…">
</head>
<body>
  <main class="layout-column">…</main>
</body>
</html>
```

## Composing a page

A page is a stack of blocks, and most pages are a reading column,
`<main class="layout-column">`: text keeps the column's measure, and a block that needs
more room grows out of the column into the room beside it without moving the prose. A
`main` with no Layout class has no arrangement at all, and its blocks run the window's
width. A diagram, a board or a
wide table states that width in its registry entry, and `data-width` asks the same of
any other block ("Bounds and widths", below). Most pages need nothing more. Compose
the stack from these:

- **Prose read in order** — a plan, a review, a write-up, a decision — is plain
  semantic HTML, with nothing declared.
- **Independent status tiles** are a block with `class="layout-tiles"`, which sets its
  children in equal cells, as many to a row as fit. Each cell holds a surface — a
  metric, chart, table, list or log, with at most a caption — rather than paragraphs;
  a row of headline numbers is `lf-metric` tiles in one. Tiles of paragraphs are prose
  cut into columns, and read worse than the column.
- **A comparison** is `lf-compare`, which keeps its variants paired at any width.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview.
- **A screen the reader moves through rather than scrolls**, like a mail client or a
  dashboard, such as a queue worked one item at a time or a run's log beside the chart
  it explains, is a workspace (below). A document read top to bottom beside a panel
  kept in view, such as a postmortem beside its timeline, is instead a `layout-sidebar`
  page whose `aside` sticks ("A wide page", below).
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, Ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. Page tabs are sections of one page: each panel takes the page's
  width, so a Layout class on `main` widens every tab, and a sidebar stands beside
  them as on any page. The `lf-tabs` entry says which placement makes which, and how
  to order and retire views.

A page grows without changing its Layout: a report that gains live status gains a row of
tiles, and its comments and anchors stay put.

Use `lf-roster` when one orchestrator publishes the page and multiple workers
report to it. On a one-agent page, the banner carries that activity. A revisited
page with several contributors, such as a working board, command hub, or long
review, can use `lf-activity` to show recent changes; a read-once page needs no
activity feed.

The banner and the bottom bar at the foot of the window are fixed reservations, so
the room a page has depends only on the window, and nothing Leaf draws moves the page's
content: the rail stands in room the page leaves beside its column ("The rail and the
margin", below).

### Contents navigation

Long scrolling documents include a contents outline. It gives the reader a
persistent route between sections and shows where they are in the document. A short
document that can be read at a glance needs no outline. Put an empty `lf-toc` with a
stable id in an `aside.sidebar`, directly inside `main` near the opening:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

On a column page with room in the desktop margin, Leaf presents it as the contents
spine; in a narrow window it is an open outline in the page's flow ("The rail and the
margin"). Workspaces and root page tabs use their own navigation.

### Layouts

A Layout is a class that arranges the box it is on. Three set the page's shape, on
`main`:

| Class | The page |
| --- | --- |
| `layout-column` | the reading column, and a block's breakout beside it |
| `layout-wide` | as wide as the window, up to a cap, holding one flow |
| `layout-workspace` | a screen filling the window: `header`, one body, `footer` |

Two arrange a box's children, on `main` or on any block:

| Class | Arranges |
| --- | --- |
| `layout-sidebar` | a body beside its `aside`, with a `header` and `footer` across both |
| `layout-tiles` | equal cells, as many to a row as fit |

On `main`, every class but `layout-column` makes a wide page: every block, the title
included, starts at one left edge and takes the page's width, and text keeps the
reading measure. A wide, sidebar or tiles page is capped at the widest page and
sets its title larger; a workspace takes the whole window and leaves its title to the
theme. `layout-column` on a block keeps the measure but gives it no
room to break out into, since that room is the page's.

A Layout is a starting point. The page's own `<style>` comes after it in the cascade, so
an ordinary rule adjusts it — a different track share, a gap, an order — and a page
whose arrangement no Layout fits writes its own grid or flex rules on its own boxes.
Where a Layout fits, use it rather than rebuilding it, since its tracks already hold
the widths and wrapping every page needs.

### A wide page

When the regions are the page rather than exhibits in an argument — a board with its
status, a release dashboard, a queue sorted into buckets, a long review whose contents
and verdict stay beside the code — widen the page itself. `<main class="layout-wide">`
holds one flow at the page's width. `<main class="layout-sidebar">` sets what the reader
works through beside what they keep an eye on — status, counts, the verdict's
follow-ups, the contents — which is the Layout's `aside`, with the page's `header` above
both:

```html
<main class="layout-sidebar">
  <header><h1>…</h1><p class="lede">…</p></header>
  <div id="body">…</div>        <!-- what the reader works through -->
  <aside id="status">…</aside>  <!-- what they keep an eye on -->
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

A track shorter than the window can stay in view while the body scrolls beside it:
give the `aside` `align-self: stretch`, so it runs the body's height, and the block it
holds `position: sticky; top: var(--lf-top)`, which keeps that block just below Leaf's
banner and any page tab strip. The block sticks only inside the track, so wherever the two stack, for either
reason, the track is only as tall as what it holds and nothing sticks over the body; no
width is needed. Leave a taller track in flow, since sticking it would hide its end
until the page ends.

Draw each region the same way, as a `section.panel` with a short heading, and keep a
`.callout` with a status tone (`warn`, `danger`, `ok`) for the one thing the reader must
act on; a row of `.tag` chips in the same tones under the lede says the page's state at a
glance.

### A workspace

`<main class="layout-workspace">` is a screen: it fills the window's height below the
banner, and the reader moves through it, choosing what its regions show, rather than
scrolling it. Its `header` and `footer` take what they hold, and its one body between
them takes the rest. The header is one row, the title with the page's state beside it
as `.tag` chips, so the regions keep the window: write no lede, eyebrow or legend there,
and put what a lede would say at the top of the region it is about, or in a footer of a
line or two. The body is one `lf-pane`, a
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
wider window still share its one height, and `page check --render` refuses them.

`density-working` is a style, not a Layout: on any block it sets smaller type, tighter
spacing and options as rows, for a surface the reader operates rather than reads down.
A workspace usually takes it, and so can a dense pane or table on a column page.

A queue whose items open one at a time beside it, such as tickets, cases or findings to
decide, is one `lf-tabs list="side"` as the body: its list is the queue and each item an
`lf-tab`, so one opens beside the list and a link or an Ask opens its own. Write no
script to select or hide an item; the tab set does both.

The page itself does not scroll; a region does, where what it holds runs past it. Each
pane's body scrolls on its own, and a widget that fills the body, such as a playground's
stage, grows to the window's height. The `lf-pane` entry says what a pane holds. Let the
Layout allocate the height: page-specific positioning should not be needed to keep a
pane or footer reachable. Where the window is too small to hold the regions, they take
their natural height and the page scrolls.

Make a region show what it holds, so scrolling one stays the exception: a region a
reader has to scroll through to reach its decision is read in two halves. `page check
--render` names each pane or body that runs past its region at a desktop size; trim it
to what the region shows, or split it. A pane that is a reader for something long, such
as a source file or a log, is the exception the region scrolls for, and the advice on it
can stand.

### Bounds and widths

A log, feed, or long listing bounds its own height with `data-bound`, naming the end
its newest entry is at. Put the entries in the order the reader needs, then bound
that order. A list that grows downward takes `data-bound="end"`, which opens it on
its last line, keeps that line in view while the user is at the end, and leaves them
where they scrolled back to otherwise. A newest-first list takes
`data-bound="start"`, which opens it at the top, as the page's own activity feed
does. Some widgets bound themselves by default. Don't make a box scroll vertically with page
CSS: Leaf keeps no reading position in a scroller it did not make, and `page
check` advises against one.

An individual block or section may request a responsive allocation with
`data-width="column"`, `data-width="wide"`, or `data-width="available"`. `column`
uses the standard prose measure, including inside a wider section. `wide` uses the
shared evidence width, `--wide`, in every Layout: past a column it grows to that
width, and in a wider track or pane it holds to it at the track's start. A narrower
frame still bounds it. `available` uses all room left by the page shell, frames,
chrome, and a margin resident that takes its side, such as a sidebar standing in the
margin or the contents map's spine; the markers beside it then stand as pins on it, and
it moves below a note hanging level with it. The occurrence overrides a
widget's package default, so `data-width="column"` can deliberately keep a normally wide
widget with the prose.
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

### The rail and the margin

Leaf marks each commented or decided element with a marker: a thread, an Ask, a
suggestion's ✓/✗. Nothing Leaf draws moves the page's content, so plan the page's
geometry without them:

- A column page keeps a rail, a strip `--rail` wide beside its column, wherever the
  room beside the column holds it: from a window of about 960px with a mouse and about
  1010px with a finger. Its markers stand in it, 22px past the column. A marker level
  with a note hanging in the margin stands as a pin instead.
- A column page's first `aside.sidebar` and its `aside.sidenote`s join the rail in the
  margin where the window holds all of them beside the column: a sidebar from about
  1130px, a note from about 1150px, both from about 1420px, the column moving off
  centre to make the room. With a mouse, a sidebar holding the contents map needs only
  the map's spine. Below that each stays where it was written. Leaf writes what stands
  in the margin on `main` as `data-lf-margin` (`rail`, `map`, `sidebar`, `note`), so page
  CSS that should follow the margin keys on it, such as
  `main:not([data-lf-margin~="sidebar"]) #route { display: none }`.
- A wide page fills the window up to its cap, so the rail stands beside it only in a
  window of about 1920px or wider. Elsewhere its markers stand as pins over the page by
  their targets, as every marker does where the rail does not stand: in a narrower
  window, and in a pane that scrolls on its own. A
  block's pin stands inside its top-right corner and a run of text's just after its
  last word, unless that covers words, a control, or another block; then it takes the
  nearest room beside its target that covers none, such as the free end of a line or
  the gap below it. Where its target leaves no such room, it may take the empty end of
  a neighbouring block's line, such as beside a short heading above it, unless that
  block paints its box (a fill, border or shadow, as a card or table does). Where none
  of that room lies within reach, it reaches one line further out, past a line of words
  but never past a painted block or nearer another pin's target, such as to the end of
  the section's heading above a full first line. A pin is 26px with a mouse and 44px
  under a finger. A pair, such as a suggestion's Accept and Reject, that finds no such
  room folds to one control, a marker wearing the face of what it folds (a suggestion's
  is a change), that opens to both on a tap or when the keyboard arrives on it or on
  its target, and takes room of that size; where even that finds none, as in a
  phone's full lines deep in a paragraph, the pin stays in the corner over the block's
  words.
- A marker on a figure grown past the rail stands on the figure as a pin, at the
  corner of the part it names when it names one.
- The user hides every pin and passage mark with `o`, or with Hide annotations in the
  banner's More under a finger, to see what lies under them; the rail stays, since it
  covers nothing. So leave no room for a pin in the page's CSS, such as padding at the
  end of a heading: wherever the rail stands, the room is left empty.

`data-rail="right"` on `body` keeps the rail on a wide page, and `data-rail="none"`
gives a column page's right margin to something of the page's own. A marker level
with a hanging `aside.sidenote` stands as a pin on its block, so a page with notes needs
neither.

### Page-owned annotations

Leaf's default draws markers, passage marks and contextual replies over the page.
For an arrangement that places annotations in the document instead, select
`data-annotations="page"` on `body`. This choice omits the overlay's modules,
styles and geometry. Exact comments, Asks, decisions, Undo, live revisions and
drawing capture still use the shared Leaf mechanisms. Changing the selection
replaces the document through the ordinary revision lifetime.

Place one empty `<lf-annotation-rail id="annotations"></lf-annotation-rail>`
where the reader should find conversations and actions. Allocate its width and
height in the page's CSS; it scrolls inside that box. At narrow widths, give it a
place the user can reach by touch and keyboard. Leaf supplies native disclosures,
reply editors, action controls and retained reading; the page supplies their layout.
Widget-local conversations keep their exact seats before the page rail takes
remaining targets. The Threads panel remains the complete conversation index.

Omitting the rail is valid. Comments open in Threads, and selection offers the
banner's Comment on selection control. A custom package can supply the same
page presentation through "Page annotation presentation" in `packages.md`;
do not reconstruct the event log or annotation inventory in page code.

## Draw the subject

Decide what each view draws before writing its words. Most of what a page explains
has a shape, and the user takes in a picture of it at a glance, where a description
has to be rebuilt in their head:

- where things sit, and what bounds, covers, or moves what: a layout, a page's
  regions, the same page at two widths;
- what contains, calls, or feeds what: a structure, an architecture, a data flow;
- how a state changes: a sequence, a lifecycle, a plan's phases;
- how two states differ: today beside proposed, before beside after;
- how alternatives differ, when they differ in arrangement or mechanism.

A page deciding, planning, or reviewing one of these draws it too. A table or list whose
rows name places, sizes, or connections is a drawing written out.

Show a visible subject with an image instead of describing its appearance: an
interface with a screenshot, and a visual change with an `lf-shot` before-and-after
capture. A proposal or a mechanism has nothing to capture yet, so draw it. A process
that unfolds over time is a diagram that moves: draw it in a page module from its
state and the moment, with controls to pause and scrub, so every moment stays
readable and its parts stay commentable. For fixed recordings and screen captures,
follow `authoring-evidence.md`, "Source files and media". When the shape of numbers is
the point — a trend, ranking, groups on one scale, or series moving together —
lead with an `lf-chart`, even if the numbers compare the same dimensions across
items. Put a table below it in `<details>` when readers also need exact values.
Use a table for value lookup, mixed units that cannot share an axis, or comparisons
with text-heavy cells; use `lf-compare` for a few alternatives read as wholes,
and `lf-options` when the user must choose among them. A headline measurement is
a metric. Movable things form a board. Use images only when they carry information.
`authoring-evidence.md` says which element draws each kind, and how to draw a figure
of your own.

For `lf-diagram`, omit `parts` when the whole drawing is one Comment target. When
individual boxes need their own targets, list every nameable box in `parts`;
`page check --render` reports a partial list so adjacent boxes do not behave differently.

The prose beside a shape says only what the shape cannot. What is left for prose is
the claim, the reason it holds, and the question the page is asking. A few sentences
hold all three. A section that runs longer is carrying either a structure with a
shape of its own or backing that belongs under `<details>`.

## Theme and vocabulary

Write semantic HTML and use the class idioms the registry lists under `$idioms`,
where each one comes with the markup it is written as. The vendored theme owns
palette, type, spacing, headings, tables, code, and widget presentation. Use a
page-local `<style>` only for presentation unique to this page.
For a page-specific inset, use the frame declaration in `references/packages.md`,
"A theme change".

The page's own CSS reaches the page's content and leaves Leaf's apparatus alone: the
banner, the thread panel, and the controls a widget builds. A rule for `button` or
`input` dresses the page's own buttons and fields, and a face set on `body` stops at
those controls. To change them on purpose, name the widget they stand in or Leaf's
class for them: `lf-options button`, `lf-board .lf-btn`, or, for controls a page
module builds with `offer`, the page's own element (`my-explorer .toolbar`). A token
such as `--accent` on `:root` changes every surface that reads it.

Widget attributes carry scalars; children carry prose; a titled compound member uses a
leading `<strong>`. A data-bodied widget such as `lf-code` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text.

Display source snippets as `<pre><code class="language-javascript">…</code></pre>`,
or `lf-code language="javascript"` for a line-numbered walkthrough, naming the actual
language from `$languages.names`. Format illustrative code with the language's usual
indentation and line breaks, preserving its behavior when you reformat an example.
Keep brevity in the surrounding prose rather than packing distinct statements or
fields onto a line. The runtime colors the declared language and preserves authored
whitespace. Verbatim source quotations keep their exact text; logs and transcripts
stay literal and uncolored when they are not source code.

The runtime injects the status banner, thread panel, Versions menu, keyboard
shortcuts, live-leaves drawer, and active-asks drawer, which lists the page's open Asks.
Do not duplicate that chrome or keep a second list of the Asks in the page.

Keep content within its allocated column, visual surface, or pane. The theme scrolls a `<pre>` or a table
that runs wider than its container and fits an image or SVG to it, so none of them needs a
width. A table that scrolls has every column at its longest unbreakable run, and
the browser gate refuses one that scrolls with a cell in it wrapped: put an
identifier in `<code>`, where it breaks inside its cell, rather than bare, where
it holds its column and squeezes the prose beside it, and keep the columns to
what the measure holds. Widgets whose element declaration requests wider space size
themselves within the page's available room. Preserve the meaningful detail in a diagram
or comparison rather than shrinking its source solely to fit the prose column.

## Page behavior

Write page-specific behavior in an inline `<script type="module">` or in browser-ready
modules below `page/`, referenced through `/page/…`. A library that ships only a classic
script loads with `<script defer src>`, from `page/` or any server; every script runs after
Leaf has read the page, so an inline classic, parser-blocking, or `async` script is
refused. Page stylesheets and their local dependencies may live below `page/` too.
Relative imports stay within `page/`; a module that integrates with Leaf may import the
public `/runtime/widget-api.js`. Leaf captures
the complete local dependency graph, effective registry, and selected layer bytes in the
same immutable revision as the markup they control.

Content and style changes update the open document when its registry and JavaScript
are unchanged. Unchanged widgets keep their elements and local interaction state;
changed widgets are replaced. An edit inside an element whose children a page module
moved or detached also replaces that element. Give elements stable ids when their
identity must survive a rewrite ("Stable anchors").

Changing the registry or JavaScript opens a fresh document. Leaf restores reading
position, recoverable drafts, and comparison state. It can also restore focus and
supported control state when an element keeps its authored id and tag. Element
instances and arbitrary module state do not survive the reload. Both update paths
wait while the user is composing, dragging, or undoing, has a gesture the server
has not yet admitted, or has the version menu open.

Page modules follow `references/packages.md`, "What a behavior module owes". In
particular, its `once()`, `quoted()`, `offer()`, `layoutChanged()`, and durable-state
rules keep authored controls correct after reconnection and thread quoting.

`leaf page check` runs a page's own code, a script or a page widget the
document places, once in the host's browser, and a page with a data widget such as a
chart or a diagram, whose body only its module can read: through upgrade,
presentation, and one frame after it. It fails on every error the page would report to
you through the watcher, an uncaught exception or a rejected promise with the source
location it came from, or a widget that could not draw its body, so a module that
throws on its first paint or a chart that does not parse is found before the URL goes
out. Code that runs only after a gesture or a timer is
not reached; operate it in the pre-handover review. A page with neither is checked
without a browser. On a host with no browser the run is skipped with a note; the page
still reports those errors to you once a browser draws it.

`page/registry.json` may contribute declarations using the package registry language.
Its element entry replaces the selected layer's complete entry; shared `$` declarations
compose at their declared grain. Declaration and implementation ownership are separate:
a page declaration keeps the package widget unless `page/widgets/<tag>.js` exists, and a
page widget may replace the package implementation without restating its declaration.
Both choices are fixed in the revision manifest.

Use a package when behavior, styling, or vocabulary is reused across pages. A one-page
explorer or playground keeps its code in `page/`. Leaf captures the local files a
page's scripts and stylesheets name literally, so import a page file by a literal URL;
a computed `import()` reaches a module on another server, named by its full URL. Leaf
refuses unresolved imports, filesystem escapes, and anything declared about the whole
document (a `<base>`, an http-equiv `<meta>`, an import map), which would send the
runtime's requests elsewhere or leave its modules unresolved.

A script, stylesheet, font, image, or frame may also come from another server, named
by its absolute `http(s)://` URL, and a page's code may fetch from anywhere. The page
loads it as written, so it arrives only while the user is online. Data the page
presents belongs in a `data/` source instead (`references/packages.md`, "External or
derived data"), where the log and an export hold it.

Typed data and media remain inert inputs. Read them through their Leaf/browser APIs;
do not turn their contents into source code or markup.

## Live samples

Use `lf-sample` with one direct `template[data-sample]` to let the user
operate a complete Leaf page inside the surrounding document. Give both the
element and template stable ids. Put the child's content and styles directly in
the template; Leaf supplies the document and its `main`:

```html
<lf-sample id="practice" label="practice release note">
  <template id="practice-page" data-sample>
    <h1>Weekend service</h1>
    <p id="service-note">The sample shuttle runs every hour.</p>
  </template>
</lf-sample>
```

The sample's gutter contains only the content being demonstrated. Keep labels,
host controls, and instructions about using the sample outside that gutter;
instructions that belong to the demonstrated page remain inside it.

The child uses the parent's selected layer and starts with its own event log. It
stands in the surrounding page as a block as tall as its content, with only the
Threads row of its chrome. When the window itself is what the sample shows, such as
Leaf's banner, bottom bar, or drawers, the boolean `window` attribute makes the child
a whole Leaf window instead, chrome included, at a fixed height that scrolls inside.
A click or Tab reaches the child directly; its normal widget controls, keyboard
routes, comments, and replies work there. Escape closes the child's open controls
before returning to the surrounding page. Reset creates a fresh page from the template.
Child decisions and comments do not change the parent's log or Ask inventory.
Set a page-wide body declaration, such as `data-annotations="page"`, on the sample
template when the child needs it. Leaf carries that declaration onto the child's
body; the surrounding page keeps its own choice.
The child is temporary: use an ordinary Leaf page when its history must outlive
the sample. A live sample needs a server, so a page declaring one cannot be
exported (`references/serving-pages.md`, "Exported files").

To start with fictional conversations or decisions, author an inert JSON script
in the parent and name its id in the template's `data-sample-events`:

```html
<script id="service-history" type="application/json">
[
  {"id":"service-question","kind":"comment","author":"user",
   "anchor":{"section":"service-note"},"text":"Does Sunday keep the same timetable?"},
  {"kind":"reply","author":"agent","parent":"service-question",
   "text":"Yes, both weekend days use this timetable."}
]
</script>
<lf-sample id="service-window" label="weekend service" window>
  <template id="service-page" data-sample data-sample-events="service-history">
    <h1>Weekend service</h1>
    <p id="service-note">The shuttle runs every hour.</p>
  </template>
</lf-sample>
```

The array contains ordinary event commands, checked against the child document
at `page check` and admitted before its first presentation. Give an event an explicit
`id` when a later command references it; omitted ids and timestamps are supplied,
and the history belongs to revision 1. Several samples can name the same script;
each gets an independent copy. Reset restores that authored history. The script
must be inline `application/json` in the template's parent document. Its events
never appear in the outer log: leave fictional fixture anchors inside the template,
and use this declaration rather than posting setup events from a page module.

To begin with threads from the parent, set `data-sample-threads` on the
template to their space-separated thread ids. The declaration selects from the
parent's standing log rather than requiring it: a page whose log does not hold one
of those threads yet — a first version, or a copy made from the source alone — opens
the sample without that thread. Their anchored content must exist in the
child. Reset copies those threads again from the parent; subsequent child
replies remain independent. A template chooses either `data-sample-events` or
`data-sample-threads`, never both.

The child is a document of its own: a `<style>` or module script in the template
applies to the child alone, and the surrounding page's styles and scripts do not
reach it. A page module can await the element's `ready` promise to receive the child
`Document`, and await `reset()` to replace it. The bubbling `lf-sample-ready`
event carries `detail.document` after each child presents, including Reset, so
host controls can reapply a selected view without inspecting the Reset button.
To select a conversation, call `await sample.showThread(id)` with its root event id;
this shows the same page destination as its marker. To inspect it in Threads,
call `await sample.showThread(id, {surface: "panel"})`. The panel view accepts
`status: "open" | "resolved" | "all"` and `waiting: "user" | "agent" | "all"`;
omitted values restore Open and unrestricted waiting. A panel view may omit the
id to show its list. Completion means the selected view has presented; it returns
false when a newer selection or Reset supersedes it. Outer controls keep keyboard
focus. Use this method instead of clicking the child's private chrome or observing
its DOM. Reapply the selected view on `lf-sample-ready` after Reset.
Author child content in the
template rather than copying rendered controls from the parent. Ordinary
`lf-sample` children, without a template, remain static quoted material.

An ordinary served Leaf page can appear in a plain `<iframe src="…">`, keeping
that page's durable history. Use its existing served URL. The parent and child
must share the browser origin: scheme, hostname, and port. Another local port
is a different origin. Leaf blocks cross-origin parents so another site cannot
place an authenticated Leaf control beneath a misleading interface. Framing
does not copy or reset the page.

## Stable anchors

Give each section, major block, and Leaf element a stable, meaningful `id` at the
tightest semantic boundary a user can distinguish. Where a sole child fills a
transparent wrapper, let the child carry the pair's one id.
Group a heading with its eyebrow or subtitle in `<hgroup>` so the complete title
has one box. Put its stable address on the group; the heading supplies the contents
label, while the group supplies the destination and position. When the title leads
an identified section, that section owns the public address instead: put its id on
the `<section>`, so a link arrives at the whole section, eyebrow included.
An id a heading needs for an internal
relationship such as `aria-labelledby` is not the section's public address.
Threads and reading position attach to those ids across versions, and so does a
user comparing this version with an earlier one: the id is how the comparison
finds what the block said before, so a rewritten paragraph keeps the id it had.
Stay out of the `lf-` prefix: it is the runtime's
namespace for ids and for classes alike, and `data-lf-` is the same for
attributes. `page check` refuses all three, including a name the runtime does
not write today — the namespace is reserved, not the list of names in it.
An id also must not look like the ids the event log mints, exactly eight lowercase
hex digits such as `4f9e2a1c`: a command's id argument names a widget or a message,
so `page check` refuses that shape too.

A code block, table, figure, or aside that a user will point at as a whole also
needs a tight id, either on itself or on its immediate semantic container.

## Reading cost

Open words are read; collapsed words are read only by a user who goes looking
for them. So whatever the page asks its readers to take in or answer stands open:
the finding, the evidence it rests on, and what they are asked to review, decide,
or comment on, a proposed plan included. A disclosure holds what they can skip and
still do that: history, method, source excerpts, exhaustive support, transcripts,
and raw output. Collapsed words stay quotable, and the runtime opens the
disclosure when a comment or a walk lands inside one.

The title names the page, and the lede under it carries the finding. A section
that reaches a finding says it in the heading, briefly enough to scan in an
`lf-toc` margin; supporting qualifications belong in the opening sentence. A
`<summary>` and an option's `<strong>` do the same for what they cover.
"Why the prefixes matter" and "What we learned" promise a finding and withhold
it. A name that only says what it holds is right where there is no finding to
state, over a list, a table, or a board that speaks for itself.

Write for what the user has seen, which is this conversation and the page so
far. Introduce the names a decision depends on, put evidence on the page for a
claim they could doubt, and drop the journey once the conclusion replaces it.

Use `lf-gloss` for a local term, acronym, or premise the reader can open beside a
phrase. Citations remain links; argument-bearing qualifications remain visible.
Longer asides belong in prose, a disclosure, or a sidenote.

## Pre-handover review

Step 3 of the main skill's "Operate" decides when a page takes this review. Every
source activation already runs the deterministic markup check; this review adds the
browser gate and a reading:

```bash
leaf page check <page> --render
```

It runs the browser gate in both color schemes, including when the host gives you
no separate browser tool. Fix every failure; a screenshot is not a substitute.

A clean check then saves screens of the page and names them: down the page three times,
on a desktop, in the widest window, where whatever scales with the window is at its
largest, and on a phone, each as far as its first eight screens (the check says when the
page runs on past them, and a long page's end then needs its own look); and one screen
at each width where the page's own arrangement is at its tightest before it changes,
such as a sidebar page just before its track stacks or a row of tiles just before it
wraps. Read every one. The gate finds what is broken; only a reading finds a drawing
whose labels shrink past reading in a narrow body or grow past the page's text in a wide
one, a row that wraps to leave one tile alone, a pin over the end of a heading, or a
summary the phone puts after everything else. Fix what the page can fix, and check
again.

Once the check is clean, and before the page goes to the user, have someone read it
as the user will meet it. You wrote it from research, notes and questions the user
never saw, so its names and shorthand resolve for you and not for them. Give a
subagent the user's request and the saved screens with their labels, and nothing
else, and have it read the page as the user would, reporting each place it could not
follow or had to guess. Fix what it reports. Your own reading still checks that each
heading gives the finding it promises, each claim has its evidence and each decision
its control, each drawing adds information, no passage describes a shape the page
could draw, and everything standing open in the column is there because the user
needs it.

Follow the page's links and operate its navigation with pointer and keyboard.
At each destination, check that the visible content and focus leave the user
oriented and able to continue; compare equivalent moves across the page's views.

For a page with Asks, the check also saves the window at each of the first eight
as `a` reaches it from the top, which is how a user working the page meets each
question. At each arrival, confirm that the question, shared premise, alternatives,
and evidence that distinguishes them are visible together, the displayed numbers
match the available actions, and the next press of `a` reaches the next thing waiting
on the user (an open Ask, a thread whose question is theirs, or a move to send again)
while the complete page remains visible.

Without a way to inspect the rendered page, read `leaf page state <page>`'s
`state` and `asks` alongside the active HTML to review the words, evidence, and
available choices. Report the render command's result separately from the visual
and keyboard review you could not perform. If the command cannot launch a browser,
it says so and goes on: report the render check as unfinished, and, where it also
says the page's code was not run, that run as well. A text reading does not establish
layout or interaction quality.
