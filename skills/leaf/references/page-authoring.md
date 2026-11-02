# Page authoring

## Develop the work

Choose the material from what the reader needs to understand or decide about the
subject. The document you write presents that subject; being asked to draft or
revise it does not make its wording the subject of the decision.

For a recommendation that changes behavior, show the result as it is and as it
would be, filled in with a representative case's content: its inputs, relevant state and result.
A description of what the result should contain, or of how to test it, is a
specification, not the result. For a proposed import report:

<example>
<bad reason="Specifies the report instead of showing it.">

Bad: "Group failed imports by cause, keeping their source rows."

</bad>
<good reason="Shows a proposed report with illustrative content.">

Good: "Missing currency — 3 imports: rows 8, 19, 27."

</good>
</example>

The result can be an experience someone uses or a mechanism that determines an
outcome. Develop enough of it to judge the benefit and cost you recommend. Make an
interaction operable when trying it reveals more than seeing its states together.

Use real material where available. Fill gaps needed to demonstrate a proposal with
plausible fictional content, clearly labeled as illustrative. This lets the reader
judge a design before it is implemented or tested; claims about real behavior
still require evidence. Keep the distinction visible beside the demonstration.
`authoring-evidence.md` owns evidence and its presentation; `live-samples.md` owns
operable Leaf examples.

Use a drawing when its arrangement, connections or scale make the subject easier
to understand.

Compose the page from that material. Explain the conclusion, reasons, costs and
limits beside the result they concern, and remove descriptions the result makes
unnecessary. Let the reader's task determine how much of each finding to develop.

## Reading cost

Give the main result and the material supporting it the most attention and space.
Write headings that tell a scanning reader what each part establishes. Use the
user's context to leave out explanations and background they already have.

A panel's heading (`section.panel`, as on a dashboard) is set in small capitals,
which read as a region's name and not as a sentence, so name the region there in a
few words and state its finding in the panel's first line.

Keep essential content visible. Collapse optional detail when it saves enough reading
to justify finding and opening it; short qualifications and evidence needed for a
judgment belong beside that judgment. Keep disclosure controls reachable, and make
nested disclosures reveal substantial content of their own.

Preserve the meaning and units of facts you use. Check derived quantities against their
inputs, and keep uncertainty and evidence limits beside the claims they qualify. When
your findings contradict the user's supplied facts, show the discrepancy explicitly.
Use `lf-gloss` for unfamiliar terms the reader can open locally.

Link each pull request, issue, commit, URL, and file or source line with a known
destination in every section, decision and reply that names it. The user reaches each
of those on its own, from the contents or On me, and opens what it names from there to
check it.

## Composing a page

Arrange the material so the reader can do the task with little navigation or memory.
Put alternatives at a comparable scale, controls beside the results they change, and
an explanation beside the evidence it interprets. Use the registry's semantic HTML,
widgets and class idioms for those roles, including the theme's `.metric` entry
for a metric.

Choose the Layout after the content: `layout-column` supports a sequence of views,
including wide diagrams and comparisons; `layout-sidebar` keeps context beside a
working region; `layout-workspace` lets the user work within one screen. A Layout is a
class on `main`. `page-layout.md` owns their geometry, custom arrangements, bounds,
tiles, and pages with tabs or parts.

A dashboard the reader glances at keeps its working state in the first window, since
a glance doesn't scroll.
Keep each relevant setting or status, its evidence and the reader's next action together
in that window, and spend as little of it as the page allows on the title, the premise
and supporting reading. By default that means a title and premise of a line or two,
`density-working` on `main` (`page-layout.md`, "A workspace"), and the working surface
first, with supporting reading below it or in later parts. A workspace fills the window
from the title's left edge; a dashboard whose detail the reader may read on down is
usually a `layout-sidebar` page with its regions side by side, so they share the window
rather than stacking past it.

Comment markers appear in the margin or over their targets; the reader hides them with
`o`, or the leaf's menu → Annotations → Hide annotations, to read what's under one.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none.

Write an empty `lf-toc` with a stable id in the authored sidebar track. A reading
page composes the route and its document as siblings:

```html
<main class="layout-sidebar">
  <aside id="contents-sidebar">
    <div class="layout-track"><lf-toc id="contents"></lf-toc></div>
  </aside>
  <article id="document" class="layout-column">…</article>
</main>
```

The browser places that route before JavaScript runs and wraps it with the document
when narrow. Keep contents and a short verdict or status in the track, and put detailed
evidence and history in the body or behind a disclosure. See `page-layout.md`,
"A sidebar page", for the shared composition and width contract.

Workspaces and root page tabs have their own navigation, and so does a
page of parts, whose column parts each take their own outline.

## Style the page

