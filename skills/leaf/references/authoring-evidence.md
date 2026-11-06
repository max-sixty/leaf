# Interactive and external evidence

## Measured facts

Use `lf-num` for a repeatably measured number inside a sentence, as its entry shows,
and plain HTML for numbers with no repeatable source.

## Interactive and visual evidence

For an existing interface, capture the relevant panel, card or menu with enough
surrounding background to preserve its whole shadow. Crop or mark the capture so
the eye lands on the point, cutting through background rather than text. Use
`lf-shot` for before-and-after captures; its instructions cover preparing the pair and
the comparison controls. Capture both versions at the same viewport. Before writing
the prose and `alt`, open both images and compare them where the change should be.
For a small change, crop both frames to the subject rather than making the reader
search a whole window. Captures that vary along other axes need each axis labelled
once, which a table does by default ("Source files and media").

Use `lf-diagram` for Mermaid syntax rendered by Pele. It ships in the `diagram`
package, so create the page with `leaf page init --package diagram <page>`. Its
instructions cover checking the drawing and reporting what you could verify.

Draw what automatic layout can't place, such as a page layout, a wireframe or a
thumbnail inside an option, as the `svg.drawing` idiom in a `<figure>` with an `id`,
with `data-width="wide"` when it needs the room. The figure scales the drawing to its
width, labels included, so make the `viewBox` close to the width it is shown at: 1600
units in a 720px column draw an 11px label at 5px. Draw only the detail the figure's
point needs, so its subject stands out, and give the accent colour to the subject
alone. Where the drawing shows wording or an interface that is itself being decided,
draw it as the product shows it, so the reader judges the real thing. Draw compared
states in one figure at one scale, alike except where they differ, side by side or one
above the other, whichever keeps the difference large and lined up. The idiom's
classes use theme tokens, so the drawing follows light and dark schemes; an SVG file
added with `leaf page media` can't. Use the `<figcaption>` for what the drawing can't
show.

Use `lf-chart` for quantities, not Mermaid's charts. Keep a few numbers in prose
when a sentence explains them clearly.

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

Use `lf-text-document` to show a text file or quoted passage the user can comment on.
When the user reviews an edit to code, prose or configuration, show its exact patch
in `lf-diff` and explain the effect beside it. Choose the comparison that covers the
work being discussed; `wt step diff`, when available, often covers a branch.
`lf-diff` ships in the `diff` package: create the page with
`leaf page init --package diff <page>`. The widget and package author instructions own
markup, source binding and patch preparation.

Choose whether evidence should follow the current source or preserve what was
reviewed. A bound widget always shows its source's current value, in every version
of the page and every thread that quotes it. For a fixed review, embed the evidence
as the widget's instructions describe, or give it a source id you never update.
Evidence that should follow later `data set` calls shares one id.

For example, a file and its patch reviewed at one commit each need fixed evidence:
give the file and the patch their own source ids and never overwrite either. A live
working-file view instead keeps its source id as the file changes. The same choice
of evidence lifetime applies whichever widget presents it.

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
or the colour scheme, the reader should be able to tell each capture's value on every
axis from where it stands rather than from prose away from the images, with each axis
labelled once. The default is a `<table>` with one linked capture per cell, a
`<th scope="col">` naming each column's value and a `<th scope="row">` naming each
row's. Captures of an option's outcome go inside that option, in such a table where
there are several (`authoring-on-me.md`). Place captures the reader compares side by
side or one above the other, so whatever moved shows as a misalignment.

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
