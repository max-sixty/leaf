# Page authoring

- [Read the registry](#read-the-registry)
- [Document scaffold](#document-scaffold)
- [Composing a page](#composing-a-page)
- [Theme and vocabulary](#theme-and-vocabulary)
- [Page behavior](#page-behavior)
- [Live specimens](#live-specimens)
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
  <main>…</main>
</body>
</html>
```

## Composing a page

Choose the page's form from the shape of its subject, before anything else:

- **A document** is an argument read in order: a plan, a review, a write-up, a
  decision. It stays in the reading column, and nothing is declared. Most pages are
  documents.
- **A sheet** is a set of regions read side by side: a board with its status, a
  release dashboard, a queue sorted into buckets, a long review whose contents and
  verdict stay beside the code. Write `<main data-width="available">`.
- **A workspace** is a sheet whose regions must stay in view together while each
  scrolls on its own: a queue beside its detail, a playground's controls beside its
  preview. Write `<main data-width="available">` with an `lf-workspace` as its only
  block.

A page can move between forms as it grows without changing kind: a report that gains
live status gains a grid, and its comments and anchors stay put. Width alone is not a
reason to change form: a wide comparison or diagram stays in a document at the width it
declares.

### A document

Within the column, compose with these:

- **Independent status tiles** are an `lf-grid` inside the explanation. Each cell
  holds a surface — a metric, chart, table, list or log, with at most a caption —
  rather than paragraphs; a row of headline numbers is a grid of `lf-metric` tiles.
  A grid of paragraphs is prose cut into columns, and reads worse than the column.
  A grid in a document stands at the wide width, centred on the column; when the
  tiles are the page, the page is a sheet.
- **A comparison** is `lf-compare`, which keeps its variants paired at any width.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview.
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, Ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. The `lf-tabs` entry says which placement makes which, and how to
  order and retire views.

### A sheet

On a sheet every block, the title included, starts at one left edge and takes the
sheet's width, while text keeps the reading measure; the title is set larger. A sheet
reads as one structure when every region stands on the same vertical lines, so give it
one set of tracks: typically a body beside a rail as one `lf-grid` of
`columns="2fr 1fr"` (`3fr 1fr` for a board), each track a nested `columns="1"` grid
stacking its regions, rather than a new grid per row whose splits land somewhere new
each time (`version check --render` advises on those). Put what the reader works
through in the body and what they keep an eye on — status, counts, the verdict's
follow-ups, the contents — in the rail. The tracks stack where the rail would become
too narrow.

Draw each region the same way, as a `section.panel` with a short heading, and keep a
`.callout` with a status tone (`warn`, `danger`, `ok`) for the one thing the reader must
act on; a row of `.tag` chips in the same tones under the lede says the page's state at a
glance. `data-width="wide"` caps the sheet at the shared evidence width instead of the
window.

### A workspace

A workspace holds its regions in view together only as a sheet's, or a page tab's,
sole content element, and elsewhere stays in document flow; `version check` refuses a
page made of one workspace that is not a sheet. The `lf-workspace` entry says where the
title goes and which elements its body can be, and the `lf-pane` entry what a pane
holds. Place several panes with an `lf-grid`, such as `columns="1fr 2fr"` for a queue
beside its detail. Let Leaf allocate the space: page-specific positioning should not be
needed to keep a pane or footer reachable. Where the window cannot hold the regions,
the workspace flows like a sheet and the page scrolls.

### Bounds and widths

A log, feed, or long listing bounds its own height with `data-bound="end"`, which
keeps it on its newest line while the user is at the end and leaves them where
they scrolled back to otherwise; `data-bound="start"` opens it at the top. Some
widgets bound themselves by default. Don't make a box scroll vertically with page
CSS: Leaf keeps no reading position in a scroller it did not make, and `version
check` advises against one.

An individual block or section may request a responsive allocation with
`data-width="column"`, `data-width="wide"`, or `data-width="available"`. `column`
uses the standard prose measure, including inside a wider section. `wide` uses the
shared capped evidence width. `available` uses all room left by the page shell, frames,
chrome, and occupied margins. The occurrence overrides a widget's package default, so
`data-width="column"` can deliberately keep a normally wide widget with the prose.
Use these names on the semantic block itself, including a native `table`, `lf-code`, or
`lf-diff`; do not reproduce their responsive widths in page CSS.

Show evidence at the scale needed to judge it. For a local change, supply an aligned
detail view with the complete object available for context; use whole frames when their
composition is the subject. A fitted thumbnail is an overview, not a substitute for
readable detail. Let the package provide inspection controls and Leaf allocate space and
scrolling; page-local width overrides and wheel handlers should not be needed.

## Theme and vocabulary

Write semantic HTML and use the class idioms the registry lists under `$idioms`,
where each one comes with the markup it is written as. The vendored theme owns
palette, type, spacing, headings, tables, code, and widget presentation. Use a
page-local `<style>` only for presentation unique to this page.

Widget attributes carry scalars; children carry prose; a titled compound member uses a
leading `<strong>`. A data-bodied widget such as `lf-code` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text.

The runtime injects the status banner, thread panel, Versions menu, keyboard
shortcuts, live-leaves tray, and active-asks tray, which lists the page's open Asks.
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
rules keep authored controls correct after reconnection, thread quoting, and export.

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

## Live specimens

Use `lf-specimen` with one direct `template[data-specimen]` to let the user
operate a complete Leaf page inside the surrounding document. Give both the
element and template stable ids, and put the child page's main content in the
template:

```html
<lf-specimen id="practice" label="practice release note">
  <template id="practice-page" data-specimen>
    <h1>Weekend service</h1>
    <p id="service-note">The sample shuttle runs every hour.</p>
  </template>
</lf-specimen>
```

The specimen's gutter contains only the content being demonstrated. Keep labels,
host controls, and instructions about using the specimen outside that gutter;
instructions that belong to the demonstrated page remain inside it.

The child uses the parent's selected layer and starts with its own event log. It
stands in the surrounding page as a block as tall as its content, with only the
Threads row of its chrome. A click or Tab reaches the child directly; its normal
widget controls, keyboard routes, comments, and replies work there. Escape closes
the child's open controls before returning to the surrounding page. Reset creates a
fresh page from the template.
Child decisions and comments do not change the parent's log or Ask inventory.
The child is temporary: use an ordinary Leaf page when its history must outlive
the specimen. A standalone copy keeps the rendered child and its assets as an
isolated static document; native links and disclosures remain usable.
Live specimens require a server, so pages declaring them cannot be exported with
`--interactive`; use the static copy instead.

To begin with conversations from the parent, set `data-specimen-threads` on the
template to their space-separated root event ids. The declaration selects from the
parent's standing log rather than requiring it: a page whose log does not hold one
of those roots yet — a first version, or a copy made from the source alone — opens
the specimen without that conversation. Their anchored content must exist in the
child. Reset copies those conversations again from the parent; subsequent child
replies remain independent.

A page module can await the element's `ready` promise to receive the child
`Document`, and await `reset()` to replace it. Author child content in the
template rather than copying rendered controls from the parent. Ordinary
`lf-specimen` children, without a template, remain static quoted material.

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
attributes. `version check` refuses all three, including a name the runtime does
not write today — the namespace is reserved, not the list of names in it.

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

Show a visible subject with an image instead of describing its appearance. Show
an interface with a screenshot, and a visual change with an `lf-shot`
before-and-after capture. A relationship, sequence, or system state transition is
a diagram. Use a table when the user compares the same dimensions across items;
use `lf-compare` for a few alternatives read as wholes, and `lf-options` when the
user must choose among them. A headline measurement is a metric, and a pattern
across measurements is a chart. Movable things form a board. Use images only when
they carry information. The prose beside a shape says only what the shape cannot.
What is left for prose is the claim, the reason it holds, and the question the page
is asking. A few sentences hold all three. A section that runs longer is carrying
either a structure with a shape of its own or backing that belongs under
`<details>`.

Write for what the user has seen, which is this conversation and the page so
far. Introduce the names a decision depends on, put evidence on the page for a
claim they could doubt, and drop the journey once the conclusion replaces it.

## Pre-handover review

Step 3 of the main skill's "Operate" decides which page takes this review, by
its lifetime: a finished record before its URL first reaches the user, and a
quick page before the stamp that turns it into one. Every source activation already runs the
deterministic markup check; this review adds the browser gate and a reading:

```bash
leaf version check <page> --render
```

It runs the browser gate in both color schemes, including when the host gives you
no separate browser tool. Fix every failure; a screenshot is not a substitute.

Then read the page as the user will. Take the headings on their own first, and
check that none of them promises a finding it does not give. Confirm that
referents are introduced, claims have evidence, decisions have controls, diagrams
add information, and that everything standing open in the column is
there because the user needs it.

Follow the page's links and operate its navigation with pointer and keyboard.
At each destination, check that the visible content and focus leave the user
oriented and able to continue; compare equivalent moves across the page's views.

For a page with Asks, start at the top and press `a` through them. At each
arrival, confirm that the question, shared premise, alternatives, and evidence
that distinguishes them are visible together, the displayed numbers match the
available actions, and the next press of `a` reaches the next open Ask while the
complete page remains visible.

Without a way to inspect the rendered page, read `leaf page state <page>`'s
`content` and `asks` alongside the source to review the words, evidence, and
available choices. Report the render command's result separately from the visual
and keyboard review you could not perform. If the command cannot launch a browser,
run `leaf version check <page>` for the markup and report the render check as
unfinished. A text reading does not establish layout or interaction quality.
