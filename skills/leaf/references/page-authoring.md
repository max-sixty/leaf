# Page authoring

## Show the subject

Before writing a view's words, decide what it shows. Ask what the user would otherwise
have to picture from a description, and put that thing on the page in its own form:

- An existing interface is a screenshot, cropped or marked so the eye lands on the
  point, with crops cutting through background rather than text. Capture a panel,
  card or menu with enough of the page around it to hold its whole shadow. A visual
  change between two versions is an `lf-shot` before-and-after pair, and captures
  that vary along other axes go in a table of captures (`authoring-evidence.md`,
  "Source files and media").
- A behavior, such as an interaction, a motion or a process over time, runs: in a live
  sample the user operates (`live-samples.md`), or in `lf-motion` from the `motion`
  package, for authored animations or video recordings. The package’s authoring
  instructions cover both forms and their evidence limits.
- A proposal or mechanism nothing can show yet is drawn: where things sit, what
  contains, calls or feeds what, how a state changes, today beside the proposal, and
  alternatives in one frame at one scale.
- Numbers whose shape is the point, such as a trend, a ranking or groups on one scale,
  are an `lf-chart`, even when they compare the same measures across items. Label the
  values the argument cites, and put exact values in a table below it when readers
  need them. "Reading cost" below governs whether to collapse that table.
- Wording the user judges, such as code, a command or a message, is shown as the text
  itself. When the point is what code does, such as what it draws or which rule wins,
  show that effect in one of the forms above, with the code beside it.

A table or list whose rows say where things sit, how large they are or what connects
to what should be a drawing.

A drawing or chart makes its point through its geometry: where its marks sit, their
sizes, and what contains or links them. One that only restates the words or numbers
beside it, as boxes holding its sentences or a mark or bar per counted item, shows
nothing. When the user has nothing to picture, as when they weigh a refactor's reasons
and cost, leave the case in words and draw nothing.

Use a table for looking up values, for mixed units that can't share an axis, or for
comparisons with text-heavy cells.

Prose says only what the page can't show: the claim, why it holds, its cost, and the
question the page asks.

## Reading cost

Readers skip collapsed text unless they go looking. Keep open everything the page asks
the reader to take in or answer: the finding, its evidence, and what they are asked to
review, decide or comment on, including a proposed plan. Keep short supporting notes
and excerpts visible. Collapse long optional material when the space and attention
saved repay its label and click. Keep the resulting disclosure controls directly
reachable; another level should reveal substantial content of its own.

The title names the page, and the lede under it states the finding. A section that
reaches a finding states it in its heading, short enough to scan in an `lf-toc`; put
qualifications in the first sentence. A `<summary>` and an option's `<strong>` do the
same. "What we learned" promises a finding and withholds it. Use a plain label only where there is no finding, as over a list, table or board
that speaks for itself. A panel's heading (`section.panel`, as on a dashboard) is
set in small capitals, which read as a region's name and not as a sentence, so name
the region there in a few words and state its finding in the panel's first line.

Write for what the user has seen: this conversation and the page so far. Introduce the
names a decision depends on, show evidence for any claim they could doubt, and drop the
story of how you got there.

The user knows the facts they gave you and reads the page against them, so one figure
that differs from theirs makes them doubt the rest. Keep each supplied fact as given,
with the measure it belongs to. A number, trend, count or consequence you work out from
them is your claim: check it against the figures it rests on, and keep those figures
beside it. Where your working contradicts a supplied fact, show both and say which the
page uses, rather than correcting theirs in place.

Use `lf-gloss` for a local term, acronym or premise the reader can open beside a
phrase. Keep citations as links and keep visible any qualification the argument rests
on.

## Composing a page

Most pages are read top to bottom and use the reading column,
`<main class="layout-column">`, where text stays within the measure and wider blocks
extend beside it. Compose the page from these:

