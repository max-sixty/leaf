# Page authoring

## Show the subject

Before writing a view's words, decide what it shows. Ask what the user would otherwise
have to picture or piece together from a description, and put that thing on the page
in its own form:

- An existing interface is a screenshot, cropped or marked so the eye lands on the
  point, and a visual change between two versions is a before-and-after pair of
  captures (`authoring-evidence.md`, "Interactive and visual evidence").
- A behavior, such as an interaction, a motion or a process over time, runs: in a live
  sample the user operates (`live-samples.md`), or as previews the reader plays and
  scrubs together. An order of events between actors is a timeline the reader steps
  through.
- A proposal or mechanism nothing can show yet is drawn: where things sit, what
  contains, calls or feeds what, how a state changes, today beside the proposal, and
  alternatives in one frame at one scale.
- Numbers whose shape is the point, such as a trend, a ranking or groups on one scale,
  are a chart, even when they compare the same measures across items. Label the
  values the argument cites, and put exact values in a table below it when readers
  need them.
- Items the user reads one at a time and compares on the same facts, such as settings,
  files or test results, are a table: a row per item, a column per fact, and rows
  grouped or sorted by the fact they scan first. Values the user looks up, and
  measures in units that can't share an axis, go in a table too.
- Wording the user judges, such as code, a command or a message, is shown as the text
  itself. When the point is what code does, such as what it draws or which rule wins,
  show that effect in one of the forms above, with the code beside it.

The page's vocabulary provides most of these forms as widgets whose entries say what
each shows ("Read the registry"). Use the one it offers rather than building the form
yourself, and where the page has none, select the package that adds it
(`leaf package list`).

A drawing or chart makes its point through its geometry: where its marks sit, their
sizes, and what contains or links them. Add one where that geometry makes a
relationship or pattern the argument rests on easier to see than the words or a table
would. Names sorted into a box per group show the grouping no more plainly than a table
grouped the same way, and leave out the facts the table gives beside each name. A mark
per counted item shows only the count, and boxes holding sentences show only the
sentences. When the user has nothing to picture, as when they weigh a refactor's reasons
and cost, leave the case in words and draw nothing.

`authoring-evidence.md` says how to present each kind of evidence, and how to draw a
figure of your own.

## Show what a claim rests on

A claim the page makes about the work, such as a count, a cause, what code does or
what a change changes, rests on material you read: the cases behind the count, the
records of what happened, the code, the diff. Put that material on the page with the
claim, quoted rather than retold, so the user can see what the claim means and check it
without asking you or leaving the page. They often see in it what your summary left
out. Quote a rule or other passage the claim turns on whole, conditions included, and
excerpt a log or a diff to the lines that show the claim.

How long the material is decides where it goes, not whether it goes on the page. The
case or the few lines that show the claim most plainly stand beside it, and the rest,
such as every case behind a count or a whole diff, stays on the page; "Reading cost"
says when to collapse it. A link to where the material lives goes beside the material
rather than in its place, except where the reader has no reason to check the claim,
as with a fact they already hold or a status they take on trust, such as a passing CI
run. Where the cases are too many, too large or private to show, show those the claim
turns on and say how to reach the rest.

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
judge a design before it is implemented or tested, while a claim about real behavior
rests on real material ("Show what a claim rests on"). Keep the distinction visible
beside the demonstration. `authoring-evidence.md` says how to present each kind of
evidence; `live-samples.md` owns operable Leaf examples.

Compose the page from that material. Explain the conclusion, reasons, costs and
limits beside the result they concern, and remove descriptions the result makes
unnecessary. Let the reader's task determine how much of each finding to develop.

## Reading cost

Give the main result and the material supporting it the most attention and space.
Write headings that tell a scanning reader what each part establishes. Use the
user's context to leave out explanations and background they already have.

A panel's heading (`section.lf-panel`, as on a dashboard) is set in small capitals,
which read as a region's name and not as a sentence, so name the region there in a
few words and state its finding in the panel's first line.

