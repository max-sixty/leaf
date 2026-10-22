# Interactive and external evidence

## Measured facts

Use `lf-num` for a number in a sentence that a repeatable measurement produced: bind it
to its measurement source and pin the `run` receipt `leaf data set` returns, as the
`lf-num` entry shows. Use one source id per measurement, and plain HTML for a number
with no repeatable source. The value stays as you wrote it, and any later write to the
source, even of the same value, makes `page check` advise that the number needs another
look.

## Interactive and visual evidence

Use `lf-diagram` for a diagram in Mermaid syntax. It ships in the `diagram` package, so
create the page with `leaf page init --package diagram <page>`. `page check --render`
reports syntax errors and empty drawings; look at each rendered diagram to check it
shows the relationships it should. Without visual access, check the source's labels and
edges against the claims, state those claims in prose or a table beside it, and report
the diagram as unchecked (`page-checkpoints.md`, "Pre-handover review").

Draw what automatic layout can't place, such as a page layout, a wireframe or a
thumbnail inside an option, as an `svg.drawing` in a `<figure>` with an `id`, with
`data-width="wide"` when it needs the room. The figure scales the drawing to its width,
labels included, so make the `viewBox` close to the width it is shown at: 1600 units in
a 720px column draw an 11px label at 5px. Keep the drawing schematic: a window is a
rounded box, a line of text a grey bar, and only the figure's subject takes the accent
colour. Put compared states side by side in one figure at one scale, drawn alike except
where they differ, and use the `<figcaption>` for what the drawing can't show. The
idiom's classes follow the light and dark schemes, which an SVG file added with
`leaf page media` can't.

Use `lf-chart` for quantities rather than Mermaid's charts. A few numbers the sentence
can carry belong in prose.

A user can comment on a whole drawing. To let them comment on one part of an inline
`<svg>`, put an `id` on each `<g>` holding a shape and its label, named for what the
part is, since the thread reports it to you. The `lf-diagram` entry says which boxes
`parts="all"` makes commentable. A comment's mark stays where its part was when the
mark was drawn, so draw parts that move in a page widget that declares `x-visual` parts
(`module-annotations.md`, "Visual parts").

## Source files and media

Use `lf-text-document` to show a text file the user can comment on without copying it
into your HTML.

When the user reviews an edit to text, such as code, prose or configuration, show its
exact patch in `lf-diff` and explain the effect beside it. Consider including the patch
in updates on current work too. Choose the comparison that covers the work being
discussed; `wt step diff`, when available, often covers a branch. `lf-diff` ships in
the `diff` package: create the page with `leaf page init --package diff <page>`. Bind
each widget to a data source:

```html
<lf-text-document
  id="skill-source"
  source="leaf-skill"
  label="SKILL.md"
  language="markdown"
></lf-text-document>

<lf-diff id="review-patch" source="review-patch" collapsed><pre></pre></lf-diff>
```

Then set each source to one JSON string, of a whole file, a line range or a diff, and
run the pipeline again to refresh the open page:

```bash
jq -Rs . SKILL.md | leaf data set <page> leaf-skill
sed -n '71,102p' SKILL.md | jq -Rs . | leaf data set <page> leaf-skill
wt step diff | jq -Rs . | leaf data set <page> review-patch
```

`lf-diff` takes text changes with `@@` hunks and pure renames; describe binary,
mode-only and copied files in prose and leave them out. For a large patch whose files
should load only when opened, read the contract's producer instructions:

```bash
leaf page instructions <page> --contract unified-diff | jq -er '.producer'
```

A bound widget always shows its source's current value, in every version of the page
and every thread that quotes it. To keep evidence exactly as it was reviewed, give it
its own source id, such as `pr-patch-8f61c2a` for one commit's patch, and never write to
that id again. Evidence that should follow later `data set` calls shares one id.

Run `leaf page media <page> <file>…` and use each printed `/media/…` `path` for images,
video and audio; never inline media bytes. To let the reader zoom into an image, link it
to its own media URL: `<a href="/media/…"><img src="/media/…" alt="…"></a>`.

Keep each capture in its own image file; never join captures into one. Where captures
vary along named axes, such as the moment in an interaction, the case, the window width
or the colour scheme, put them in a `<table>` with one linked capture per cell, a
`<th scope="col">` naming each column's value and a `<th scope="row">` naming each
row's, so each axis is labelled once. Captures that show what each option of a decision
gives stand in their options instead (`authoring-decisions.md`). Place captures the
reader compares side by side or one above the other, so whatever moved shows as a
misalignment.

Use a recording for a fixed demo and a live widget where the user should operate the
subject. Show a browser journey recorded with Playwright as a trace in `lf-trace`
rather than a video, so the user can step through and comment on each action. `lf-trace`
ships in the `playwright` package; after `leaf page init --package playwright <page>`,
its author instructions cover comparable journeys and its producer instructions give
the import command:

```bash
leaf page instructions <page> --contract playwright-trace | jq -er '.producer'
```

Give `<video>` and `<audio>` `controls` and a label, and give a video a `poster`. Leaf
accepts MP4 and WebM video and MP3, M4A, Ogg and WAV audio. An export embeds each
recording whole, a third larger, so trim recordings to what the reader needs.

Put invented examples inside `lf-sample` and make them visibly fictional. Render
tickets, source locations and URLs as real links.

`lf-shot` shows two captures of an interface, before and after, taken at the same
viewport. It draws each capture across the column, so a capture of a whole window shows
well below its real size. For a smaller change, capture the subject in a reading column
rather than the whole window and crop both frames to the change, or show the element at
real size. Before writing the prose and `alt`, open both images and compare them where
the change should be.

Add `outlines` to outline what changed in each frame, and with a dashed line what only
moved. Leave it off where most outlines would mark something else, such as live data
that changed between captures, and say in the prose where to look. The pair's control
strip reads "identical", "only slight changes" or "changed throughout". If it reads
"identical", or no outline sits where the prose puts the change, capture a case that
shows the change or say that nothing changed. If it reads "only slight changes", name
the change in the prose, since the reader will hardly see it.

Add `pixels` when the reader must see exactly which pixels changed, such as a shift of a
few pixels, a subtle recolour or a claim that nothing else changed. It paints the
removed, added and recoloured pixels over the greyed after image, so build no
difference image of your own. Leave it off where the change reflows much of the frame.
