# Theme packages

Read with [packages.md](packages.md), which holds the package contract and how styles compose.

## A theme change

Tokens change every surface that reads them: `--accent`, `--r`, the three faces
`--serif` (body prose), `--sans` (apparatus: chrome, injected controls, and annotations
embedded in evidence), and `--mono` (literal evidence). Ordinary selectors tune one
element or widget. A shape the project reuses across pages is an idiom — declare it
under its CSS selector in the package's `registry.json`, beside element names
(a `description`, `x-example`, and optional `x-instructions`) and style it in the layer's
`theme.css`; the page's merged `registry.json` then carries it beside the shipped ones.
An idiom may also declare `x-space`, the width it takes, as `.callout` keeps
the column; delivery paints it on every element the selector matches.

A package that declares widgets has its whole sheet scoped to them, below the Layouts,
so page-wide rules and idioms belong in a theme package, one that declares none. A
theme package's rules rank above the Layouts and every widget package's defaults
(`packages.md`, "Styles and composition"), so it restyles a Layout or a widget on every page as the
page's own stylesheet does on one. Where a Layout reads a page geometry input (the
override table's "Theme inputs"), setting the input changes it with less CSS.

A package's rules read the box a widget is given and the theme's tokens, never the Layout
or style class around it, so a widget behaves the same in a shipped Layout as on a page
whose own CSS gives it the same box. A size query on the widget's own container answers
its width. What a width cannot say arrives as a token its owner sets: `--lf-full-height`
on the box that gives the widget a definite height to fill (`module-scroll-and-motion.md`,
"Reading regions"), and `--lf-density: working` under the `density-working` style.

A rule that draws a box's inset — padding, border, or tinted field — declares
`--lf-block-frame: 1` in the same rule. The shared layout uses that declaration to trim child
margins, bound wide content, and stretch a table to the frame. A box whose edges keep its
children's margins in but which draws nothing, as a page tab's panel or a box that contains
floats does, declares `--lf-block-frame: trim` instead, so its edges trim while wide content
in it takes the page's room and a table in it keeps to its content. The trim follows the frame's edge down through each
first or last child, so a wrapper between the frame and the margin it trims declares
nothing. A box that lays its children
out side by side (a flex row, a grid) declares `--lf-holds-edge: 1`, so the trim stops at
it rather than taking one item's margin and leaving the others'.

Delivery paints declared layout facts into the served document as `[data-lf-inline]`,
`[data-lf-space]`, `[data-lf-bound]`, `[data-lf-height]`, `[data-lf-exhibit]`, and
`[data-lf-views]`, `[data-lf-content]`, and `[data-lf-verbatim]`; shared selectors read those attributes instead of naming widget
tags. The registry's `$keys` entries for `x-space`, `x-bound`, and `x-height` say what
each declaration requests; none of them chooses the widget's internal layout, which the
package arranges inside the allocation.
An element whose attributes name page media also arrives with the largest width and the
largest height among those images, read from their bytes, as `data-lf-media-width` and
`data-lf-media-height`, so a theme can give a frame the images' shape before they decode
(`aspect-ratio: attr(data-lf-media-width type(<number>)) / attr(data-lf-media-height
type(<number>))`, as `lf-shot` does).
How wide the page is, and how its blocks are arranged, is the page's choice, made with a
Layout class or its own CSS (`page-layout.md`, "Layouts"); a package's element fills
the box it is given, and its `x-space` states the width it prefers, which a page may
override. Declare `column` for an element whose content is read as lines of text, such
as a list of choices or a timeline, so in a flow wider than the column, such as a
sidebar page's body, it keeps the measure the prose around it keeps instead of
stretching its rows across the page. Only the column and the sidebar page allocate
`x-space`; in a workspace every element fills the region it stands in.
A widget that needs a minimum width to stay usable, such as a board's columns at a
readable size, states it as `min-inline-size` capped by the box it stands in:
`min(<its floor>, 100%, 100cqi, var(--lf-box-cap, 100vw))`. `100%` is the box it
stands in, such as a workspace's grid cell; `100cqi` measures the nearest size
container, which is the page's shell or a framed box around the widget (a pane's body, a
card), and a sample, which cannot be one, states `--lf-box-cap`. So in a box
narrower than the floor the widget scrolls sideways rather than widening the page.
Choose vertical bounds by the task need in
`page-layout.md`, "Bounds and widths", including a widget's `x-bound` default.
When a bounded widget's scroller should be a box inside it, such as a listing under a
caption that stays in view, the package theme moves the bound there under
`[data-lf-bound]` and declares `--lf-bound-box: 1` on that box, which is the one Leaf
registers as the block's reading region and keeps on its newest entry, and
`--lf-holds-height: 1`, which says the box holds its height on purpose (`packages.md`, "Seeing it",
`grows-with-content`). A box a
package scrolls sideways needs no declaration of its own: the runtime
measures every scroller on each layout and marks each edge with content beyond it.
Leaf fades the content at those edges, so a widget that has to scroll says so without
the package writing anything. An interactive
affordance stands down inside `[data-lf-exhibit]`, where the widget is quoted rather
than offered. The stylesheet is
inlined into an export, which opens offline, so use fonts available on the user's
machine rather than a remote font.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).