Keep essential content visible. Collapse optional detail when it saves enough reading
to justify finding and opening it; short qualifications and evidence needed for a
judgment belong beside that judgment. Keep disclosure controls reachable, and make
nested disclosures reveal substantial content of their own.

Preserve the meaning and units of facts you use. Check derived quantities against their
inputs, and keep uncertainty and evidence limits beside the claims they qualify. When
your findings contradict the user's supplied facts, show the discrepancy explicitly.
Explain an unfamiliar term where the reader meets it, in a gloss they can open beside
the phrase without leaving the sentence.

Link each pull request, issue, commit, URL, and file or source line with a known
destination in every section, decision and reply that names it. The user reaches each
of those on its own, from the contents or On Me, and opens what it names from there to
check it. A fragment link to an id on the page, such as `<a href="#decision">`, shows
the reader where it points while they point at or focus it: the place's name and first
lines, a question's answer, and the threads about it.

## Composing a page

Arrange the material so the reader can do the task with little navigation or memory.
Put alternatives at a comparable scale, controls beside the results they change, and
an explanation beside the evidence it interprets. Use the registry's semantic HTML,
widgets and class idioms for those roles, including the `.lf-metric` entry
for a metric. Arrange an experiment's results so each variant's effect against its
baseline reads without arithmetic, and show what each variant changed beside its
effect.

Choose the Layout after the content: `layout-column` supports a sequence of views,
including wide diagrams and comparisons; `layout-sidebar` keeps context beside a
working region; `layout-workspace` lets the user work within one screen. A Layout is a
class on `main`. `page-layout.md` owns their geometry, custom arrangements, bounds,
tiles, and pages with tabs or parts. Use a workspace when the page's whole task
happens in one view whose height changes as the user works, such as a stack of cards
taken one at a time. When that view is part of a report, keep it in the report's flow.

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
`g H`, or the leaf's menu → Annotations → Hide annotations, to read what's under one.

## Contents navigation

Give a long scrolling document a contents outline so the reader can move between
sections and see where they are; a document short enough to take in at a glance needs
none.

Write the contents outline in the authored sidebar track, as its entry says. A reading
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
when narrow. Beside the body the map stands open as an outline, or, where the page
narrows its sidebar, rests as its spine, whose labels show over the page when the
reader points at it. Put a verdict or status the reader should see at once at the top of the
body, and detailed evidence and history in the body or behind a disclosure. See
`page-layout.md`, "A sidebar page", for the shared composition, the spine and the width
contract.

Workspaces and root page tabs have their own navigation, and so does a
page of parts, whose column parts each take their own outline.

## Style the page

