# Page authoring

## Show the subject

Before writing a view's words, decide what it shows. Put on the page, in its own form,
whatever the user would otherwise have to picture from a description:

- An existing interface is a screenshot, cropped or marked so the eye lands on the
  point, with crops cutting through background rather than text. Capture a panel, card
  or menu with enough of the page around it to keep its shadow and rounded corners. A
  visual change between two versions is an `lf-shot` before-and-after pair, and
  captures that vary along other axes go in a table of captures
  (`authoring-evidence.md`, "Source files and media").
- A behavior, such as an interaction, a motion or a process over time, runs: in a live
  sample the user operates (`live-samples.md`), or as an animation in `lf-motion` from
  the `motion` package, which the user can slow, pause and scrub.
- A proposal or mechanism nothing can show yet is drawn: where things sit, what
  contains, calls or feeds what, how a state changes, with today beside the proposal
  and alternatives in one frame at one scale.
- Numbers whose shape is the point, such as a trend, a ranking or groups on one scale,
  are an `lf-chart`, even when they compare the same measures across items. Label the
  values the argument cites, and put exact values in a table in `<details>` below the
  chart when readers need them.
- Wording the user judges, such as code, a command or a message, is the text itself.
  When the point is what code does, such as what it draws or which rule wins, show that
  effect in one of the forms above, with the code beside it.

A drawing or chart makes its point through its geometry: where its marks sit, their
sizes, and what contains or links them. A table or list whose rows say where things
sit, how large they are or what connects to what should be a drawing. One that only
restates the words or numbers beside it, as boxes holding its sentences or a mark per
counted item, shows nothing. When the user has nothing to picture, as when they weigh a
refactor's reasons and cost, leave the case in words and draw nothing. Use a table for
looking up values, for mixed units that can't share an axis, and for comparisons with
text-heavy cells.

Prose says what the page can't show: the claim, why it holds, its cost, and the
question the page asks. That takes a few sentences. A longer section is carrying
something the page should show, or backing that belongs in `<details>`.

## Reading cost

Readers skip collapsed text unless they go looking. Keep open everything the page asks
the reader to take in or answer: the finding, its evidence, and what they are asked to
review, decide or comment on, including a proposed plan. Collapse what they can skip
and still do that, such as history, method, source excerpts, transcripts and raw
output.

The title names the page, and the lede under it states the finding. A section that
reaches a finding states it in its heading, short enough to scan in an outline, and
puts qualifications in its first sentence; a `<summary>` and an option's `<strong>` do
the same. A heading such as "What we learned" promises a finding and withholds it. Use
a plain label only where there is no finding, as over a list, table or board that
speaks for itself.

Write for what the user has seen: this conversation and the page so far. Introduce the
names a decision depends on, show evidence for any claim they could doubt, and leave out
the story of how you got there. Use `lf-gloss` for a local term, acronym or premise the
reader can open beside its phrase. Keep citations as links, and keep visible any
qualification the argument rests on.

The user reads the page against the facts they gave you, so one figure that differs
from theirs makes them doubt the rest. Keep each supplied fact as given, with the
measure it belongs to. A number, trend, count or consequence you work out from them is
your claim: check it against the figures it rests on, and keep those figures beside it.
Where your working contradicts a supplied fact, show both and say which the page uses,
rather than correcting theirs in place.

## Composing a page

Most pages are read top to bottom in the reading column, `<main class="layout-column">`,
where text keeps to the measure and wider blocks extend beside it (`page-layout.md`,
"Bounds and widths"). Compose the page from these:

- **Prose read in order**, such as a plan, review or decision, is plain semantic HTML.
- **Independent status tiles** are a block with `class="layout-tiles"`, whose children
  sit in equal cells. Each cell holds a metric, chart, table, list or log, with at most
  a caption; tiles of paragraphs read worse than the column.
- **A comparison** is a table, or native sections arranged by the page's CSS.
- **Controls beside evidence** is a playground.
- **A screen the reader works in rather than scrolls**, such as a mail client, a queue
  worked one item at a time, a log beside its chart, or a playground that is the page's
  subject, is a workspace (`page-layout.md`, "A workspace"), whose surface fills the
  window from the title's left edge. A surface the document only cites, such as one
  exhibit among its sections, stays in the column and breaks out of it. Reading that
  supports the main surface, such as the review behind a design the reader tunes, goes
  in a part of its own on a page of parts (below).