- **Prose read in order**, such as a plan, review or decision, is plain semantic HTML.
- **Independent status tiles** are a block with `class="layout-tiles"`, whose children
  sit in equal cells. Each cell holds a metric (the theme's `.metric` entry), chart,
  table, list or log, with at most a caption; tiles of paragraphs read worse than the
  column.
- **A comparison** is a table, or native sections arranged by the page's CSS.
- **Controls beside evidence** is a playground. Aim for one coherent experience to
  read, operate and comment on. Embedded documents can isolate a demonstration, but
  also separate its navigation and interaction from the surrounding Leaf page
  (`live-samples.md`).
- **A surface the reader works at or keeps open rather than reads down**, like a mail
  client, a queue worked one item at a time, a log beside its chart, settings tuned
  against their evidence, a desktop interface the reader tunes, or a rollout dashboard
  glanced at between other work, keeps its working state in the reader's window, since a tuning pass or a glance
  doesn't scroll: each setting or status beside the evidence that judges it, and the
  decision or submission waiting on the reader. Keep the title and premise to a line
  or two, and give `main` `density-working` (`page-layout.md`, "A workspace"). A screen
  the reader works in is a workspace, whose surface fills the window from the title's
  left edge; a dashboard whose detail the reader may read on down is a
  `layout-sidebar` page with its regions side by side. Let that surface lead when it
  is the main task; supporting reading, such as the review behind a design the reader
  tunes or the full history behind a status, goes below it or in later parts on a page
  of parts (below). A document read top to bottom beside a panel kept in view, such as
  a postmortem beside its timeline, is a `layout-sidebar` page (`page-layout.md`, "A
  sidebar page").
- **Several views of one artifact** are one `lf-tabs` set. Page tabs hold project-scale
  views; a tabbed section holds local alternatives within a view. The `lf-tabs` entry says which placement makes
  which.
- **Parts of one subject that each want their own Layout**, such as a playground to try
  beside the proposal it argues for and the reasoning behind it, are a page of parts
  (`page-layout.md`, "A page of parts"). Where the views share the page's Layout and
  a header across the top, such as one shared with a site's other pages, they are page
  tabs instead.

Leaf's panel takes its own room at the window's foot, and comment markers go in the
margin or over their targets, so leave room for neither. The reader hides markers with
`o`, or the leaf's menu → Annotations → Hide annotations, to read what's under one.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none.

Write an empty `lf-toc` with a stable id. On a column page, put it in an
`aside.sidebar` directly inside the box carrying `layout-column`, near the top:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

On a sidebar page, put the
contents and a short verdict or status at the top of the `aside` (`page-layout.md`, "A sidebar page"), short enough
to fit the window, and put detailed evidence and history in the body or behind a
disclosure. Workspaces and root page tabs have their own navigation, and so does a
page of parts, whose column parts each take their own outline.

## Read the registry

Use Leaf's default styling for ordinary content, with semantic HTML from the registry's
elements and class idioms. The vendored theme supplies colours, type, spacing,
headings, tables, code and widgets. Polish a page through clearer content and hierarchy
within that treatment. Reserve page CSS for task-specific arrangement, visualization
or a particular design the user requests. An added card surface should express a
grouping or interaction the task needs; wrapping already styled elements just for
polish adds visual weight without meaning. A box page CSS makes opaque, such as a
sticky bar, paints `background: var(--lf-ground)`: the surface it stands on, which a
card or a playground's preview sets for what it holds.

When page CSS reveals controls while a container is hovered or focused, include
`:has([data-lf-control-active])` in the condition if it contains a code block.
Leaf marks that block while its floating Copy control is hovered or focused, since
Copy lives outside the block's tree. For example,
`.card:is(:hover, :focus-within, :has([data-lf-control-active])) .actions`
keeps a card's actions visible when the pointer or focus moves onto Copy.

`page-checkpoints.md`, "Page diagnostics", describes the optional source inventory
for inspecting how much CSS a page adds and where it comes from.

First read the shared author instructions of the page's packages, which can steer
which entries you pick:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`<page>/registry.json` is the vocabulary `page init` vendored. Ordinary keys are
element names or CSS selectors; `$` keys are facts shared across the layer. List the
vocabulary by purpose, then read the entries you pick, and any `$` fact you rely on, in
full:

```bash
registry="<page>/registry.json"
jq 'with_entries(select(.key | startswith("$") | not))
    | map_values(.description)' "$registry"
jq '.["lf-options"], .[".eyebrow"], .["$series"]' "$registry"
```

Before writing markup, read the author instructions for the entries you will use,
including any example you copy:

```bash
leaf page instructions <page> --use lf-options --use .eyebrow | jq -r '.author // empty'
```

The output is a JSON map from audience to text. When you or an agent you assign takes
another role a package names, such as a contract's `producer` or a `coordinator`, read
that audience's text for the same selection; `--contract` selects a data contract
directly (`packages.md`, "Package contract").

## Document scaffold

Write a complete HTML document whose head has a title and description; Leaf adds the
encoding, theme, runtime and viewport when it serves the page. Put page CSS in
`<style>` and JavaScript in `<script>` (`page-behavior.md`). Give every `lf-*` element
an explicit end tag.

The title and description represent the page outside it, in a tab, a search result or
a pasted link, so write a description that makes sense on its own.

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
language from `$languages.names`. Native `code` classes also accept the bundled
grammar's aliases, such as `language-js` and `language-sh`. Format example code with
the language's usual indentation and line breaks rather than packing several statements or fields onto one
line, and keep it working when you reformat it. Quote source verbatim when quoting it;
logs and transcripts that aren't source code stay literal and uncoloured.

For a custom horizontal scroll area, set `overflow-x: auto` and add
`class="scroll"` to that same box. Leaf contains its positioned descendants and
adds keyboard access and continuation cues when content exceeds the box. Its CSS may
change overflow at a breakpoint; Leaf measures the declared surface, never all of its
descendants. Use a bounded reading region for independently scrolling vertical content.

The theme scrolls a `<pre>` or table wider than its container and fits an image or SVG
to it, so none needs a width. In a table that scrolls sideways, prose wraps a word per
line. Put identifiers in `<code>`, which can break inside a cell, and keep the columns
to what fits at the narrowest width the page's readers use.

## Stable anchors

Give each section, major block and Leaf element a stable, meaningful `id` on the
smallest element a user would point at. A code block, table, figure or aside a user
will point at as a whole needs one too, on itself or its immediate container. Where a
wrapper holds only one child that fills it, put the id on the child.

Group a heading with its eyebrow or subtitle in `<hgroup>` and put the id on the group.
When that title starts a section with an id, the `<section>` carries the address
instead. An id a heading needs for `aria-labelledby` is not the section's address.

Threads, reading position and version comparison all find a block by its id, so a
rewritten paragraph keeps its id. A heading offers the reader a link to that address, so
a heading with no id on it, its `<hgroup>` or the section it opens offers none.