Leaf's reading theme, the `reading` package a page selects (the main skill's "Author
the page"), styles semantic HTML (headings, prose,
tables, code, controls) in both colour schemes, and Leaf draws its class idioms, such
as `.lf-callout`, on every page, so a page of ordinary content needs no CSS of its
own: polish it through clearer content and hierarchy within that treatment. Where the
task calls for a design of its own, such as an instrument, an arrangement, or a look
the user asks for, write it in ordinary CSS. A page whose design is wholly its own, such as an existing site, a
mockup or a page the user brings, selects no theme instead, leaving `reading` out of
its packages, so it starts from the browser's defaults, its tables, code blocks and
controls included, and none of the theme shows through its rules; Leaf's widgets,
idioms, threads and panel keep their own faces either way.
`leaf package list` names the other themes a page can select (`package-themes.md`, "A
page's theme"). Page CSS stands above every theme rule
without `!important` or extra specificity, and an element rule of its own, such as
`table`, `code` or `blockquote`, replaces only the properties it names, so set the rest
too wherever the theme's would show through. Wrapping elements the theme already
styles in a card adds visual weight without meaning; give a card a grouping or
interaction to express.

On a themed page, wrap content that has its own design in a box that sets
`--lf-reading-face: initial`. The reading face then stays out of the box, and the
controls in it keep the browser's look, as on a page that selects no theme
(`package-themes.md`, "A page's theme").

Restyle the whole page through the theme's tokens on `:root` rather than rules on
`body`, so Leaf's widgets, threads and panel follow the page. Three colours carry a
palette: `--lf-paper` for the ground, `--lf-ink` for text and `--lf-accent` for
links. Leaf steps the neutral colours of every surface from the first two,
and the page's own rules read them too: `--lf-card`, `--lf-field`, `--lf-muted`,
`--lf-rule` and `--lf-border`. The faces are `--lf-serif` for prose, `--lf-sans` for
labels and controls and `--lf-mono` for code, and `--lf-r` sets every corner
(`package-themes.md`, "Theme tokens", lists every token). A palette made for one
scheme also sets `color-scheme: light` or `dark`, so the tokens it leaves alone take
that scheme's values. `--lf-col` sets the reading column's width, and the spacing
steps `--lf-sp-1` to `--lf-sp-5` tighten under `density-working`.

The page is `body`. One `main` directly inside it holds the page's content, its title
included, and carries its Layout. Site furniture around that content, such as a
site-wide header, navigation or footer, can stand beside `main`, where comments,
revisions and checks cover it as they cover `main`. `page-layout.md`, "Layouts", says
how to lay out what stands beside it.

Leaf pads `body`'s head by `--lf-head-room`, the phone's status bar. Leaf's panel
stands over the page's foot and takes no room, so lay the page out in the whole
window. Set the page's ground in
`--lf-paper`, which the theme paints the window in. A page that takes no theme
paints its own ground on `html`, since `body` is a container, which keeps its own
background off the window below a short page. It also sets `--lf-paper` and
`--lf-ink` to its ground and text colours, so Leaf's panel, thread cards and
widgets stand on that ground rather than the browser's white. A reset
that zeroes `body`'s padding, or an app shell whose own box scrolls, puts
`padding-top: var(--lf-head-room)` on whatever scrolls. A box page CSS makes opaque,
such as a sticky bar, uses `background: var(--lf-ground)` to match its containing
surface; cards and playground previews set this property for their contents.
`page-layout.md`, "Page CSS and Leaf's controls", says how page CSS meets Leaf's own
controls.

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
leaf page vocabulary <page> | jq '.["lf-options"], .[".lf-lede"], .["$series"]'
```

Before writing markup, read the author instructions for the entries you will use,
including any example you copy:

```bash
leaf page instructions <page> --use lf-options --use .lf-lede | jq -r '.author // empty'
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

Widget attributes carry scalars and children carry prose; a member of a compound widget
takes its name in `label`, as an option card and a board card do, and shows its title
in its own HTML, a leading `<strong>`. A widget whose body is data, such as `lf-code`,
holds escaped text in a `<pre>`. Escape `&` first, then `<` and `>`.

Format filenames and paths as inline code.

Write a formula in LaTeX in a `<code class="language-math">`, escaping `&`, `<` and `>`
as in any HTML text: inside a sentence it reads as an inline formula, and as the code
of its own `<pre>`, which takes an id like any block a reader points at, as a display
formula. Leaf typesets the LaTeX in the surrounding text's size and colour,
`page check --render` reports a formula it can't read, and a comment quotes a formula
by its LaTeX.

Show quoted text as a reader of its language reads it, whoever wrote the text and
whoever it is for: code and data coloured, Markdown rendered, and only text in no
language, such as a log, literal and uncoloured.

Show source snippets as `<pre><code class="language-javascript">…</code></pre>`, and
put the same block inside a code excerpt with numbered lines for a walkthrough. Name
the actual language from `$languages.names` or a bundled grammar's alias, such as
`language-js` and `language-sh`. Leaf colours a native block only where the reading
face reaches it: the `reading` theme turns it on, and a page with no theme sets
`--lf-reading-face: 1` on a box around the `<pre>` (`package-themes.md`, "A page's
theme"). Format example code with the language's usual indentation and line breaks,
even where it reached you with several statements or fields packed onto a line, and keep
it working when you reformat it. Quote source verbatim when quoting it.
Data in a language Leaf colours, such as JSON a tool returned, goes in a code block
named for its language, even beside plain samples, with its values exact, `…` included,
and laid out so the reader can pick out each field and compare values down a column.
A code block wraps lines longer than the column's 80 or so characters, which breaks the
indentation the reader follows. Give a block with longer lines `data-width="wide"`
(`page-layout.md`, "Bounds and widths").

Show Markdown you quote, such as a rule from a doc, a pull request's description or a
prompt an agent receives, in a text document that previews it, with its exact Markdown
a tab away (`authoring-evidence.md`, "Source files and media"). The preview draws
tags in the text as HTML, so show text whose own tags carry its meaning, such as a
prompt's `<example>` blocks, as its source alone, coloured as Markdown. Where Markdown
syntax is itself the subject, show it literally in `<pre><code>`.

For a custom horizontal scroll area, set `overflow-x: auto` and add
`class="lf-scroll"` to that same box. Leaf contains its positioned descendants and
adds keyboard access and continuation cues when content exceeds the box. Its CSS may
change overflow at a breakpoint; Leaf measures the declared surface, never all of its
descendants. Leaf fits media to its container (below), so an image or SVG meant to
scroll in the box needs `max-width: none`. For a box that scrolls vertically, see
`page-layout.md`, "Bounds and widths".

Leaf fits an image or SVG to its container on every page. On a page that wears the
reading face, as a page in the `reading` theme does (`package-themes.md`, "A page's
theme"), Leaf also wraps a `<pre>`'s long lines, and a table's columns size to their
content. It puts each line of a `<pre>` in a `<span data-lf-pre-line>`, so the rows a line wraps onto
hang from its indent behind a mark; a selector such as `pre span` reaches those spans
too. A block whose columns must line up past its container's width, such as a diagram
drawn in characters, keeps its lines with `white-space: pre` and scrolls them sideways. Such
a block or a table scrolls inside a box that sets its own width, such as the column, a
panel or any other block. A box that takes its width from its content, such as a flex
item or a grid `auto` track, widens to its lines or the table's columns instead, past
a phone's window if they need it, so give that box `min-width: 0` to keep it scrolling
inside. A page without the face keeps the browser's tables and code blocks, so it puts
one that can outgrow a narrow window in a box of its own that scrolls sideways, as
above. Text that can't break, such as a bare identifier or a cell kept on
one line, holds its column at its full length, and once the table scrolls sideways,
prose in the other columns wraps a word per line. Under the face, put identifiers in
`<code>`, which can break inside a cell, and write each row's name as its first cell,
a `<th scope="row">`: a `<code>` name that is all the heading holds stays whole, up to
a third of the column, and the names stay in view while the other columns scroll. Keep
the columns to what fits at the narrowest width the page's readers use.

## Stable anchors

Give each section, major block and Leaf element a stable, meaningful `id` on the
smallest element a user would point at. A user comments on words by selecting them and
on anything else by pointing at it, with Alt-click or by pressing `s` for Select mode
and then the target or its hint. A pointed comment lands on the nearest element
around the pointer that has an id. So each block they would point at whole, such as a
picture, a drawing, a code block, a table or an aside, needs an id of its own, on
itself or on a block that holds only it and its caption, such as its `<figure>` or its
table cell. An inline wrapper, such as a link around a picture, has only the box of a
line of text, so there the id goes on the picture. One id around several such blocks,
as on a table of screenshots, puts a comment aimed at any one of them on the whole
table. Where a wrapper holds only one child that fills it, put the id on the child.

Group a heading with its eyebrow or subtitle in `<hgroup>` and put the id on the
`<hgroup>`.
When that title starts a section with an id, the `<section>` carries the address
instead.

Threads, reading position and version comparison all find a block by its id, so a
rewritten paragraph keeps its id. A heading offers the reader a link to that address, so
a heading with no id on it, its `<hgroup>` or the section it opens offers none.
