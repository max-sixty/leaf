# Page authoring

Read this before writing or revising a version.

## Read the registry

`<page>/registry.json` is the page's complete vendored vocabulary. List its keys
without printing the entries:

```bash
registry="<page>/registry.json"
jq 'keys' "$registry"
```

Then read the complete entries for the widgets and `$` facts the page will use:

```bash
registry="<page>/registry.json"
jq '{"lf-chart": .["lf-chart"], "$series": .["$series"]}' "$registry"
```

Each selected entry owns its purpose and instructions in `description`, along with
its example, attributes, content and parent rules, and behavioral contracts.
Package-defined tags and `$` facts join the same key list.
`leaf page guidance <page>` lists the composed guidance audiences; read `author`
when it is present.

## Document scaffold

Write a complete HTML document. The head contains exactly one `/theme.css` link
and one external `/leaf.js` module. Every `lf-*` element has an explicit end tag.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>…</title>
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'">
  <link rel="stylesheet" href="/theme.css">
  <script type="module" src="/leaf.js"></script>
</head>
<body>
  <main>…</main>
</body>
</html>
```

## Theme and vocabulary

Write semantic HTML and use the registry's class idioms. The vendored theme owns
palette, type, spacing, headings, tables, code, and widget presentation. Use a
page-local `<style>` only for presentation unique to this page.

Widget attributes carry scalars; children carry prose; an item's title is a
leading `<strong>`. A data-bodied widget such as `lf-diagram` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text. The
registry is the only widget vocabulary.

The runtime injects the status banner, thread panel, version picker, keyboard
shortcuts, live-leaves tray, and open-decisions tray. Authors declare reader
decisions through the registry's decision widgets and regions, but do not duplicate
that chrome or maintain a second list of it in the page.

Keep content inside the page's column. The theme scrolls a `<pre>` or a table
that runs wider than it and fits an image or SVG to it, so none of them needs a
width. A table that scrolls has every column at its longest unbreakable run,
and the browser gate refuses one that scrolls with a cell in it wrapped: put an
identifier in `<code>`, where it breaks inside its cell, rather than bare, where
it holds its column and squeezes the prose beside it, and keep the columns to
what the measure holds. Widgets whose registry
entry declares a wide shape size themselves; fix a diagram that is too wide in
its source rather than pinning a page width.

## Stable anchors

Give every section, major block, and widget item a stable, meaningful `id`.
Threads and reading position attach to those ids across versions. Keep an id
where its passage survives, and stay out of the `lf-` prefix: it is the runtime's
namespace for ids and for classes alike, and `data-lf-` is the same for
attributes. `version check` refuses all three, including a name the runtime does
not write today — the namespace is reserved, not the list of names in it.

A code block, table, figure, or aside that a reader will point at as a whole also
needs a tight id, either on itself or on its immediate semantic container.

When broad context gives way to focused work, branch the live page with one
`lf-tabs`. Keep the shared title and lede before it, and move earlier context
intact into another `lf-tab` so its ids retain their comments and decisions. Put
the current workstream first: ordering makes it the default for a reader with no
saved panel or reading position. A saved panel or restored position takes
precedence. Threads, decisions, versions, and sign-off still cover the whole page,
so none of that runtime chrome belongs inside a tab.

## Decisions and sign-off

Put alternatives in `lf-options` with `choose`. Each option carries its title,
case, and evidence in the option itself. When whole page sections are the
alternatives, use short option labels with `for="<section-id>"`. Use `multiple`
only when several options may stand.

On the page the group's last cell is an option the reader writes, saying
`Another option`, so author the alternatives you actually mean and no catch-all
beside them: a `Something else` option takes a click where that cell takes the
answer. In a thread the reply box is already that cell, so the group carries
none of its own.

Writing there is the reader dealing with the question, so the group stops being
one of the page's open decisions and the ball is yours. Nothing is recorded by it:
the group still holds no new pick. Answer what they wrote in the authored page:
carry their words in as another option and mark the pick it settled. If the reader
explicitly rejects every option, settle the group without a pick. This thread
takes no agent reply; if the revision needs an answer first, open a separate
exact-section thread on the same Decision. Only authored state in a later version can
answer an originating open Decision, or change its declared answer when the Decision was
already answered. Reader actions before or after the proposal do not substitute
for that revision, and an unrelated version cannot close it.

A decision must name itself without context outside the decision. Begin `lf-decision` with one
ordinary heading, then include any introduction or evidence and the actionable
widget. That heading is the question: it stays in the document's hierarchy, is
available to selection and comments, names the Decisions tray row, and is where `d` /
`D` arrives. The nested widget still owns the answer or request lifecycle. An
`lf-decision` has exactly one leading direct heading and one non-quoted local decision
declared by `x-awaits` or `x-request.decision`.

Keep the author's preference in the option it belongs to as ordinary prose:
`<em>My take: this is the safest rollout.</em>` is enough. Say why when the reason
matters. Do not encode the preference as a badge, tint, ring, or option state; it
is an argument for the reader to weigh, not a decision the reader has made.

A page whose approval unblocks work declares:

```html
<meta name="lf-review" content="sign-off">
```

An informational page omits it. A `done` event approves the work and leaves the
page live while that work proceeds.

## Revisions and reader-owned words

Fresh content is authored directly. Rewrite prose the reader has already seen as
an `lf-suggestion`: `lf-old` carries the current markup verbatim, `lf-new` carries
the proposed replacement, and `resolves="<comment-id>"` connects a requested fix
to its thread. Introduce the first suggestion in prose so the reader knows its
new words can also receive comments.

A correction is not a proposal. Where the page got something wrong — a number, a
misread source, a unit — rejecting the fix would only restore the error, so the
reader has nothing to weigh: write the true thing straight and name the correction
in the version note. Suggest wording the reader could reasonably prefer as it
stands.

Use `lf-draft` for a passage whose wording belongs to the reader. Carry their
submitted words verbatim into the next revision. A draft never sits inside a
suggestion, and a suggestion does not propose a widget's state.

## Honoring reader state

The event log outranks authored markup. The server projects every standing action
and the browser replays that view onto later revisions, but the source must
eventually record the decision so the page reads correctly without the log:

- Mark every picked option `chosen`.
- Carry an option a reader wrote in the group's last cell into the group as an
  option, or settle the question their words settled. Their answer stands in a
  thread and in no record at all, and the group stops asking only until you have
  finished with that thread.
- Replace an accepted suggestion with `lf-new`; replace a rejected one with
  `lf-old`, retaining ids on surviving passages.
- Carry a reader edit verbatim.
- Carry a worker report into markup, or mark the element `overruled` with the
  reason in the version note.

To deliberately replace state established by an action, put `restated` on the
rewritten element and explain why in the version note. Without `restated`, replay
restores the user's state and `version check` refuses a conflicting version. Do
not carry a gesture withdrawn by an `undo` event.

## Keeping the current page current

Each active revision presents what is live now. Move a concluded section intact to a
`Settled` section at the foot, inside a `<details>` whose summary names the
question and what closed it. Preserve its ids and words. Mark a concluded
`lf-options` group `settled` when it retires inside a section that remains live.

Relocation is not revision: moving unchanged content needs neither a suggestion
nor `restated`. Keep a decision live while it is being applied, and settle it
only after the work no longer revisits it. Keep a section live while the reader
is still commenting there.

## Reading cost

Open words are read; collapsed words are there when the reader wants them. So
what stands open in the column is what the reader has to take from the page, and
its backing goes under `<details>`: the full argument, a transcript, source and
output, how a number was reached. Collapsed words stay quotable, and the runtime
opens the disclosure when a comment or a walk lands inside one. A decision never
collapses, and neither does the evidence it turns on.

The title names the page, and the lede under it carries the finding. A section
that reaches a finding says it in the heading, in a clause short enough to scan,
and a `<summary>` and an option's `<strong>` do the same for what they cover.
"Why the prefixes matter" and "What we learned" promise a finding and withhold
it. A name that only says what it holds is right where there is no finding to
state, over a list, a table, or a board that speaks for itself.

Give a structure its own shape rather than describing it in sentences. A flow or
a sequence is a diagram, a comparison is a table, a measurement is a metric and a
run of them is a chart, a set of movable things is a board, and the prose beside
one says only what the shape cannot. What is left for prose is the claim, the
reason it holds, and the question the page is asking. A few sentences hold all
three. A section that runs longer is carrying either a structure with a shape of
its own or backing that belongs under `<details>`.

When one measured scalar belongs inside a sentence, freeze it with its provenance:

```html
The import takes <lf-num source="import-latency"
  at="2026-08-27T09:00:00Z" via="uv run bench-import">184 ms</lf-num> at p95.
