# Page authoring

This reference holds what every page needs. What only some pages need has a
reference of its own, named where a choice below leads to it.

## Show the subject

Decide what each view shows before writing its words. Find what the user would have
to picture from a description to judge the view's point, and put that thing on the
page in the form it takes:

- An interface that exists is a screenshot, cropped or marked where the point sits
  so the eye lands there, its crop cutting through background rather than through
  text the reader would try to read; a visual change is an `lf-shot` before-and-after
  capture.
- A behavior, such as an interaction, a motion, or a process over time, runs: in a
  live sample the user operates (`live-samples.md`), or in a page module that draws it
  from its state and the moment, with controls to pause and scrub, so every moment
  stays readable and its parts stay commentable. A fixed recording or screen
  capture follows `authoring-evidence.md`, "Source files and media".
- A proposal or mechanism that nothing can show yet is drawn: where things sit and
  what bounds, covers, or moves what; what contains, calls, or feeds what; how a
  state changes; today beside proposed; alternatives in one frame at one scale.
- Numbers whose shape is the point, such as a trend, a ranking, groups on one scale,
  or series moving together, are an `lf-chart`, even when the numbers compare the
  same dimensions across items. The chart labels the values the page's argument
  cites (`lf-chart`'s instructions); put the rest in a table below it in
  `<details>` when readers also need exact values.
- Code, a command, a message, or any other wording is the text itself, as it would
  appear, where that text is what the user judges. What code does, such as what it
  draws, which rule wins, or what calls what, is the interface, behavior, or
  mechanism above, with the code beside it.

A page deciding, planning, or reviewing something shows it the same way: a work item
that fixes a visible fault shows the fault, and an ask's options show what each
answer gives the user (`authoring-asks.md`). A table or list whose rows name places,
sizes, or connections is a drawing written out.

Use a table for value lookup, mixed units that cannot share an axis, or comparisons
with text-heavy cells; use native sections for a few alternatives read as wholes,
and `lf-options` when the user must choose among them. A headline measurement is
a metric. Grouped cards form a board; its registry entry guides when to use it.
Use images only when they carry information.
`authoring-evidence.md` says which element draws each kind, and how to draw a figure
of your own.

The prose beside what the page shows says only what it cannot. What is left for prose
is the claim, the reason it holds, the cost, and the question the page is asking. A
few sentences hold them. A section that runs longer is carrying either something the
page should show or backing that belongs under `<details>`.

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

## Composing a page

Most pages use a reading column, `<main class="layout-column">`. Text stays within
the column's measure; wider blocks extend beside it without moving the prose.
Without a Layout class, Leaf sets no page geometry: the page lays out as the browser
lays out plain HTML, and `main`'s blocks fill its width. A diagram or board
declares its preferred width in the registry; `data-width` makes the same request
for other blocks, such as a wide table (`page-layout.md`, "Bounds and widths").
Compose the page from these:

- **Prose read in order** — a plan, a review, a write-up, a decision — is plain
  semantic HTML, with nothing declared.
- **Independent status tiles** are a block with `class="layout-tiles"`, which sets its
  children in equal cells, as many to a row as fit. Each cell holds a surface — a
  metric, chart, table, list or log, with at most a caption — rather than paragraphs;
  a row of headline numbers can use ordinary `dl` elements in one. Tiles of paragraphs are prose
  cut into columns, and read worse than the column.
- **A comparison** is a table or native sections arranged by the page's CSS.
- **Controls beside evidence** is a playground, which declares how its controls
  operate its preview.
- **A screen the reader moves through rather than scrolls**, like a mail client or a
  dashboard, such as a queue worked one item at a time or a run's log beside the chart
  it explains, is a workspace (`page-layout.md`, "A workspace"). A document read top
  to bottom beside a panel kept in view, such as a postmortem beside its timeline, is
  instead a `layout-sidebar` page whose `aside` sticks (`page-layout.md`, "A sidebar
  page").
- **Several views of one artifact** are one `lf-tabs` set: page tabs for
  project-scale views that share one history, Threads panel, ask inventory, and
  revision sequence, and a tabbed section for local alternatives within the
  surrounding view. Page tabs are sections of one page: each panel takes the page's
  width, so a Layout class on `main` widens every tab, and a sidebar stands beside
  them as on any page. The `lf-tabs` entry says which placement makes which, and how
  to order and retire views.

A page grows without changing its Layout: a report that gains live status gains a row of
tiles, and its comments and anchors stay put.

Leaf's banner and bottom bar reserve their own space in the window, and Leaf seats
annotation markers in the margin or over their targets, so lay out the page without
reserving room for either. `page-layout.md` holds each Layout's geometry, wide and
bounded blocks, the margin, and page CSS that reaches Leaf's controls.

## Contents navigation

Long scrolling documents include a contents outline. It gives the reader a
persistent route between sections and shows where they are in the document. A short
document that can be read at a glance needs no outline. Keep navigation available at
the desktop opening and while the document scrolls; in a narrow window, place it
before the substantive reading.

Write an empty `lf-toc` with a stable id. On a column page, put it in an
`aside.sidebar`, directly inside `main` near the opening:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

With room in the desktop margin, Leaf presents the column's outline as the contents
spine; in a narrow window it is an open outline in the page's flow (`page-layout.md`,
"The rail and the margin"). On a sidebar page, keep the outline and short verdict or
status available in the opening overview inside the Layout's `aside`
(`page-layout.md`, "A sidebar page"). Keep that overview short enough to fit the
window, with detailed evidence and history in the body or behind a disclosure.
Workspaces and root page tabs use their own navigation.

## Read the registry

Write semantic HTML and use the registry's elements and class idioms. The vendored
theme owns palette, type, spacing, headings, tables, code, and widget presentation.
Use a page-local `<style>` only for presentation unique to this page.

Read the shared author instructions, when the page's packages carry any, before
choosing vocabulary:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`<page>/registry.json` is the vocabulary `page init` vendored; a
`page/registry.json` the page writes adds to it or replaces its entries
(`page-behavior.md`). Ordinary keys are authoring vocabulary: custom-element names or CSS
selectors. `$` keys are shared layer facts. Discover all vocabulary by purpose:

```bash
registry="<page>/registry.json"
jq 'with_entries(select(.key | startswith("$") | not))
    | map_values(.description)' "$registry"
```

Read a selected entry's complete example and instructions. Elements also carry
an attribute schema; idioms show the semantic HTML and classes the theme styles.
Both use the same lookup and the same `x-example` and `x-instructions` fields:

```bash
jq '.["lf-options"], .[".eyebrow"]' "$registry"
```

Before writing markup, read the composed author instructions for the entries you
will use, including examples you copy:

```bash
leaf page instructions <page> --use lf-options --use .eyebrow | jq -r '.author // empty'
```

Each repeated `--use` selects an element or idiom. The command includes shared
package instructions, the selected entries' instructions, elements and idioms used in
their examples, and declared data contracts. It returns one JSON map from audience
to complete text. Whoever takes another role, you or an agent you assign, reads
that audience's value for the same selection before acting. Inspect the map's
keys to see the roles it carries; `--contract` selects a data contract directly.
"Package contract" in `packages.md` defines composition.

Read each `$` fact the page relies on in full:

```bash
jq '.["$series"]' "$registry"
```

`description` identifies purpose and when an entry helps. The schema and
`x-example` state its form; `x-instructions` carries authoring choices and
obligations the schema cannot express. Implementation contracts live beside
their owning modules. Package-defined elements, idioms, and `$` facts join the
same registry.

## Document scaffold

Write a complete HTML document. The authored head names and describes the page;
Leaf adds the encoding, identity, theme, runtime, and canonical address when it
delivers the document. Put page-specific CSS in `<style>` and JavaScript in
`<script>` (`page-behavior.md`). Every `lf-*` element has an explicit end tag.

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

## Markup

Widget attributes carry scalars; children carry prose; a titled compound member uses a
leading `<strong>`. A data-bodied widget such as `lf-code` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text.

Format filenames and paths as inline code, using backticks in Markdown and
`<code>` in HTML; use an authored link when the file has a known destination.

Display source snippets as `<pre><code class="language-javascript">…</code></pre>`,
or `lf-code language="javascript"` for a line-numbered walkthrough, naming the actual
language from `$languages.names`. Format illustrative code with the language's usual
indentation and line breaks, preserving its behavior when you reformat an example.
Keep brevity in the surrounding prose rather than packing distinct statements or
fields onto a line. The runtime colors the declared language and preserves authored
whitespace. Verbatim source quotations keep their exact text; logs and transcripts
stay literal and uncolored when they are not source code.

Keep content within its allocated column, visual surface, or pane. The theme scrolls a
`<pre>` or a table that runs wider than its container and fits an image or SVG to it,
so none of them needs a width. A table that scrolls has every column at its longest
unbreakable run, so prose that wraps in it wraps a word a line while the reader also
scrolls sideways. The browser gate advises on each width from a 360px phone up where a
table scrolls with a cell in it wrapped: put an identifier in `<code>`, where it breaks
inside its cell, rather than bare, where it holds its column and squeezes the prose
beside it, and keep the columns to what the measure holds at the narrowest width the
page's readers use. Widgets whose element declaration requests wider space size
themselves within the page's available room. Preserve the meaningful detail in a
diagram or comparison rather than shrinking its source solely to fit the prose column.

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
