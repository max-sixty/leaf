# Interactive and external evidence

## Measured facts

Use `lf-num` for a repeatably measured scalar inside a sentence, with the snapshot
that established it. A headline KPI belongs in `lf-metric`; a number without a
repeatable measurement feed remains ordinary text. Freeze a measured prose value
with its provenance:

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

If the source's `updated` instant later moves past `at`, `page check` advises
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
its renderer parts from Mermaid. `page check --render` reports a diagram the
renderer refuses or draws empty, not one it draws only in part, so inspect each
rendered diagram. Without visual access, check the source's labels and relations
against the claims it supports, and state those claims in prose or a table beside it
so the user need not rely on an uninspected picture. Follow `page-authoring.md`,
"Pre-handover review", for the checks and what remains unverified.

Draw what Mermaid's automatic layout cannot put where it belongs, such as a page
layout, geometry, a wireframe, or a thumbnail inside an option, as the `svg.drawing`
idiom in a `<figure>` with an `id`, and give the figure `data-width="wide"` when it
needs the room. The figure scales the drawing to its width, labels included, so draw
the `viewBox` near the width it is shown at: 1600 units in a 720px column draw an 11px
label at 5px, and `page check --render` advises when a label is drawn under 10px.
Keep it schematic: a window is a rounded box, a line of text a grey bar, a marker a
dot, and only what the figure is about takes the accent colour. Put the states being
compared side by side in one figure at one scale, drawn alike except where they
differ. The idiom's classes paint in theme tokens, so the drawing follows
the light and dark schemes; an SVG file added with `leaf page media` loads as an image
and cannot read them. Give a mark particular to the subject a page-local class on the
same tokens. Keep the `<figcaption>` for what the drawing cannot show, and inspect
each rendered figure as you would a diagram.

Use `lf-chart` rather than Mermaid's XY or pie charts for quantities: its body is
Observable Plot code, the options `Plot.plot` takes, so any chart Plot draws is
available in Plot's own API. `lf-chart` needs no package. A handful of numbers the
sentence beside them can carry is prose; a chart is for when the shape of the
numbers is the point.

For source snippets and code walkthroughs, follow `page-authoring.md`, "Theme and
vocabulary". An `lf-code` block's `lines` attribute quotes an excerpt
of a longer file under the file's own line numbers, with elided rows where it skips;
a note placed at a skipped line captions that row with what was left out.

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

A patch goes through the `diff` package's producer script; the contract's
instructions give the command:

```bash
leaf page instructions <page> producer --contract unified-diff
```

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

Run `leaf page media <page> <file>…` and use each printed `/media/…` `path` for
images, video, and audio. Never inline media bytes. Use a recording for a fixed
demo or screen capture; keep a live widget where the user should manipulate the
subject. Give native `<video>` and `<audio>` elements `controls`, label their
content, and give a video a `poster` image. MP4 and WebM video, and MP3, M4A,
Ogg, and WAV audio are admitted; codec playback is the browser's. Export embeds
the complete recording for offline playback with no size cap or omissions: base64
stores each recording once and adds about a third to its bytes, so trim recordings
to what the reader needs. Offline embedded images, fonts, and recordings need
JavaScript; the scripts-off export preserves authored text, layout, and alt text.
Browser paste and upload still accept raster images only.

Put invented examples inside `lf-sample` and
make them visibly fictional. Render tickets, source locations, and URLs as real
links.

For a page-scale visual change, use `lf-shot` with before and after captures from
the same viewport, of the versions the page compares. For a small change, crop
both frames to the changed area or show the element itself at real size.
Before writing the prose and `alt` around a pair, open both images and compare
them where the change should be.
Add `outlines`, and each frame outlines what changed and, dashed, what only moved,
where it sits in that frame, and the rail counts them. Leave it off where most
outlines would mark what the pair is not about, such as live data that moved between
captures you cannot retake, and say in the prose where to look. Either way, the rail
reads "identical", "only slight changes" where no pixel moved far, or "changed
throughout" where most of the image changed. Where it reads "identical", or no
outline stands where the prose puts the change, capture a case that shows the
change, or say that nothing changed. Where it reads "only slight changes", the
reader will hardly see the change, so name it in the prose, or say that nothing but
redrawing changed.