```

Set that source after every run with `leaf data set PAGE import-latency`, then pin
`at` to that write's `updated` instant. The element's words and `at` remain part of the
authored version; the replaceable source is only the freshness channel. If its `updated`
instant moves past `at`, `version check` advises that the pinned number needs another
look. `leaf data set` stamps `updated` at wall-clock, so an `at` naming when the
measurement itself ran is already behind the write that recorded it and reads as stale
the moment it is authored. This detects a rerun the version missed, not a measurement
that is merely old. Use one source id for one stable measurement definition.

Write for what the reader has seen, which is this conversation and the page so
far. Introduce the names a decision depends on, put evidence on the page for a
claim they could doubt, and drop the journey once the conclusion replaces it.

## Interactivity and evidence

Introduce each interaction in the page's own language: say that a board takes a
drag, an options group takes a click, or a review task's nested Decision takes a pick.
Do not copy the connective sentence from another page.

Use `lf-diagram` for what mermaid draws — a flow, a sequence, a state machine —
and `lf-chart` for quantities: a comparison across a few categories, a run over
time, a ranking, a composition, two numbers against each other. A handful of numbers the sentence beside them can
carry is prose; a chart is for when the shape of the numbers is the point. Use
inline SVG only for a bespoke drawing. Use `<pre><code class="language-…">` for
selectable literal source and `lf-code` for a line-numbered walkthrough. The
registry's `$languages.names` lists accepted language names. Keep logs and
transcripts plain when they are not source code.

Use `lf-source` when the literal text already lives in a UTF-8 file and should remain
selectable and commentable without copying it into the authored HTML. First add a
current-data binding to the page source so Leaf can give the source its page-lifetime
contract:

```html
<lf-source id="skill-source" source="leaf-skill" language="markdown"></lf-source>
```

Then capture the whole UTF-8 text file or an inclusive line range:

```bash
leaf data capture <page> leaf-skill --text-file SKILL.md --label SKILL.md
leaf data capture <page> leaf-skill --text-file SKILL.md --lines 71:102
```

Capture prints the data revision it retained. Add `snapshot="REVISION"` before
stamping or handing over the reviewed page to freeze that capture; omit the attribute
when the block should follow later captures or `data set` calls. On a served page, the
valid unpinned save that adds the binding may already have become an interim revision
before capture. That is expected; the next valid save activates the pinned snapshot.
Wrap `lf-source` in ordinary `<details>` or place it in an `lf-tabs` panel when the
evidence should start collapsed or share a compact frame with alternatives.

Run `leaf page media <page> <file>…` and use the printed `/media/…` path for
images. Never inline image bytes. For a real visual change, use `lf-shot` with
before and after captures from the same viewport. Put invented examples inside
`lf-specimen` and make them visibly fictional. Render tickets, source locations,
and URLs as real links.

## Pre-handover review

Every source activation runs the deterministic markup check. For a quick page
put up for reaction, that check is the whole gate, and the URL goes out as soon
as it passes. A finished record takes the browser gate once before its URL first
reaches the user; a quick page that a stamp turns into a record takes it before
that stamp:

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