- **A document read top to bottom beside a panel kept in view**, such as a postmortem
  beside its timeline or a review beside its verdict, is a sidebar page
  (`page-layout.md`, "A sidebar page"). A long document with only its contents beside
  it stays a column page.
- **Several views of one artifact** are one `lf-tabs` set: page tabs for project-scale
  views and a tabbed section for local alternatives within a view, placed as the
  `lf-tabs` entry says.
- **Parts of one subject that each want their own Layout**, such as a playground to try
  beside the proposal it argues for and the reasoning behind it, are a page of parts
  (`page-layout.md`, "A page of parts"). Views that share the page's Layout and a header
  across the top, such as a site's pages, are page tabs instead.

Leave no room for Leaf's panel, which takes its own at the window's foot, or for comment
markers, which sit in the margin or over their target; the reader hides markers with `o`
to read what is under one.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none. Write an empty `lf-toc` with a stable id. On a column page, put it in an
`aside.sidebar` directly inside the box carrying `layout-column`, near the top:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

On a sidebar page, the contents go at the top of the `aside` (`page-layout.md`, "A
sidebar page"). Workspaces and page tabs have their own navigation, and each column part
of a page of parts takes its own outline.

## Read the registry

Write semantic HTML in the registry's elements and class idioms. The vendored theme
styles colours, type, spacing, headings, tables, code and widgets; use a page `<style>`
only for presentation unique to this page.

First read the author instructions the page's packages share, which can steer which
entries you pick:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`<page>/registry.json` is the page's vocabulary. Its ordinary keys are element names or
CSS selectors, and its `$` keys are facts shared across the layer. List the vocabulary
by purpose, then read in full the entries you pick and any `$` fact you rely on:

```bash
registry="<page>/registry.json"
jq 'with_entries(select(.key | startswith("$") | not))
    | map_values(.description)' "$registry"
jq '.["lf-options"], .[".eyebrow"], .["$series"]' "$registry"
```

Before writing markup, read the instructions for the entries you will use, which
include those of the elements their examples use:

```bash
leaf page instructions <page> --use lf-options --use .eyebrow | jq -r '.author // empty'
```

## Document scaffold

Write a complete HTML document whose head has a title and a description; Leaf adds the
encoding, theme, runtime and viewport when it serves the page. The title and
description represent the page in a tab, a search result or a pasted link, so the
description must make sense on its own. Put page CSS in `<style>` and JavaScript in
`<script>` (`page-behavior.md`), and give every `lf-*` element an explicit end tag.

```html
<!doctype html>
<html lang="en">
  <head>
    <title>…</title>
    <meta name="description" content="…" />
  </head>
  <body>
    <main class="layout-column">…</main>
  </body>
</html>
```

## Markup

Widget attributes carry scalars and children carry prose; a titled member of a compound
widget starts with a `<strong>`. A widget whose body is data, such as `lf-code`, holds
escaped text in a `<pre>`. Escape `&` first, then `<` and `>`.

Format filenames and paths as inline code, and link a file that has a known
destination.

Show source snippets as `<pre><code class="language-javascript">…</code></pre>`, or as
`lf-code language="javascript"` for a line-numbered walkthrough, naming the actual
language from `$languages.names`; a native `code` class also accepts the grammar's
aliases, such as `language-js`. Format example code with the language's usual
indentation and line breaks rather than packing several statements or fields onto one
line, and keep it working when you reformat it. Quote source verbatim. Logs and
transcripts that aren't source code stay literal and uncoloured.

The theme scrolls a `<pre>` or table wider than its container sideways and fits an
image or SVG to it, so none needs a width. In a table that scrolls sideways, prose
wraps a word per line, so keep a table's columns to what fits the narrowest window its
readers use, and put identifiers in `<code>`, which can break inside a cell.

## Stable anchors

Give each section, major block and Leaf element a stable, meaningful `id` on the
smallest element a user would point at, including a code block, table, figure or aside
a user would point at whole. Where a wrapper holds only one child that fills it, put
the id on the child. Group a heading with its eyebrow or subtitle in `<hgroup>` and put
the id on the group, or on the `<section>` that title starts when the section has an
id. An id a heading needs for `aria-labelledby` is not the section's address.

Threads, reading position and version comparison find a block by its id, so a
rewritten paragraph keeps its id.
