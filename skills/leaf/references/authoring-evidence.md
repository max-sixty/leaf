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

Use `lf-chart` rather than Mermaid's XY or pie charts for quantities that need Leaf's
data-first chart vocabulary: a comparison across a few categories, a run over time, a
ranking, a composition, or two numbers against each other. `lf-chart` needs no
package. A handful of numbers the sentence beside them can carry is prose; a chart is
for when the shape of the numbers is the point. Use inline SVG only for a bespoke
drawing. Use `<pre><code class="language-…">` for selectable literal source and
`lf-code` for a line-numbered walkthrough. The registry's `$languages.names` lists
accepted language names. Keep logs and transcripts plain when they are not source
code.

A diagram's authored source ids also give the user something to comment on: the
`lf-diagram` entry says which boxes `parts` can open to a comment of their own.

## Source files and media

Use `lf-text-document` when literal UTF-8 text should remain selectable and
commentable without copying it into the authored HTML, and `lf-diff` for a
unified-patch capture. `lf-diff` and the `unified-diff` contract travel in the `diff`
package: initialize such a page with `leaf page init --package diff <page>`. First
add a current-data binding so Leaf can give the source its page-lifetime contract:

```html
<lf-text-document id="skill-source" source="leaf-skill" language="markdown"></lf-text-document>

<lf-diff id="review-patch" source="pr-patch" collapsed><pre></pre></lf-diff>
```

Then capture the whole UTF-8 text file or an inclusive line range:

```bash
leaf data capture <page> leaf-skill --file SKILL.md --label SKILL.md
leaf data capture <page> leaf-skill --file SKILL.md --lines 71:102
leaf data capture <page> pr-patch --file change.patch --format unified-diff \
  --label "PR at 8f61c2a"
```

The `unified-diff` transform validates each file and builds a structured value whose
`files` array carries its path, change counts, and patch. An entry the widget's
declaration does not support is refused before capture.

Capture and structured `data set --capture-label` print the data revision they
retained, one sequence across the page's sources. Before stamping or handing over the
reviewed page, add that revision as `snapshot` to freeze the capture, as in
`<lf-diff id="review-patch" source="pr-patch" snapshot="2" collapsed>` after the
capture that printed `snapshot 2`; omit the attribute when the block should follow
later captures or `data set` calls. On a served page, the valid unpinned save that
adds the binding may already have become an interim revision before capture. That is
expected; the next valid save activates the pinned snapshot.

Run `leaf page media <page> <file>…` and use the printed `/media/…` path for
images. Never inline image bytes. For a real visual change, use `lf-shot` with
before and after captures from the same viewport. Put invented examples inside
`lf-specimen` and make them visibly fictional. Render tickets, source locations,
and URLs as real links.
