# Theme packages

Read with [packages.md](packages.md), which holds the package contract and how styles
compose. Page-wide rules and idioms belong in a theme package, one that declares no
widgets; its rules outrank the Layouts and every widget package's defaults.

## A theme change

To change every surface at once, set a token: `--accent`, `--r`, or one of the three
faces, `--serif` for prose, `--sans` for Leaf's chrome, injected controls and notes on
evidence, and `--mono` for literal evidence. An ordinary selector tunes one element. A
pattern the project reuses across pages, such as a callout, is an idiom: declare it
under its CSS selector in the package's `registry.json`, with a `description`, an
`x-example` and optional `x-instructions`, and style it in the package's `theme.css`.

Where a Layout reads a geometry
input (the override table's "Theme inputs"), set that input rather than overriding the
Layout.

A widget's rules depend only on the box it is given and the theme's tokens, never on
the Layout around it. A
size query on its own container gives its width. What a width can't say arrives as a
token from the box that knows it: `--lf-full-height` where the widget has a definite
height to fill (`module-scroll-and-motion.md`, "Reading regions"), and
`--lf-density: working` under the `density-working` style.

The body supplies `--lf-ground: var(--paper)`. Each solid containing surface
overrides `--lf-ground`; both it and its opaque controls paint
`background: var(--lf-ground)`. Hover and selection states change the same token. Transparent
wrappers inherit it; a surface becoming transparent restores `--lf-ground: inherit`.
This color describes a solid background, not an image or gradient.

A rule that draws an inset around a box, with padding, a border or a tinted background,
also declares `--lf-block-frame: 1`. Leaf then trims the first child's top margin and the
last child's bottom margin and keeps wide content inside the frame. A box that keeps its
children's margins in but draws nothing, such as a page tab's panel or a box that
contains floats, declares `--lf-block-frame: trim`: its edge margins are trimmed, but
wide content may take the page's width. The trim reaches through a plain wrapper at the
edge, which declares nothing. A flex row or grid declares `--lf-holds-edge: 1` to stop
the trim, which would otherwise take its first item's margin and not its neighbours'.

Shared CSS selects widgets by what their registry entries declare, which delivery
writes onto each element as `[data-lf-space]`, `[data-lf-bound]`, `[data-lf-height]`,
`[data-lf-exhibit]` and similar attributes, rather than by tag. An element that names
page media also arrives with `data-lf-media-width` and `data-lf-media-height`, the
largest width and height among its images, so a theme can give the frame their shape
before they load, as `lf-shot` does with `aspect-ratio`.

The page decides how wide it is and how its blocks are arranged (`page-layout.md`,
"Layouts"). A package's element fills its box. One that needs more room than the
reading measure, such as a board or a diagram, declares it in `x-space`: `wide` or
`available`. One read as lines of text, such as a list of choices, keeps the prose's line
length on a wide page with `max-inline-size: var(--lf-measure)` in its own stylesheet,
under `@media screen`. Only the column and sidebar Layouts apply `x-space`. A workspace
states no measure, so there every element fills its region.

A widget that needs a minimum width, such as a board whose columns must stay readable,
caps it by the space it is in: `min-inline-size: min(<floor>, 100%, 100cqi,
var(--lf-box-cap, 100vw))`. `100%` is its box, `100cqi` the nearest size container such
as a pane's body or a card, and `--lf-box-cap` stands in where there is none, as in a
live sample. In a narrower box the widget then scrolls sideways rather than widening the
page.

Choose vertical bounds as `page-layout.md`, "Bounds and widths", describes. Where a
bounded widget should scroll a box inside it, such as a listing under a caption that
stays in view, move the bound to that box under `[data-lf-bound]`. On the bounded host,
declare `--lf-bound-box` as a selector within it, such as `.listing`.
Leaf scrolls and keeps the user's place in the first match outside nested bounds,
or in the host while no match exists. The declaration does not inherit. Declare
`--lf-holds-height: 1` on the scrolling box (`packages.md`, "Seeing it",
`grows-with-content`). A box that scrolls sideways
needs nothing: Leaf fades its content at any edge with more beyond.

A rule that draws a control's focus ring on a box around it, such as a choice's face
holding its radio and words, declares `--lf-wears-ring: 1` beside the ring, so Leaf
scrolls that box rather than the control into view with room for its ring.

Turn off a widget's interactive styling inside `[data-lf-exhibit]`, where it is quoted
rather than offered. An export inlines the stylesheet and opens offline, so use fonts on
the user's machine, not remote ones.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).
