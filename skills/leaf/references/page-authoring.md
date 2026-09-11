# Page authoring

Read this before writing or revising any version. It owns the rules every page
needs; the main skill routes Asks, live revisions, and evidence to separate
references.

- [Read the registry](#read-the-registry)
- [Document scaffold](#document-scaffold)
- [Document or workspace](#document-or-workspace)
- [Theme and vocabulary](#theme-and-vocabulary)
- [Page behavior](#page-behavior)
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
reader acts on it, and how to word the question it puts. Package-defined tags and
`$` facts join the same key list. `leaf page guidance <page>` lists the composed
guidance audiences and `leaf page guidance <page> <audience>` prints one guide;
read `author` when it is present, and the assigned audience before acting in any
other role.

## Document scaffold

Write a complete HTML document. The head contains exactly one `/theme.css` link
and one external `/leaf.js` module. Page-specific JavaScript uses inline module
blocks. Every `lf-*` element has an explicit end tag.

The title and description are what the page says it is anywhere outside itself: a
tab, a search result, a link someone pastes into a chat. Write a description that
stands alone, since whoever reads it there has none of the page around it.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>…</title>
  <meta name="description" content="…">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'none'; form-action 'none'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
  <link rel="stylesheet" href="/theme.css">
  <script type="module" src="/leaf.js"></script>
</head>
<body>
  <main>…</main>
</body>
</html>
```

## Document or workspace

Use ordinary document flow for material the reader takes in sequence. Use a
workspace when the task needs regions visible together, such as controls beside a
preview or a queue beside its detail. Both use the same widgets, Asks, comments,
and revisions; packages supply the vocabulary and guidance for the task.

For a workspace, make `lf-workspace` the sole content element directly inside
`main`, with the page title in its optional direct native `header`. Its body is
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

## Theme and vocabulary

Write semantic HTML and use the class idioms the registry lists under `$idioms`,
where each one comes with the markup it is written as. The vendored theme owns
palette, type, spacing, headings, tables, code, and widget presentation. Use a
page-local `<style>` only for presentation unique to this page.

Widget attributes carry scalars; children carry prose; a titled compound member uses a
leading `<strong>`. A data-bodied widget such as `lf-code` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text. The
registry is the only widget vocabulary.

The runtime injects the status banner, thread panel, Versions menu, keyboard
shortcuts, live-leaves tray, and active-asks tray. Authors declare reader asks
through the registry's Ask sources and surfaces, but do not duplicate that
chrome or maintain a second list of it in the page.

Keep content inside its document column or pane. The theme scrolls a `<pre>` or a table
that runs wider than its container and fits an image or SVG to it, so none of them needs a
width. A table that scrolls has every column at its longest unbreakable run, and
the browser gate refuses one that scrolls with a cell in it wrapped: put an
identifier in `<code>`, where it breaks inside its cell, rather than bare, where
it holds its column and squeezes the prose beside it, and keep the columns to
what the measure holds. Widgets whose element declaration names a wide shape size
themselves; fix a diagram that is too wide in its source rather than pinning a
page width.

## Page behavior

Write page-specific behavior in one or more `<script type="module">` blocks. Leaf
stores the code in the same immutable revision as the markup it controls and hashes
its exact contents into the served policy. Standard browser APIs are available; code
that integrates with Leaf may import the public `/runtime/widget-api.js` module and
listen to public widget events such as `lf-playground-change`.

Use a package when behavior, styling, or vocabulary is reused across pages. A one-page
explorer or playground keeps its code in the page. The one external script element
remains `/leaf.js`; import any vendored dependencies from an inline module. Leaf
refuses classic scripts, event-handler attributes, and `javascript:` URLs so every
executable source remains an explicit module block.

Typed data and media remain inert inputs. Read them through their Leaf/browser APIs;
do not turn their contents into source code or markup.

## Stable anchors

Give each section, major block, and Leaf element a stable, meaningful `id` at the
tightest semantic boundary a reader can distinguish. Where a sole child fills a
transparent wrapper, let the child carry the pair's one id.
Put a titled section's public id on the `<section>`, not on its heading just for
`lf-toc`: the heading supplies the link text, while the section fragment arrives at
the complete title, including an eyebrow. A heading may still need its own id for an
internal relationship such as `aria-labelledby`; that id is not the section's public
address.
Threads and reading position attach to those ids across versions, and so does a
reader comparing this version with an earlier one: the id is how the comparison
finds what the block said before, so a rewritten paragraph keeps the id it had.
Stay out of the `lf-` prefix: it is the runtime's
namespace for ids and for classes alike, and `data-lf-` is the same for
attributes. `version check` refuses all three, including a name the runtime does
not write today — the namespace is reserved, not the list of names in it.

A code block, table, figure, or aside that a reader will point at as a whole also
needs a tight id, either on itself or on its immediate semantic container.

## Reading cost

Open words are read; collapsed words are there when the reader wants them. What
stands open in the column is what the reader has to take from the page. History,
method, source excerpts, exhaustive support, transcripts, and raw output are
backing by default and go under `<details>`. Collapsed words stay quotable, and
the runtime opens the disclosure when a comment or a walk lands inside one. An
Ask and the evidence it turns on never collapse.

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
a diagram. Use a table when the reader compares the same dimensions across items;
use `lf-compare` for a few alternatives read as wholes, and `lf-options` when the
reader must choose among them. A headline measurement is a metric, and a pattern
across measurements is a chart. Movable things form a board. Use images only when
they carry information. The prose beside a shape says only what the shape cannot.
What is left for prose is the claim, the reason it holds, and the question the page
is asking. A few sentences hold all three. A section that runs longer is carrying
either a structure with a shape of its own or backing that belongs under
`<details>`.

Write for what the reader has seen, which is this conversation and the page so
far. Introduce the names a decision depends on, put evidence on the page for a
claim they could doubt, and drop the journey once the conclusion replaces it.

## Pre-handover review

The main skill's handoff ceremony decides which page takes this review: a
finished record before its URL first reaches the user, and a quick page before
the stamp that turns it into one. Every source activation already runs the
deterministic markup check; this review adds the browser gate and a reading:

```bash
leaf version check <page> --render
```

It loads the page in both color schemes and checks runtime errors, widget size,
overflow, diagrams, selectable words, print output, replay-safe state, and
action idempotence. Fix every failure; a screenshot is not a substitute.

Then read the page as the user will. Take the headings on their own first, and
check that none of them promises a finding it does not give. Confirm that
referents are introduced, claims have evidence, decisions have controls, diagrams
add information, links work, and that everything standing open in the column is
there because the reader needs it.

For a page with Asks, start at the top and press `a` through them. At each
arrival, confirm that the question, shared premise, alternatives, and evidence
that distinguishes them are visible together, the displayed numbers match the
available actions, and the next press of `a` reaches the next open Ask while the
complete page remains visible.
