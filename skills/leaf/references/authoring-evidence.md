# Interactive and external evidence

## Measured facts

Use `lf-num` for a repeatably measured number inside a sentence, as its entry shows.

The value stays as you wrote it. Any later write to the source, even of the same value,
makes `page check` advise that the number needs another look. Use one source id per
measurement, and plain HTML for numbers with no repeatable source.

## Interactive and visual evidence

For an existing interface, capture the relevant panel, card or menu with enough
surrounding background to preserve its whole shadow. Crop or mark the capture so
the eye lands on the point, cutting through background rather than text. Use
`lf-shot` for before-and-after captures and a table for captures that vary along
other axes ("Source files and media").

Use `lf-diagram` for Mermaid syntax rendered by Pele. It ships in the `diagram`
package, so create the page with `leaf page init --package diagram <page>`.
`page check --render` reports
syntax errors and empty drawings; look at each rendered diagram to check it shows the
relationships it should. Without visual access, check the source's labels and edges
against the claims, state those claims in prose or a table beside it, and report the
diagram as unchecked (`page-checkpoints.md`, "Pre-handover review").

Draw what automatic layout can't place, such as a page layout, a wireframe or a
thumbnail inside an option, as the `svg.drawing` idiom in a `<figure>` with an `id`,
with `data-width="wide"` when it needs the room. The figure scales the drawing to its
width, labels included, so make the `viewBox` close to the width it is shown at: 1600
units in a 720px column draw an 11px label at 5px. Keep the drawing schematic: a window is a
rounded box, a line of text a grey bar, and only the figure's subject takes the accent
colour. Put compared states side by side in one figure at one scale, drawn alike except
where they differ. The idiom's classes use theme tokens, so the drawing follows light
and dark schemes; an SVG file added with `leaf page media` can't. Use the
`<figcaption>` for what the drawing can't show.

Use `lf-chart` for quantities, not Mermaid's charts. Keep a few numbers in prose
when a sentence explains them clearly. For experiments, show each variant beside its
baseline on a shared scale, with the changed text or setting beside its effect.

Use `lf-timeline` for an order of events between actors that you describe, such as a
race between two jobs, rather than drawing one in `svg.drawing`: it places every label
clear of bars, other labels and the playhead, and the reader steps through the events
with the keyboard or a finger. It ships in the `timeline` package. A recorded browser
journey belongs in `lf-trace` instead (below).

A user can comment on a whole drawing. To let them comment on one part, give the part
an id: in an inline `<svg>`, put an `id` on each `<g>` holding a shape and its label,
named for what the part is, since the thread reports it to you. For `lf-diagram`, its
entry says which boxes `parts="all"` makes commentable.

A comment's mark stays where its part was when the mark was drawn, so a part that moves
leaves its mark behind. Draw moving parts in a page widget that declares `x-visual`
parts (`module-annotations.md`, "Visual parts").

## Source files and media

Use `lf-text-document` to show a text file the user can comment on without copying it
into your HTML.

When the user reviews an edit to text, such as code, prose or configuration, show its
exact patch in `lf-diff` and explain the effect beside it. Choose the comparison that covers the work being
discussed; `wt step diff`, when available, often covers a branch.
`lf-diff` ships in the `diff` package: create the page with
`leaf page init --package diff <page>`. Bind each widget to a data source:

```html
<lf-text-document
  id="skill-source"
  source="leaf-skill"
  label="SKILL.md"
  language="markdown"
></lf-text-document>

<lf-diff id="review-patch" source="review-patch" collapsed><pre></pre></lf-diff>
```

Then set each source to one JSON string, of a whole file, a line range, or a diff:

```bash
jq -Rs . SKILL.md | leaf data set <page> leaf-skill
sed -n '71,102p' SKILL.md | jq -Rs . | leaf data set <page> leaf-skill
wt step diff | jq -Rs . | leaf data set <page> review-patch
```

Run the pipeline again to refresh the open page. Keep the complete Git patch, including
file-operation metadata: files without textual hunks still have commentable rows.
For a large patch, use the manifest producer described by the contract:

