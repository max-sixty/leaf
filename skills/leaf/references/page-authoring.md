# Page authoring

This reference covers what every page needs. Choices only some pages make have their
own references, named where each choice comes up.

## Show the subject

Before writing a view's words, decide what it shows. Ask what the user would otherwise
have to picture from a description, and put that thing on the page in its own form:

- An existing interface is a screenshot, cropped or marked so the eye lands on the
  point, with crops cutting through background rather than text. A visual change
  between two versions is an `lf-shot` before-and-after pair, and captures that vary
  along other axes go in a table of captures (`authoring-evidence.md`, "Source files
  and media").
- A behavior, such as an interaction, a motion or a process over time, runs: in a live
  sample the user operates (`live-samples.md`), or in a page module that draws it with
  controls to pause and scrub, so each moment stays readable and commentable.
- A proposal or mechanism nothing can show yet is drawn: where things sit, what
  contains, calls or feeds what, how a state changes, today beside the proposal, and
  alternatives in one frame at one scale.
- Numbers whose shape is the point, such as a trend, a ranking or groups on one scale,
  are an `lf-chart`, even when they compare the same measures across items. Label the
  values the argument cites, and put exact values in a table in `<details>` below it
  when readers need them.
- Wording the user judges, such as code, a command or a message, is shown as the text
  itself. When the point is what code does, such as what it draws or which rule wins,
  show that effect in one of the forms above, with the code beside it.

Pages that decide, plan or review show their subject the same way: a work item that
fixes a visible fault shows the fault, and an ask's options show what each answer gives
the user (`authoring-asks.md`). A table or list whose rows name places, sizes or
connections should be a drawing.

Use a table for looking up values, for mixed units that can't share an axis, or for
comparisons with text-heavy cells. Use native sections for a few alternatives read as
wholes, and `lf-options` when the user must choose among them. Use images only when
they carry information. `authoring-evidence.md` says which element draws each kind of
evidence, and how to draw a figure of your own.

Prose says only what the page can't show: the claim, why it holds, its cost, and the
question the page asks. That takes a few sentences. A longer section is carrying
something the page should show, or backing that belongs in `<details>`.

## Reading cost

Readers skip collapsed text unless they go looking. Keep open everything the page asks
the reader to take in or answer: the finding, its evidence, and what they are asked to
review, decide or comment on, including a proposed plan. Collapse what they can skip
and still do that, such as history, method, source excerpts, transcripts and raw
output. Leaf opens a disclosure when a comment lands inside it.

The title names the page, and the lede under it states the finding. A section that
reaches a finding states it in its heading, short enough to scan in an `lf-toc`; put
qualifications in the first sentence. A `<summary>` and an option's `<strong>` do the
same. "Why the prefixes matter" and "What we learned" promise a finding and withhold
it. Use a plain label only where there is no finding, as over a list, table or board
that speaks for itself.

Write for what the user has seen: this conversation and the page so far. Introduce the
names a decision depends on, show evidence for any claim they could doubt, and drop the
story of how you got there.

Use `lf-gloss` for a local term, acronym or premise the reader can open beside a
phrase. Keep citations as links and keep visible any qualification the argument rests
on.

## Composing a page

Most pages use the reading column, `<main class="layout-column">`, where text stays
within the measure and wider blocks extend beside it. Without a Layout class, the page
lays out as plain HTML. A diagram or board declares its width; `data-width` asks for
one on other blocks, such as a wide table (`page-layout.md`, "Bounds and widths").
Compose the page from these:

- **Prose read in order**, such as a plan, review or decision, is plain semantic HTML.
- **Independent status tiles** are a block with `class="layout-tiles"`, whose children
  sit in equal cells. Each cell holds a metric, chart, table, list or log, with at most
  a caption; tiles of paragraphs read worse than the column.
- **A comparison** is a table, or native sections arranged by the page's CSS.
- **Controls beside evidence** is a playground.
- **A screen the reader works in rather than scrolls**, like a mail client, a queue
  worked one item at a time, or a log beside its chart, is a workspace
  (`page-layout.md`, "A workspace"). A document read top to bottom beside a panel kept
  in view, such as a postmortem beside its timeline, is a `layout-sidebar` page
  (`page-layout.md`, "A sidebar page").
- **Several views of one artifact** are one `lf-tabs` set. Page tabs hold project-scale
  views that share one history, Threads panel and set of asks; a tabbed section holds
  local alternatives within a view. The `lf-tabs` entry says which placement makes
  which.

A page can grow without changing its Layout: a report that gains live status gains a
row of tiles. Leaf's banner and bottom bar take their own space, and comment markers go
in the margin or over their targets, so leave room for neither.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none. The outline should be reachable from the top of the page on a desktop and while
the document scrolls, and in a narrow window it comes before the main reading.

Write an empty `lf-toc` with a stable id. On a column page, put it in an
`aside.sidebar` directly inside `main`, near the top:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

Leaf shows it in the desktop margin when there is room, and as an open outline in the
page's flow in a narrow window. On a sidebar page, put the outline and a short verdict
or status at the top of the `aside` (`page-layout.md`, "A sidebar page"), short enough
to fit the window. Workspaces and root page tabs have their own navigation.

## Read the registry

Write semantic HTML using the registry's elements and class idioms. The vendored theme
styles colours, type, spacing, headings, tables, code and widgets; use a page `<style>`
only for presentation unique to this page.

First read the shared author instructions of the page's packages, which can steer
which entries you pick:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`<page>/registry.json` is the vocabulary `page init` vendored, and a
`page/registry.json` the page writes adds to it (`page-behavior.md`). Ordinary keys are
element names or CSS selectors; `$` keys are facts shared across the layer. List the
vocabulary by purpose, then read the entries you pick, and any `$` fact you rely on, in
full:

```bash
registry="<page>/registry.json"
jq 'with_entries(select(.key | startswith("$") | not))
    | map_values(.description)' "$registry"
jq '.["lf-options"], .[".eyebrow"], .["$series"]' "$registry"
```

`description` says what an entry is for and when it helps; the schema and `x-example`
give its form; `x-instructions` gives choices and obligations the schema can't express.

Before writing markup, read the author instructions for the entries you will use,
including any example you copy:

```bash
leaf page instructions <page> --use lf-options --use .eyebrow | jq -r '.author // empty'
```

The output is a JSON map from audience to text. It includes the packages' shared
instructions, the named entries' instructions, and those of the elements and contracts
their examples use. When you or an agent you assign takes another role, such as a
data producer, read that audience's text for the same selection; `--contract` selects
a data contract directly (`packages.md`, "Package contract").

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
  <meta name="description" content="…">
</head>
<body>
  <main class="layout-column">…</main>
</body>
</html>
```

## Markup

Widget attributes carry scalars and children carry prose; a titled member of a compound
widget starts with a `<strong>`. A widget whose body is data, such as `lf-code`, holds
escaped text in a `<pre>`. Escape `&` first, then `<` and `>`; any other order can
silently decode entity text.

Format filenames and paths as inline code, and link a file that has a known
destination.

Show source snippets as `<pre><code class="language-javascript">…</code></pre>`, or as
`lf-code language="javascript"` for a line-numbered walkthrough, naming the actual
language from `$languages.names`. Format example code with the language's usual
indentation and line breaks rather than packing several statements or fields onto one
line, and keep it working when you reformat it. Quote source verbatim when quoting it;
logs and transcripts that aren't source code stay literal and uncoloured.

The theme scrolls a `<pre>` or table wider than its container and fits an image or SVG
to it, so none needs a width. In a table that scrolls sideways, prose wraps a word per
line, and the render check reports each width from a 360px phone up where that happens.
Put identifiers in `<code>`, which can break inside a cell, and keep the columns to
what fits at the narrowest width the page's readers use. Keep a diagram's detail rather
than shrinking it to fit the column.

## Stable anchors

Give each section, major block and Leaf element a stable, meaningful `id` on the
smallest element a user would point at. A code block, table, figure or aside a user
will point at as a whole needs one too, on itself or its immediate container. Where a
wrapper holds only one child that fills it, put the id on the child.

Group a heading with its eyebrow or subtitle in `<hgroup>` and put the id on the group.
When that title starts a section with an id, the `<section>` carries the address
instead. An id a heading needs for `aria-labelledby` is not the section's address.

Threads, reading position and version comparison all find a block by its id, so a
rewritten paragraph keeps its id.

Don't start an id or class with `lf-`, or an attribute with `data-lf-`: Leaf reserves
those prefixes, and `page check` refuses any name in them. It also refuses an id of
exactly eight lowercase hex digits, such as `4f9e2a1c`, the shape of the message ids
the event log creates.