A new page takes Leaf's reading theme, which styles semantic HTML (headings, prose,
tables, code) in both colour schemes and adds the class idioms, such as `.callout`, so
a page of ordinary content needs no CSS of its own: polish it through clearer content
and hierarchy within that treatment. Where the task calls for a design of its own,
such as an instrument, an arrangement, or a look the user asks for, write it in
ordinary CSS. A page whose design is wholly its own, such as an existing site, a
mockup or a page the user brings, takes no theme instead (`leaf page init <page>
--no-theme`), so it starts from the browser's defaults and none of the theme shows
through its rules; Leaf's widgets, threads and panel keep their own faces either way.
`leaf theme list` names the themes a page can take (`package-themes.md`, "Personal
themes"). Page CSS stands above every theme rule
without `!important` or extra specificity, and an element rule of its own, such as
`table`, `code` or `blockquote`, replaces only the properties it names, so set the rest
too wherever the theme's would show through. Wrapping elements the theme already
styles in a card adds visual weight without meaning; give a card a grouping or
interaction to express.

Restyle the whole page through the theme's tokens on `:root` rather than rules on
`body`, so Leaf's widgets, threads and panel follow the page: `--paper` and `--ink` for
ground and text, `--card`, `--muted`, `--rule` and `--accent`, and the faces
`--serif` for prose, `--sans` for labels and controls and `--mono` for code
(`package-themes.md`, "Theme colors", lists every input). A palette made for one scheme
also sets `color-scheme: light` or `dark`, so the tokens it leaves alone take that
scheme's values. `--col` sets the reading column's width, and the spacing steps
`--sp-1` to `--sp-5` tighten under `density-working`.

`body` is Leaf's: it holds the one `main`, which is the page, and Leaf's own interface,
and pads its foot by `--lf-foot-room` so the page's end scrolls clear of the panel. Put
the page's grid and header on or inside `main`, and its ground in `--paper`; a page that
takes no theme paints its ground on `html` and names it in `--lf-ground`, since `body`
is a container, which keeps its own background off the window below a short page. A
reset that zeroes
`body`'s padding, or an app shell whose own box scrolls, puts
`padding-bottom: var(--lf-foot-room)` on whatever scrolls. A box page CSS makes opaque,
such as a sticky bar, uses `background: var(--lf-ground)` to match its containing
surface; cards and playground previews set this property for their contents.
`page-layout.md`, "Page CSS and Leaf's controls", says how page CSS meets Leaf's own
controls.

When page CSS reveals controls while a container is hovered or focused, include
`:has([data-lf-control-active])` in the condition if it contains a code block.
Leaf marks that block while its floating Copy control is hovered or focused, since
Copy lives outside the block's tree. For example,
`.card:is(:hover, :focus-within, :has([data-lf-control-active])) .actions`
keeps a card's actions visible when the pointer or focus moves onto Copy.

`page-checkpoints.md`, "Page diagnostics", describes the optional source inventory
for inspecting how much CSS a page adds and where it comes from.

## Read the registry

Use the registry's elements and class idioms for what they record or do. First read
the shared author instructions of the page's packages, which can steer
which entries you pick:

```bash
leaf page instructions <page> | jq -r '.author // empty'
```

`leaf page vocabulary <page>` prints the vocabulary the page is written in. Ordinary
keys are element names or CSS selectors; `$` keys are facts shared across the layer.
List the vocabulary by purpose, then read the entries you pick, and any `$` fact you
rely on, in full:

```bash
leaf page vocabulary <page> | jq 'with_entries(select(.key | startswith("$") | not))
    | map_values(.description)'
leaf page vocabulary <page> | jq '.["lf-options"], .[".eyebrow"], .["$series"]'
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

Format filenames and paths as inline code.

Show source snippets as `<pre><code class="language-javascript">…</code></pre>`, or as
`lf-code language="javascript"` for a line-numbered walkthrough, naming the actual
language from `$languages.names`. Native `code` classes also accept the bundled
grammar's aliases, such as `language-js` and `language-sh`. Format example code with
the language's usual indentation and line breaks rather than packing several statements or fields onto one
line, and keep it working when you reformat it. Quote source verbatim when quoting it;
logs and transcripts that aren't source code stay literal and uncoloured.

Readers read Markdown rendered, so show a passage of Markdown you quote, such as a rule
from a doc or a pull request's description, in `lf-text-document preview="markdown"`
with its exact text in the `<pre>` (`authoring-evidence.md`, "Source files and media").
Leaf renders it, and its Source tab shows the exact Markdown. Where Markdown syntax is
itself the subject, show it literally in `<pre><code>`.

For a custom horizontal scroll area, set `overflow-x: auto` and add
`class="scroll"` to that same box. Leaf contains its positioned descendants and
adds keyboard access and continuation cues when content exceeds the box. Its CSS may
change overflow at a breakpoint; Leaf measures the declared surface, never all of its
descendants. For a box that scrolls vertically, see `page-layout.md`, "Bounds and widths".
A box that only clips, such as a card with rounded corners, takes `overflow: clip`.
`overflow: hidden` makes it a scroller Leaf doesn't know, so a tab strip or other sticky
header inside it can drop below its place and cover the content under it.

Leaf scrolls a `<pre>` or table wider than its container and fits an image or SVG to
it, whatever theme the page takes, so none needs a width. A table's columns size to
their content, so leave its cells' widths and wrapping to Leaf too. Text that can't break, such as a bare
identifier or a cell kept on one line, holds its column at its full length, and once
the table scrolls sideways, prose in the other columns wraps a word per line. Put
identifiers in `<code>`, which can break inside a cell, and keep the columns to what
fits at the narrowest width the page's readers use. Write each row's name as its
first cell, a `<th scope="row">`, and the names stay in view while the other columns
scroll.

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
