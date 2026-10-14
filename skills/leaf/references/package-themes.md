# Theme packages

Read with [packages.md](packages.md), which holds the package contract and how styles compose.

## A theme change

To change every surface at once, set a token: `--accent`, `--r`, or one of the three
faces, `--serif` for prose, `--sans` for Leaf's chrome, injected controls and notes on
evidence, and `--mono` for literal evidence. An ordinary selector tunes one element. A
pattern the project reuses across pages, such as a callout, is an idiom: declare it
under its CSS selector in the package's `registry.json`, with a `description`, an
`x-example` and optional `x-instructions`, and style it in the package's `theme.css`. An
idiom may declare `x-space`, the width it takes, as `.callout` keeps to the column.

Page-wide rules and idioms belong in a theme package, one that declares no widgets. A
package that declares widgets has its stylesheet scoped to them, below the Layouts,
while a theme package's rules take priority over the Layouts and every widget package's
defaults (`packages.md`, "Styles and composition"). Where a Layout reads a geometry
input (the override table's "Theme inputs"), set that input rather than overriding the
Layout.

A widget's rules depend only on the box it is given and the theme's tokens, never on
the Layout around it, so it behaves the same on any page that gives it the same box. A
size query on its own container gives its width. What a width can't say arrives as a
token from the box that knows it: `--lf-full-height` where the widget has a definite
height to fill (`module-scroll-and-motion.md`, "Reading regions"), and
`--lf-density: working` under the `density-working` style.

A rule that draws an inset around a box, with padding, a border or a tinted background,
also declares `--lf-block-frame: 1`. Leaf then trims the first child's top margin and the
last child's bottom margin, keeps wide content inside the frame, and stretches a table
to its width. A box that keeps its children's margins in but draws nothing, such as a
page tab's panel or a box that contains floats, declares `--lf-block-frame: trim`: its
edge margins are trimmed, but wide content may take the page's width and a table keeps
its natural width. The trim reaches through a plain wrapper at the edge, which declares
nothing. A flex row or grid declares `--lf-holds-edge: 1` to stop the trim, which would
otherwise take its first item's margin and not its neighbours'.

Shared CSS selects widgets by what their registry entries declare, which delivery
writes onto each element as `[data-lf-space]`, `[data-lf-bound]`, `[data-lf-height]`,
`[data-lf-exhibit]` and similar attributes, rather than by tag. An element that names
page media also arrives with `data-lf-media-width` and `data-lf-media-height`, the
largest width and height among its images, so a theme can give the frame their shape
before they load, as `lf-shot` does with `aspect-ratio`.

The page decides how wide it is and how its blocks are arranged (`page-layout.md`,
"Layouts"). A package's element fills its box, and its `x-space` states the width it
prefers. Declare `column` for an element read as lines of text, such as a list of
choices, so on a wide page it keeps the prose's line length. Only the column and sidebar
Layouts apply `x-space`; in a workspace every element fills its region.

A widget that needs a minimum width, such as a board whose columns must stay readable,
caps it by the space it is in: `min-inline-size: min(<floor>, 100%, 100cqi,
var(--lf-box-cap, 100vw))`. `100%` is its box, `100cqi` the nearest size container such
as a pane's body or a card, and `--lf-box-cap` stands in where there is none, as in a
live sample. In a narrower box the widget then scrolls sideways rather than widening the
page.

Choose vertical bounds as `page-layout.md`, "Bounds and widths", describes. Where a
bounded widget should scroll a box inside it, such as a listing under a caption that
stays in view, move the bound to that box under `[data-lf-bound]` and declare
`--lf-bound-box: 1` there, making it the box Leaf scrolls and keeps the user's place in,
and `--lf-holds-height: 1`, which tells the render check the box keeps its height on
purpose (`packages.md`, "Seeing it", `grows-with-content`). A box that scrolls sideways
needs nothing: Leaf fades its content at any edge with more beyond.

Turn off a widget's interactive styling inside `[data-lf-exhibit]`, where it is quoted
rather than offered. An export inlines the stylesheet and opens offline, so use fonts on
the user's machine, not remote ones.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).
