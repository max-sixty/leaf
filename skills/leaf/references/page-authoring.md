# Page authoring

## Develop the content

Show the page's subject at work in a concrete case. For a recommendation, construct
the proposed result in use, with the content it operates on and the outcome the
change would produce. Research notes supply facts and constraints; develop this
material before composing the explanation. Make reasonable illustrative choices to
complete the case, labeling invented content and untested behavior as proposed.

For example, an operator needs to locate failed imports in the original file. A
proposed report groups them by cause and keeps their original row numbers:

```html
<lf-sample id="import-report" label="Proposed report — fictional data">
  <h3>Missing currency — 12 rows</h3>
  <p>Three representative rows shown.</p>
  <table>
    <thead>
      <tr>
        <th>Original row</th>
        <th>Supplier</th>
        <th>Amount</th>
        <th>Currency</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>8</td>
        <td>Northwind</td>
        <td>29.00</td>
        <td>Missing</td>
      </tr>
      <tr>
        <td>19</td>
        <td>Acme</td>
        <td>15.50</td>
        <td>Missing</td>
      </tr>
      <tr>
        <td>27</td>
        <td>Northwind</td>
        <td>8.00</td>
        <td>Missing</td>
      </tr>
    </tbody>
  </table>
</lf-sample>
```

The reader can inspect the proposed grouping and locate its records. The missing
currencies remain visible: grouping the failures does not establish the correction.
Explain why this report would help and what remains untested beside the sample.

Choose the material by what is being judged. Draw relationships for a mechanism,
use a shared scale when comparing quantities by size, show arrangements for a layout,
and show behavior through the actual or proposed subject before and after an action.
For an interface, depict its content, controls and arrangement, showing where the
action happens and what changes. Make behavior operable when trying it reveals more
than seeing those states together. A wording choice can show the actual candidate
sentences; a reasoning question can present the
argument directly. These are all ways to let the reader examine the work itself.

Compose the explanation around the result: the claim, reason, cost and limits
the material cannot show. Select from the research for the current question
and remove descriptions the example makes unnecessary. Let using the material
determine the page's arrangement and sequence.

`authoring-evidence.md` owns captures, drawings, charts, recordings and code
excerpts; `live-samples.md` owns operable Leaf examples.
A demonstration on the page illustrates a proposal; it does not implement that change
in the product being discussed.

An author assigned to construct material builds it directly and returns candidate
files to the parent. `SKILL.md`’s operating workflow belongs to the session talking
with the user, which composes and publishes the page.

## Reading cost

Give the main result and the material supporting it the most attention and space.
Write headings that tell a scanning reader what each part establishes. Use the
user's context to leave out explanations and background they already have.

Keep essential content visible. Collapse optional detail when it saves enough reading
to justify finding and opening it; short qualifications and evidence needed for a
judgment belong beside that judgment. Keep disclosure controls reachable, and make
nested disclosures reveal substantial content of their own. Leaf opens a disclosure
when a comment lands inside it.

Preserve the meaning and units of facts you use. Check derived quantities against their
inputs, and keep uncertainty and evidence limits beside the claims they qualify. When
your findings contradict the user's supplied facts, show the discrepancy explicitly.
Use links for citations and `lf-gloss` for unfamiliar terms the reader can open locally.

## Composing a page

Arrange the material so the reader can do the task with little navigation or memory.
Put alternatives at a comparable scale, controls beside the results they change, and
an explanation beside the evidence it interprets. Use the registry's semantic HTML,
widgets and class idioms for those roles.

Choose the Layout after the content: `layout-column` supports a sequence of views,
including wide diagrams and comparisons; `layout-sidebar` keeps context beside a
working region; `layout-workspace` lets the user work within one screen. A Layout is a
class on `main`; a page can also use its own grid or flex arrangement. `page-layout.md`
owns their geometry, bounds, tiles, and pages with tabs or parts.

Leaf supplies the theme and its own panel and comment margins. Use page CSS for the
task's arrangement or visualization, or a design the user requests. Let the content
supply the hierarchy; give a card surface a grouping or interaction to express.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none. The outline should be reachable from the top of the page on a desktop and while
the document scrolls, and in a narrow window it comes before the main reading.

Write an empty `lf-toc` with a stable id. On a column page, put it in an
`aside.sidebar` directly inside the box carrying `layout-column`, near the top:

```html
<aside class="sidebar" id="contents-sidebar">
  <lf-toc id="contents"></lf-toc>
</aside>
```

Leaf shows it in the desktop margin when there is room, and behind an **On this page**
disclosure in the page's flow when there isn't. The same links remain available by
keyboard and touch; printing shows the complete outline. On a sidebar page, put the
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
polish adds visual weight without meaning.

`page-checkpoints.md`, "Page diagnostics", describes the optional source inventory
for inspecting how much CSS a page adds and where it comes from.

First read the shared author instructions of the page's packages, which can steer
which entries you pick:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`<page>/registry.json` is the vocabulary `page init` vendored, and a
`page/registry.json` the page writes adds entries to it; an element entry there
replaces the layer's entry for that tag (`page-behavior.md`). Ordinary keys are
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
escaped text in a `<pre>`. Escape `&` first, then `<` and `>`; any other order can
silently decode entity text.

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
to it, so none needs a width. It scrolls them sideways only: one given just a
`max-height` clips what runs past it, so add `overflow-y: auto` to let it scroll down
too. In a table that scrolls sideways, prose wraps a word per
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