```bash
leaf page instructions <page> --contract unified-diff | jq -er '.producer'
```

A bound widget always shows its source's current value, in every version of the page
and every thread that quotes it. To keep evidence exactly as it was reviewed, give it
its own source id, such as `pr-patch-8f61c2a` for one commit's patch, and never write to
that id again. Evidence that should follow later `data set` calls shares one id.

Run `leaf page media <page> <file>…`, naming each file as its own argument as a glob
such as `shots/*.png` does, and use each printed `/media/…` `path` for images, video
and audio; never inline media bytes. To let the reader zoom into an image, link it
to its own media URL: `<a href="/media/…"><img src="/media/…" alt="…"></a>`.
The reading theme gives every image a thin outline and shadow, so its boundary remains visible
when the image and page have the same background colour. To remove that treatment,
for example from a badge or transparent logo, give the image
`box-shadow: none; border-radius: 0` in the page's CSS.

Keep each capture in its own image file; never join captures into one. Where captures
vary along named axes, such as the moment in an interaction, the case, the window width
or the colour scheme, put them in a `<table>` with one linked capture per cell, a
`<th scope="col">` naming each column's value and a `<th scope="row">` naming each
row's, so each axis is labelled once. Captures of an option's outcome go inside that
option, in such a table where there are several (`authoring-on-me.md`). Place
captures the reader compares side by side or one above the other, so whatever moved
shows as a misalignment.

Use a recording for a fixed demo and a live widget where the user should operate the
subject. Show a browser journey recorded with Playwright as a trace in `lf-trace`
rather than a video, so the user can step through and comment on each action. `lf-trace`
ships in the `playwright` package; after `leaf page init --package playwright <page>`,
its author instructions own the convention for comparable journeys; its producer
instructions give the import command:

```bash
leaf page instructions <page> --contract playwright-trace | jq -er '.producer'
```

Give `<video>` and `<audio>` `controls` and a label, and give a video a `poster`.
For recordings compared inside `lf-motion`, use its shared transport as the motion
package's author instructions describe. Leaf
accepts MP4 and WebM video and MP3, M4A, Ogg and WAV audio. An export embeds each
recording whole, a third larger, so trim recordings to what the reader needs.

Put invented examples inside `lf-sample` and make them visibly fictional.

`lf-shot` shows two versions of an interface, before and after, captured at the same
viewport. Before writing the prose and `alt`, open both images and compare them where
the change should be. For a small change, crop both frames to the subject rather than
making the reader search a whole window. Check the pair as it first appears: Fit
may shrink the captures to fit the available space. Choose crops and page space that make
the relevant change readable there, without requiring the reader to zoom first.

Every pair starts in **Slider**, followed by **Pair** and **Pixels** in the shared
header. Before and After label the header, or each frame when stacked. Pair keeps
the captures at the same scale; clicking either image opens its original. Fit places them beside one another or stacks
them, whichever draws them larger, so short wide captures stack and tall narrow ones sit
side by side; stacked frames fit together within the screen or the comparison's height limit. At 100%, both panes stay visible and scrolling either image moves
the other to the same location. This scale uses CSS pixels when capture metadata
supplies the pixel ratio, or bitmap pixels otherwise. The **…** menu offers Fit,
100%, the Changed pixels color key and, for a pair with focus metadata, Full frame to inspect
beyond that region. Outline changes stays beside the menu.

In Slider, click or tap the image to alternate between the complete Before and After
frames. Drag the divider for an intermediate comparison, or focus it and use the
arrow keys; Home and End show the complete frames.

**Outline changes** marks changed regions in Pair and Slider, using the accent color
for content that only moved. **Pixels** paints changed pixels amber over the greyed after image, softly for
small changes and more strongly for large ones, so build no difference image of your
own. It locates differences without inferring what was added or removed. These controls belong to the reader; author the pair with `before`,
`after` and `alt`.

The comparison reports identical images, slight changes or changes throughout the
frame. If it reports identical images, or no outline sits where the prose puts the
change, capture a case that shows the change or say that nothing changed. Name subtle
changes in the prose. Where live data changed between captures, say where to look.
