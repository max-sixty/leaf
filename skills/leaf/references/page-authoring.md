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

`<page>/registry.json` is the vocabulary `page init` vendored; a
`page/registry.json` the page writes adds to it or replaces its entries ("Page
behavior"). List the vendored keys without printing the entries:

```bash
registry="<page>/registry.json"
jq 'keys' "$registry"
```

For a tag whose shape the page is copying, the worked example and the attribute
schema are enough to write the markup, at a fraction of the reading cost. Ask for
a group's parent and child together, because the parent's example is the one that
shows both:

```bash
registry="<page>/registry.json"
jq '{"lf-options": .["lf-options"], "lf-option": .["lf-option"]}
    | map_values({"x-example", properties, required})' "$registry"
```

Read the complete entry wherever the page does more than the example shows, and
for every `$` fact:

```bash
registry="<page>/registry.json"
jq '{"lf-chart": .["lf-chart"], "$series": .["$series"]}' "$registry"
```

The field the short query leaves out is `description`, and it carries what no
schema can state: what may go inside the tag, what the widget does when the
user acts on it, and how to word the question it puts. Package-defined tags and
`$` facts join the same key list. `leaf page guidance <page>` lists the composed
guidance audiences and `leaf page guidance <page> <audience>` prints one guide;
read `author` when it is present, and the assigned audience before acting in any
other role.

## Document scaffold

Write a complete HTML document. The authored head names and describes the page;
Leaf adds the encoding, CSP, identity, theme, runtime, and canonical address when it
delivers the document. Put page-specific CSS in `<style>` and JavaScript in inline
module blocks. Every `lf-*` element has an explicit end tag.

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
- **Regions that stay in view together** while each scrolls on its own, such as a
  queue beside its detail, are a workspace (below).
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, Ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. Page tabs are sections of one page: each panel takes the page's
  width, so a Layout class on `main` widens every tab, and a sidebar stands beside
  them as on any page. The `lf-tabs` entry says which placement makes which, and how
  to order and retire views.

A page grows without changing kind: a report that gains live status gains a row of
tiles, and its comments and anchors stay put.

The banner and the bottom bar at the foot of the window are fixed reservations, so
the room a page has depends only on the window, and nothing Leaf draws moves the page's
content: the rail stands in room the page leaves beside its column ("The rail and the
margin", below).

### Layouts

A Layout is a class that arranges the box it is on. Put one on `main` to shape the
page, or on any block to arrange that block's children. `layout-column` on a block keeps
the measure but gives it no room to break out into, since that room is the page's:

| Class | Arranges |
| --- | --- |
| `layout-column` | the reading column, and a block's breakout beside it |
| `layout-wide` | a page as wide as the window, up to a cap, holding one flow |
| `layout-sidebar` | a body beside its `aside`, with a `header` and `footer` across both |
| `layout-tiles` | equal cells, as many to a row as fit |
| `layout-workspace` | a page that fills the window: `header`, one body, `footer` |

On `main`, every class but `layout-column` makes a wide page: every block, the title
included, starts at one left edge and takes the page's width, text keeps the reading
measure, and the title is set larger.

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
one of these, whatever its length: its contents stand in the margin beside the column
("The rail and the margin"), and its figures keep the column's measure. Stack each
track's regions inside it, so every region stands on the same two vertical lines, rather
than a new split per row whose edges land somewhere new each time.

A track shorter than the window can stay in view while the body scrolls beside it:
give the `aside` `align-self: stretch`, so it runs the body's height, and the block it
holds `position: sticky; top: var(--lf-top)`, which keeps that block just below Leaf's
banner. The block sticks only inside the track, so wherever the two stack, for either
reason, the track is only as tall as what it holds and nothing sticks over the body; no
width is needed. Leave a taller track in flow, since sticking it would hide its end
until the page ends.

Draw each region the same way, as a `section.panel` with a short heading, and keep a
`.callout` with a status tone (`warn`, `danger`, `ok`) for the one thing the reader must
act on; a row of `.tag` chips in the same tones under the lede says the page's state at a
glance.

### A workspace

`<main class="layout-workspace">` fills the window's height below the banner: its
`header` and `footer` take what they hold, and its one body between them takes the
rest. The header is one row, the title with the page's state beside it as `.tag`
chips, so the panes keep the window: write no lede, eyebrow or legend there, and put
what a lede would say at the top of the pane it is about. The body is one `lf-pane`, a
widget that composes its own regions, or the page's own grid of panes, such as a run's
log beside the chart it explains, which the page's `<style>` places:

```html
<main class="layout-workspace">
  <header><h1>…</h1><p><span class="tag warn">…</span></p></header>
  <div id="regions">
    <lf-pane id="log" label="Log">…</lf-pane>
    <lf-pane id="chart" label="Chart">…</lf-pane>
  </div>
</main>
```

```css
#regions { display: grid; grid-template-columns: minmax(16rem, 1fr) 2fr; gap: var(--sp-4); }
@media (width < 720px) { #regions { grid-template-columns: 1fr; } }
```

Stack the panes below 720px, where the Layout lets the page scroll: panes stacked in a
wider window still share its one height, and `page check --render` refuses them.

A queue whose items open one at a time beside it, such as tickets, cases or findings to
decide, is one `lf-tabs list="side"` as the body: its list is the queue and each item an
`lf-tab`, so one opens beside the list, a link or an Ask opens its own, and each tab counts
the Asks its item still holds. Write no script to select, hide or mark an item; the tab
set does all three.

Each pane's body scrolls on its own, and a widget that fills the body of a full-height
workspace, such as a playground's stage, grows to the window's height. The `lf-pane`
entry says what a pane holds. Let the Layout allocate the height: page-specific
positioning should not be needed to keep a pane or footer reachable. Where the window is
too small to hold the regions, the panes take their natural height and the page scrolls.

### Bounds and widths

A log, feed, or long listing bounds its own height with `data-bound`, naming the end
its newest entry is at. Put the entries in the order the reader needs, then bound
that order. A list that grows downward takes `data-bound="end"`, which opens it on
its last line, keeps that line in view while the user is at the end, and leaves them
where they scrolled back to otherwise. A newest-first list takes
`data-bound="start"`, which opens it at the top, as the page's own activity feed
does. Some widgets bound themselves by default. Don't make a box scroll vertically with page
CSS: Leaf keeps no reading position in a scroller it did not make, and `version
check` advises against one.

An individual block or section may request a responsive allocation with
`data-width="column"`, `data-width="wide"`, or `data-width="available"`. `column`
uses the standard prose measure, including inside a wider section. `wide` uses the
shared capped evidence width. `available` uses all room left by the page shell, frames,
chrome, and a margin resident that takes its side, such as a sidebar standing in the
margin or the contents map's spine; the markers beside it then stand as pins on it, and
it moves below a note hanging level with it. The occurrence overrides a
widget's package default, so `data-width="column"` can deliberately keep a normally wide
widget with the prose.
Use these names on the semantic block itself, including a native `table`, `lf-code`, or
`lf-diff`; do not reproduce their responsive widths in page CSS.

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
- A wide page fills the window up to its cap and keeps no rail there. Its
  markers stand as pins over the page by their targets, as every marker does where the
  rail does not stand: in a narrower window, and in a pane that scrolls on its own. A
  block's pin stands inside its top-right corner and a run of text's just after its
  last word, unless that covers words, a control, or another block; then it takes the
  nearest room beside its target that covers none, such as the free end of a line or
  the gap below it. Where its target leaves no such room, it may take the empty end of
  a neighbouring block's line, such as beside a short heading above it, unless that
  block paints its box (a fill, border or shadow, as a card or table does). A pin is
  26px with a mouse and 44px under a finger, and where no
  such room exists, as for a pair of them in a phone's full lines, it stays in the
  corner over the block's words.
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
readable and its parts stay commentable. A recorded video is flat and heavy, and
belongs only where the explanation leaves the page. Use a table when the user
compares the same dimensions across items; use `lf-compare` for a few alternatives
read as wholes, and `lf-options` when the user must choose among them. A headline
measurement is a metric, and a pattern across measurements is a chart. Movable
things form a board. Use images only when they carry information.
`authoring-evidence.md` says which element draws each kind, and how to draw a figure
of your own.

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
modules below `page/`, referenced through `/page/…`. Page stylesheets and their local
dependencies may live there too. Relative imports stay within `page/`; code that
integrates with Leaf may import the public `/runtime/widget-api.js` module. Leaf captures
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

`leaf page check` runs a page's own code, a module script or a page widget the
document places, once in the host's browser: through upgrade, presentation, and one
frame after it. It fails on every error the page would report to you through the
watcher, an uncaught exception or a rejected promise with the source location it came
from, so a module that throws on its first paint is found before the URL goes out.
Code that runs only after a gesture or a timer is not reached; operate it in the
pre-handover review. A page with no code of its own is checked without a browser.

`page/registry.json` may contribute declarations using the package registry language.
Its element entry replaces the selected layer's complete entry; shared `$` declarations
compose at their declared grain. Declaration and implementation ownership are separate:
a page declaration keeps the package widget unless `page/widgets/<tag>.js` exists, and a
page widget may replace the package implementation without restating its declaration.
Both choices are fixed in the revision manifest.

Use a package when behavior, styling, or vocabulary is reused across pages. A one-page
explorer or playground keeps its code in `page/`. Leaf captures literal local module
and stylesheet dependencies, and refuses unresolved imports, filesystem escapes, classic
scripts, event-handler attributes, and `javascript:` URLs.

A stylesheet, font, module, or image may also come from Google Fonts or a public script
CDN, the set a Claude artifact page may use: jsdelivr, cdnjs, unpkg, Tailwind's, and
jQuery's. Name it by its absolute `https://` URL; the page loads it as written, so it
arrives only while the user is online. Load a library as a module — jsdelivr's
`/+esm` builds one from any npm package — since a classic script is refused. A
reference to any other origin is refused, and the refusal names the ones admitted.

Typed data and media remain inert inputs. Read them through their Leaf/browser APIs;
do not turn their contents into source code or markup.

## Live samples

Use `lf-sample` with one direct `template[data-sample]` to let the user
operate a complete Leaf page inside the surrounding document. Give both the
element and template stable ids, and put the child page's main content in the
template:

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
Threads row of its chrome. A click or Tab reaches the child directly; its normal
widget controls, keyboard routes, comments, and replies work there. Escape closes
the child's open controls before returning to the surrounding page. Reset creates a
fresh page from the template.
Child decisions and comments do not change the parent's log or Ask inventory.
The child is temporary: use an ordinary Leaf page when its history must outlive
the sample. A live sample needs a server, so a page declaring one cannot be
exported (`references/serving-pages.md`, "Exported files").

To begin with threads from the parent, set `data-sample-threads` on the
template to their space-separated thread ids. The declaration selects from the
parent's standing log rather than requiring it: a page whose log does not hold one
of those threads yet — a first version, or a copy made from the source alone — opens
the sample without that thread. Their anchored content must exist in the
child. Reset copies those threads again from the parent; subsequent child
replies remain independent.

A page module can await the element's `ready` promise to receive the child
`Document`, and await `reset()` to replace it. Author child content in the
template rather than copying rendered controls from the parent. Ordinary
`lf-sample` children, without a template, remain static quoted material.

## Stable anchors

Give each section, major block, and Leaf element a stable, meaningful `id` at the
tightest semantic boundary a user can distinguish. Where a sole child fills a
transparent wrapper, let the child carry the pair's one id.
Put a titled section's id on the `<section>`, not on its heading, so a link to it
arrives at the whole title, eyebrow included. An id a heading needs for an internal
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

Open words are read; collapsed words are there when the user wants them. What
stands open in the column is what the user has to take from the page. History,
method, source excerpts, exhaustive support, transcripts, and raw output are
backing by default and go under `<details>`. Collapsed words stay quotable, and
the runtime opens the disclosure when a comment or a walk lands inside one. An
open Ask and the evidence it turns on never collapse.

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

Then read the page as the user will. Take the headings on their own first, and
check that none of them promises a finding it does not give. Confirm that
referents are introduced, claims have evidence, decisions have controls, each
drawing adds information, no passage describes a shape the page could draw, and
everything standing open in the column is there because the user needs it.

Follow the page's links and operate its navigation with pointer and keyboard.
At each destination, check that the visible content and focus leave the user
oriented and able to continue; compare equivalent moves across the page's views.

For a page with Asks, start at the top and press `a` through them. At each
arrival, confirm that the question, shared premise, alternatives, and evidence
that distinguishes them are visible together, the displayed numbers match the
available actions, and the next press of `a` reaches the next open Ask while the
complete page remains visible.

Without a way to inspect the rendered page, read `leaf page state <page>`'s
`state` and `asks` alongside the active HTML to review the words, evidence, and
available choices. Report the render command's result separately from the visual
and keyboard review you could not perform. If the command cannot launch a browser,
run `leaf page check <page>` for the markup and report the render check as
unfinished; for a page with code of its own, that check needs the browser too, so
report the run of its code as unfinished as well. A text reading does not establish
layout or interaction quality.
