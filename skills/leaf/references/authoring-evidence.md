# Interactive and external evidence

## Measured facts

When one measured scalar belongs inside a sentence, freeze it with its provenance:

```html
The import takes <lf-num source="import-latency"
  at="2026-08-27T09:00:00Z" via="uv run bench-import">184 ms</lf-num> at p95.
```

The number and its `at` are part of the authored version; the source is only the
freshness channel. After every run:

1. Run the measurement.
2. Record it with `leaf data set PAGE import-latency`. The command stamps the
   source's `updated` instant at wall-clock and prints it.
3. Write that printed `updated` instant into `at`, not the time the measurement
   itself ran; an earlier instant is already behind the write and reads as stale
   the moment it is authored.

If the source's `updated` instant later moves past `at`, `version check` advises
that the pinned number needs another look. This detects a rerun the version
missed, not a measurement that is merely old. Use one source id for one stable
measurement definition.

## Interactive and visual evidence

Introduce each interaction in the page's own language: say that a board takes a
drag, an options group takes a click, or a review task's nested Ask takes a pick.
Do not copy the connective sentence from another page.

Use `lf-diagram` for flows, state machines, sequences, class relationships, ER
schemas, and the other Mermaid families its entry lists. It travels in the `diagram`
package rather than in every page: initialize a page that wants one with
`leaf page init --package diagram <page>`, then read the entry for styling and where
its renderer parts from Mermaid. `version check --render` reports a diagram the
renderer refuses or draws empty, not one it draws only in part, so inspect each
rendered diagram. Without visual access, check the source's labels and relations
against the claims it supports, and state those claims in prose or a table beside it
so the user need not rely on an uninspected picture. Follow `page-authoring.md`,
"Pre-handover review", for the checks and what remains unverified.

Draw what Mermaid's automatic layout cannot put where it belongs, such as a page
layout, geometry, a wireframe, or a thumbnail inside an option, as an inline `<svg>`
in a `<figure>` with an `id`, and give the figure `data-width="wide"` when it needs
the room. Keep it schematic: a window is a rounded box, a line of text a grey bar, a
marker a dot, and only what the figure is about takes the accent colour. Put the
states being compared side by side in one figure at one scale, drawn alike except
where they differ. Style every figure on the page from one page-local set of classes
whose fills and strokes are theme tokens such as `var(--ink)`, `var(--muted)`,
`var(--accent)`, and `var(--ok)`. The tokens follow the light and dark schemes; an
SVG file added with `leaf page media` loads as an image and cannot read them. Give the
`<svg>` `role="img"` and a `<title>` stating its claim, keep the `<figcaption>` for
what the drawing cannot show, and inspect each rendered figure as you would a
diagram.

Use `lf-chart` rather than Mermaid's XY or pie charts for quantities that need Leaf's
data-first chart vocabulary: a comparison across a few categories, a run over time, a
ranking, a composition, or two numbers against each other. `lf-chart` needs no
package. A handful of numbers the sentence beside them can carry is prose; a chart is
for when the shape of the numbers is the point. Use
`<pre><code class="language-…">` for selectable literal source and
`lf-code` for a line-numbered walkthrough; its `lines` attribute quotes an excerpt
of a longer file under the file's own line numbers, with elided rows where it skips;
a note placed at a skipped line captions that row with what was left out.
The registry's `$languages.names` lists
accepted language names. Keep logs and transcripts plain when they are not source
code.

A user can comment on a drawing as a whole and quote the words in it, but a part
of it takes a comment of its own only when the author named that part. In an
`lf-diagram`, the entry says which boxes `parts` opens to a comment of their own.
In an inline `<svg>`, give an `id` to each element the user may want to point at,
usually a `<g>` that holds one shape and its label. The user can then aim at that
part alone, and the thread's anchor reports its `id` to you, so choose ids that
name what the part is.

Leaf paints a comment's mark where its part stood when the mark was painted, so a
part that CSS animates or a script redraws moves away from its mark. Draw moving
parts in a page widget that registers them: declare `x-visual` parts on its entry,
call `registerVisualParts` from its module, and call the registration's `update()`
after each paint so marks move with their parts. A `reveal` that draws a frame
holding a part the current frame lacks lets a thread still take the user to it. The
registry's `$keys` entry for `x-visual` states the contract.

## Source files and media

Use `lf-text-document` when literal UTF-8 text should remain selectable and commentable
without copying it into the authored HTML. Use a unified-patch capture with
`lf-diff`; the diff keeps its per-file view
and gives each source line a stable comment coordinate. `lf-diff` and the
`unified-diff` contract travel in the `diff` package: initialize such a page with
`leaf page init --package diff <page>`. First add a data binding so Leaf can give the
source its page-lifetime contract:

```html
<lf-text-document id="skill-source" source="leaf-skill" label="SKILL.md" language="markdown"></lf-text-document>

<lf-diff id="review-patch" source="pr-patch-8f61c2a" collapsed><pre></pre></lf-diff>
```

Then set the source. Text is one JSON string, of the whole file or an inclusive line
range:

```bash
jq -Rs . SKILL.md | leaf data set <page> leaf-skill
sed -n '71,102p' SKILL.md | jq -Rs . | leaf data set <page> leaf-skill
```

A patch goes through the `diff` package's producer script; `leaf page guidance <page>
producer` gives the command, as it gives each contract's own instructions.

A bound widget shows its source's current value, in every version and thread that
binds it. Evidence a review must keep exactly gets a source id of its own, such as the
commit in `pr-patch-8f61c2a`, which nothing captures into again; evidence that should
follow later captures or `data set` calls shares one id. `lf-text-document` shows
`label` above the text, or the source id without one. Wrap `lf-text-document` in
ordinary `<details>` or place it in an `lf-tabs` panel when the evidence should start
collapsed or share a compact frame with alternatives. A bound `lf-diff` keeps one empty
`<pre></pre>` because that is the shared data-body shape; the captured patch, not that
element, supplies its text. Add `collapsed` to a large diff so each file starts closed;
a comment or navigation target still opens the file that owns its line.

Run `leaf page media <page> <file>…` and use the printed `/media/…` path for
images. Never inline image bytes. For a real visual change, use `lf-shot` with
before and after captures from the same viewport. Put invented examples inside
`lf-specimen` and make them visibly fictional. Render tickets, source locations,
and URLs as real links.
