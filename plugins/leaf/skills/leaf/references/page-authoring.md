# Page authoring

Read this before writing or revising a version and before the first handoff.
`leaf page catalog <page>` is the authority for the page's vendored widgets,
attributes, examples, and theme idioms; read it before authoring.

## Document scaffold

Write a complete HTML document. The head contains exactly one `/theme.css` link
and one external `/leaf.js` module. Every `lf-*` element has an explicit end tag.

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
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

Write semantic HTML and use the catalog's class idioms. The vendored theme owns
palette, type, spacing, headings, tables, code, and widget presentation. Use a
page-local `<style>` only for presentation unique to this page.

Widget attributes carry scalars; children carry prose; an item's title is a
leading `<strong>`. A data-bodied widget such as `lf-diagram` holds escaped
notation in `<pre>`, because its whitespace is part of the data. Escape `&`
first, then `<` and `>`; any other order can silently decode entity text. The
catalog is the only widget vocabulary.

The runtime injects the status banner, comment sidebar, version picker, keyboard
shortcuts, live-leaves tray, and open-asks tray. Author the asks as widgets,
but do not duplicate that chrome or maintain a second list of it in the page.

Keep content inside the page's column. Give raw `<pre>`, tables, SVG, and images
`max-width: 100%` or local overflow. Widgets whose catalog entry declares a wide
shape size themselves; fix a diagram that is too wide in its source rather than
pinning a page width.

## Stable anchors

Give every section, major block, and widget item a stable, meaningful `id`.
Comments and reading position attach to those ids across versions. Keep an id
where its passage survives, and avoid the `lf-` prefix reserved for runtime ids.

A code block, table, figure, or aside that a reader will point at as a whole also
needs a tight id, either on itself or on its immediate semantic container.

When broad context gives way to focused work, branch the live page with one
`lf-tabs`. Keep the shared title and lede before it, and move earlier context
intact into another `lf-tab` so its ids retain their comments and decisions. Put
the current workstream first: ordering makes it the default for a reader with no
saved panel or reading position. A saved panel or restored position takes
precedence. Comments, asks, versions, and sign-off still cover the whole page,
so none of that runtime chrome belongs inside a tab.

## Asks and sign-off

Put alternatives in `lf-options` with `choose`. Each option carries its title,
case, and evidence in the option itself. When whole page sections are the
alternatives, use short option labels with `for="<section-id>"`. Use `multiple`
only when several options may stand.

An ask must name itself without surrounding context. Give an options group a
`label` containing its question; tasks and milestones lead with their own
`<strong>` title.

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
submitted words verbatim into the next version. A draft never sits inside a
suggestion, and a suggestion does not propose a widget's state.

## Honoring reader state

The event log outranks authored markup. The browser replays every standing action
onto later versions, but the version must eventually record the decision so the
page reads correctly without the log:

- Mark every picked option `chosen`.
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

Each version presents what is live now. Move a concluded section intact to a
`Settled` section at the foot, inside a `<details>` whose summary names the
question and what closed it. Preserve its ids and words. Mark a concluded
`lf-options` group `settled` when it retires inside a section that remains live.

Relocation is not revision: moving unchanged content needs neither a suggestion
nor `restated`. Keep a decision live while it is being applied, and settle it
only after the work no longer revisits it. Keep a section live while the reader
is still commenting there.

## Interactivity and evidence

Introduce each interaction in the page's own language: say that a board takes a
drag, an options group takes a click, or a review task awaits a decision. Do not
copy the connective sentence from another page.

Use `lf-diagram` for flow, sequence, and state diagrams; use inline SVG only for
bespoke drawings. Use `<pre><code class="language-…">` for selectable literal
source and `lf-code` for a line-numbered walkthrough. The catalog lists accepted
language names. Keep logs and transcripts plain when they are not source code.

Run `leaf page media <page> <file>…` and use the printed `/media/…` path for
images. Never inline image bytes. For a real visual change, use `lf-shot` with
before and after captures from the same viewport. Put actual source, output, or a
diff behind `<details>`; put invented examples inside `lf-specimen` and make them
visibly fictional. Render tickets, source locations, and URLs as real links.

Write for what the reader has seen: the conversation and the page so far.
Introduce names the decision depends on, support questionable claims with
evidence on the page, and remove journey narrative once the current conclusion
replaces it.

## Pre-handover review

Publishing runs the deterministic markup check. Before the URL first reaches the
user, run the browser gate once:

```bash
leaf version check <page> --render
```

It loads the page in both color schemes and checks runtime errors, widget size,
overflow, diagrams, selectable words, print output, replay-safe state, and
action idempotence. Fix every failure; a screenshot is not a substitute.

Then read the page as the user will. Confirm that referents are introduced,
claims have evidence, decisions have controls, diagrams add information, links
work, and no section merely repeats or preserves the history of reaching the
current answer.
