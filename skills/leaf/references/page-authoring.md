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

`<page>/registry.json` is the page's complete vendored vocabulary. List its keys
without printing the entries:

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

Start from a sequential explanation and insert the other compositions where they
help, keeping the prose around them. A report that gains live status gains a grid;
it does not become another kind of page, so its comments and anchors stay put.

- **A sequential explanation** is the default: plans, reviews, write-ups. Nothing is
  declared.
- **Independent status tiles** are an `lf-grid` inside the explanation. Each cell
  holds a surface — a metric, chart, table, list or log, with at most a caption —
  rather than paragraphs; a row of headline numbers is a grid of `lf-metric` tiles.
  A grid of paragraphs is prose cut into columns, and reads worse than the column.
- **A comparison** is `lf-compare`, which keeps its variants paired at any width.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview. Use an `lf-workspace` of plain panes for task regions that
  must stay visible together with no such relationship, such as a queue beside its
  detail.

`lf-grid` places its direct children as cells. Without `columns` it fits as many
equal columns as the width allows; `columns="3"` caps that at three, and a template
such as `columns="1fr 2fr"` gives unequal columns, which stack once the grid is
narrower than 600px. A grid takes the page's available width, and each cell is a
frame: text inside keeps the reading measure, while a surface fills the cell. Nest
a grid in a cell for a cell that spans rows. Let the grid place its cells: page CSS
that sets a grid's own `display`, `grid-*` or `position` fights it, and `version
check` says so.

A log, feed, or long listing bounds its own height with `data-bound="end"`, which
keeps it on its newest line while the user is at the end and leaves them where
they scrolled back to otherwise; `data-bound="start"` opens it at the top. Some
widgets bound themselves by default. Don't make a box scroll vertically with page
CSS: Leaf keeps no reading position in a scroller it did not make, and `version
check` advises against one.

Use page tabs for project-scale views that belong to one artifact and share one
history, Threads panel, Ask inventory, and revision sequence, and a tabbed section for
local alternatives within the surrounding view. The `lf-tabs` entry says which
placement makes which, and how to order and retire views.

For a root workspace, make `lf-workspace` the sole content element directly inside
`main`, with the page title in its optional direct native `header`. A workspace used as
a page tab's sole content element follows the same bounded composition. Its body is
exactly one element. Put prose in an `lf-pane`; compose multiple named panes with
one `lf-partition`, where each partition takes two panes or partitions in `columns` or
`rows`.
The workspace's optional direct native `footer` follows its body. A pane's direct
`header` and `footer` frame its reading body; put existing action widgets in the
footer when they should stay available while the body scrolls. A pane's `label`
names it for navigation and assistive technology; author a `header` when it needs
a visible heading. Query the element declarations for their complete markup contracts.

Keep a compound widget's authoring grammar and state ownership together. A
playground supplies its own controls and preview regions; its Ask still surrounds
the playground. Structural and compound owners register their reading arrangements so the
workspace can allocate them directly; a plain wrapper does not carry allocation to
a registered descendant. An embedded workspace stays within its containing content.
Constrained windows and standalone copies expose regions in authored order, so
choose an order that remains useful when stacked. Let Leaf allocate the space;
page-specific positioning should not be needed to keep a pane or footer reachable.

Choose width separately from document or workspace form. Keep prose at a readable
measure and let declared visual surfaces use the room their task needs. A wide comparison
can remain part of a scrolling document. Use a workspace when the user benefits from
keeping task regions together, rather than merely to obtain more width.

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
shortcuts, live-leaves tray, and active-asks tray. Authors declare user asks
through the registry's Ask sources and surfaces, but do not duplicate that
chrome or maintain a second list of it in the page.

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

Page modules follow the behavior-module contract in `references/packages.md`. In
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
Put a titled section's public id on the `<section>`, not on its heading just for
`lf-toc`: the heading supplies the link text, while the section fragment arrives at
the complete title, including an eyebrow. A heading may still need its own id for an
internal relationship such as `aria-labelledby`; that id is not the section's public
address.
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
When lower-level headings name local controls or evidence rather than page destinations,
set the `lf-toc`'s `max-level` to the deepest navigational level.
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
