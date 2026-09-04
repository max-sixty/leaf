# Interactive and external evidence

Read the selected registry entries first. Read this reference when the page uses
measured facts, diagrams, charts, source files, images, or before/after captures.

## Measured facts

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

## Interactive and visual evidence

Introduce each interaction in the page's own language: say that a board takes a
drag, an options group takes a click, or a review task's nested Decision takes a pick.
Do not copy the connective sentence from another page.

Use `lf-diagram` for flows, state machines, sequences, class relationships, ER
schemas, and small XY plots; Beautiful Mermaid renders that Mermaid-source subset.
Flowcharts accept Mermaid's classic node shapes. Their `classDef` declarations can
apply Leaf's semantic tokens directly, for example
`fill:var(--ok-tint),stroke:var(--ok),color:var(--ok-ink)`. Use `lf-chart` for
quantities that need Leaf's data-first chart vocabulary: a comparison across a few
categories, a run over time, a ranking, a composition, or two numbers against each
other. The diagram renderer is 1.5MB, so `lf-diagram` travels in the `diagram`
package rather than in every page: initialize a page that wants one with
`leaf page init --package diagram <page>`. `lf-chart` needs no selection. A handful of
numbers the sentence beside them can carry is prose; a chart is for when the
shape of the numbers is the point. Use inline SVG only for a bespoke drawing.
Use `<pre><code class="language-…">` for selectable literal source and `lf-code`
for a line-numbered walkthrough. The registry's `$languages.names` lists accepted
language names. Keep logs and transcripts plain when they are not source code.

The authored source ids also provide comment coordinates. A flowchart node or
subgraph, state or composite state, sequence participant, class, or ER entity listed
in `parts` takes an individual comment. Edges, sequence messages, and XY marks have no
stable source id and take comments on the whole drawing.

## Source files and media

Use `lf-source` when literal UTF-8 text should remain selectable and commentable
without copying it into the authored HTML. Use a unified-patch capture with
`lf-diff`; the diff keeps its per-file view
and gives each source line a stable comment coordinate. Its Pierre renderer is
1.7MB, so `lf-diff` and the `unified-diff` contract travel in the `diff` package:
initialize such a page with `leaf page init --package diff <page>`. The reader gets
the rest of a long review without anything authored: each file's header pins under
the banner while its own rows scroll past, `]` and `[` step by hunk and `}` and `{`
by file, and a Soft wrap switch in the diff's own header folds lines too long for
the column — paper takes that wrap whether or not the switch is on, so nothing is
cut off a printed patch. First add a current-data binding so Leaf can give the
source its page-lifetime contract:

```html
<lf-source id="skill-source" source="leaf-skill" language="markdown"></lf-source>

<lf-diff id="review-patch" source="pr-patch" snapshot="2" collapsed><pre></pre></lf-diff>
```

Then capture the whole UTF-8 text file or an inclusive line range:

```bash
leaf data capture <page> leaf-skill --file SKILL.md --label SKILL.md
leaf data capture <page> leaf-skill --file SKILL.md --lines 71:102
leaf data capture <page> pr-patch --file change.patch --format unified-diff \
  --label "PR at 8f61c2a"
```

The `unified-diff` transform validates each file and builds a structured value whose
`files` array carries its path, change counts, and patch. Leaf sends only that manifest
at startup and fetches each patch fragment when its disclosure opens. Files the widget
cannot present as review evidence are rejected before capture: binary, mode-only, empty
added or deleted, copy, malformed hunk, and inexact hunkless rename entries.

Capture and structured `data set --capture-label` print the data revision retained. Add
`snapshot="REVISION"` before
stamping or handing over the reviewed page to freeze that capture; omit the
attribute when the block should follow later captures or `data set` calls. On a
served page, the valid unpinned save that adds the binding may already have
become an interim revision before capture. That is expected; the next valid save
activates the pinned snapshot. Wrap `lf-source` in ordinary `<details>` or place
it in an `lf-tabs` panel when the evidence should start collapsed or share a
compact frame with alternatives. A bound `lf-diff` keeps one empty `<pre></pre>`
because that is the shared data-body shape; the captured patch, not that element,
supplies its text. Add `collapsed` to a large diff so each file starts closed; a
comment or navigation target still opens the file that owns its line.

Run `leaf page media <page> <file>…` and use the printed `/media/…` path for
images. Never inline image bytes. For a real visual change, use `lf-shot` with
before and after captures from the same viewport. Put invented examples inside
`lf-specimen` and make them visibly fictional. Render tickets, source locations,
and URLs as real links.
