# Theme packages

Read with [packages.md](packages.md), which holds the package contract and how styles
compose. A theme is a page's look: a package whose rules style the page as a whole,
whether or not it also declares widgets. Defaults that Layouts and the page's sheet
should outrank, such as element rules, belong in `defaults.css`, in the layer with
Leaf's own defaults; rules meant to win over widget defaults and Layouts belong in
`overrides.css`. Idioms belong in either, declared in the package's registry.

## Personal themes

Leaf bundles one theme, `reading`: the reading look, which styles the body's type and
colour and the idioms such as `.callout`, and turns on the reading face markup wears
in Leaf's own surfaces (headings, prose, lists, tables, code, quotes, figures,
disclosures, definitions, rules and pictures) by setting `--lf-reading-face: 1` on the
root. The face's rules rank below every other rule of `lf-base`, so a theme's or
package's rule for one of those elements outranks them whatever its weight. A new page
takes it unless the user names another default. A page that takes none
(`--no-theme`) starts from the browser's defaults and Leaf's tokens: nothing of the
look reaches it, while Leaf's widgets, threads and panel keep their own faces. A page
or a theme may still set `--lf-reading-face: 1` on any box to give the markup in it
that face.

A user can also keep several named themes and choose one default. Each is an ordinary
installed package; its `instructions/author.md` describes the tasks it suits. Install
the package with `leaf package install <directory>`, then list its name in
`~/.config/leaf/themes.toml` (`$XDG_CONFIG_HOME/leaf/themes.toml` when set):

```toml
themes = ["editorial", "dense"]
default = "editorial"
```

A page takes one theme, so a personal theme is the page's whole look and replaces
`reading`. One that only adjusts the reading look, such as its palette, is selected
as a content package on a page that keeps `reading`: `leaf page init <page> --package
dense`.

`leaf theme list` returns the available choices, default and author instructions.
The author's selection follows the user's request first, then the task and those
instructions; leaving it unspecified uses the default on a new page. Select one with
`leaf page init <page> --theme dense`. Content packages remain independent; the
selected theme composes right after Leaf's default package and before them, so a
project package can restate a theme's idiom, such as `.callout`, and its rules win a
tie with the theme's.

A page captures its selected theme when initialized. Re-initializing preserves that
choice, even if the user's default changes; an explicit `--theme` replaces it.
`--no-theme` takes none, and a later plain init keeps none; `--no-packages` clears
only the content packages.
Developer fixture builders use an empty configuration home, so examples, the website
and demo recordings take `reading` rather than the developer's personal default.
`leaf page state <page>` exposes the effective name and whether it was explicit or
default under `layer.theme`.

A page records its theme's name, and the Leaf serving, checking or exporting it
composes the theme package it finds by that name, so each of those needs the package
installed; an export carries the theme's bytes. Live samples inherit their parent's
layer; a sample may deliberately show different theme inputs as a style reference
(`live-samples.md`). Applying the catalogue's current default to already-authored
pages remains a possible later change.

## A theme change

Shared inputs coordinate the page and its widgets: color palettes, radius `--r`, and
the three faces, `--serif` for prose, `--sans` for Leaf's chrome, injected controls and
notes on evidence, and `--mono` for literal evidence. The color pairs are described
under "Theme colors" below. An ordinary selector tunes one element. A
pattern the project reuses across pages, such as a callout, is an idiom: declare it
under its CSS selector in the package's `registry.json`, with a `description`, an
`x-example` and optional `x-instructions`, and style it in one of the package's sheets.

Where a Layout reads a geometry input (the "Theme inputs" table in `packages.md`,
"Styles and composition"), set that input rather than overriding the Layout.

A widget's rules depend only on the box it is given and the theme's tokens, never on
the Layout around it. A
size query on its own container gives its width. What a width can't say arrives as a
token from the box that knows it: `--lf-full-height` where the widget has a definite
height to fill (`module-scroll-and-motion.md`, "Reading regions"), and
`--lf-density: working` under the `density-working` style.

The body supplies `--lf-ground`: the browser's `Canvas`, or `var(--paper)` under the
reading theme, which paints the body that colour; a theme or page that paints its own
ground sets it to match. Each solid containing surface
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
A grid or flex box whose items stack, as the reading column's do, declares
`--lf-items-keep-margins: 1`: each item keeps its children's margins inside its box, so
Leaf gives an item opening with a heading the heading's gap as its own margin, and its
box starts at the heading.

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

Leaf rings every box that holds visible focus, at a control's gap outside it. A box
whose ring belongs elsewhere states its own `outline-offset`, in its face's rule, as the
token of its kind (`base.css`, "Where it stands"): `--focus-region-gap` for a block of
the page, `0` for a box that draws its own edge, and `--focus-ring-inset` for a row
packed edge to edge with others or a box whose clip leaves no room outside it. Leaf's
marks over the page read the same value where it isn't `0`, so a comment's or an aim's
frame stands where the ring does.

A rule that draws a control's focus ring on a box around it, such as a choice's face
holding its radio and words, declares `--lf-wears-ring: 1` beside the ring, so Leaf
scrolls that box rather than the control into view with room for its ring.

Turn off a widget's interactive styling inside `[data-lf-exhibit]`, where it is quoted
rather than offered. An export inlines the stylesheet and opens offline, so use fonts on
the user's machine, not remote ones.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).

## Leaf's chrome

Leaf's panel, thread cards and comment box take the page's look through its tokens, so
a theme or page that sets `--paper`, `--ink`, `--sans` or `--r` on `:root` changes them
with the page. To restyle one of them alone, name it by its part:

| Part       | Surface                                             |
| ---------- | --------------------------------------------------- |
| `panel`    | the floating panel at the window's foot             |
| `card`     | a thread card                                       |
| `composer` | the comment box, and the choices a selection offers |

Tokens set on a part change that surface alone, whether a theme's sheet or the page's
own CSS sets them: `[part~="card"] { --paper: #fffdf5; --r-l: 4px; }` gives thread
cards their own ground and corners. Each part resolves the chrome's fonts again
(`--font-*`, `base.css`), so a face or rung set on it, such as `--sans` or `--t-5`,
reaches every word the surface shows. Other values Leaf derives on the root keep the
root's reading, so set them on the part beside their input, as `--focus-ring` and
`--focus-shadow` beside `--accent`. Leaf draws each surface's ground, ring, corners and
shadow from these tokens, and places and sizes the surface itself, so restyle those
through tokens rather than `background`, `border` or a position.

Any other property, such as `letter-spacing` or `display`, goes in the package's
`chrome.css`. Leaf nests each of its style rules in the chrome's root, as if written
inside `.lf-chrome { … }`, with more weight than any of the chrome's own selectors, so
the rule wins over the chrome's stylesheet rules whatever selectors either writes and
reaches nothing outside the chrome. A selector keyed on the page around the chrome
therefore places `&` for its root: `html.dark & [part~="panel"]`. The rule still loses
to a style Leaf's script sets on an element, and to Leaf's few `!important`
declarations, such as its borders in forced colours. A rule the sheet puts inside
`@layer` loses to the chrome's rules too. Other at-rules, such as `@keyframes` and
`@font-face`, are global, as anywhere in CSS, and a sheet holding `@scope` is refused,
since Leaf already scopes it.

```css
[part~="panel"],
[part~="card"] {
  --sans: var(--mono);
  --r-l: 0;
}
[part~="panel"] {
  letter-spacing: -0.01em;
}
```

The comment box and threads a widget seats in an outlet of its own
(`x-thread-surface`), as `lf-diff` and `lf-visual-review` do, stand outside the chrome
and take the widget's look rather than the theme's `chrome.css`. The part names are
the chrome's public interface. Its classes are private and change between Leaf
versions, so a rule naming one can stop applying after an update. A page that restyles
the chrome beyond tokens does it through a package of its own, named beside every
package the page keeps: `leaf page init <page> --package diff --package ./chrome-look`.

## Theme colors

Use independent inputs where the foreground and background need a deliberate contrast
choice. The default palette is declared in `browser/base.css`:

| Surface                  | Inputs                                                                                                                                                                                |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Page and raised surfaces | `--paper`, `--card`, `--field`; `--ink`, `--ink-2`, `--muted`; `--rule`, `--border-2`                                                                                                 |
| Interactive emphasis     | `--accent`; focus ring and shadow derive from it at their declaration scope                                                                                                           |
| Status                   | `--ok`, `--warn`, `--danger` for markers; each has independent `-ink` and `-tint` inputs for text and ground                                                                          |
| Pins                     | `--pin-fill` with `--pin-ink`; the user's turn uses `--pin-on-user` with `--pin-on-user-ink`                                                                                          |
| Code                     | `--code-bg`, `--pre-bg`, `--code-chrome`, `--code-ink`, `--code-muted`, `--code-border`; `--syn-comment`, `--syn-keyword`, `--syn-string`, `--syn-number`, `--syn-name`, `--syn-type` |

Changing `--accent` does not choose the pin pair or the status palette. Check the
foreground against each ground where it is used, in both color schemes. A theme may
set `light-dark()` values so the browser's scheme preference selects the palette.
Subtree overrides follow normal CSS inheritance: when changing an input locally,
redeclare any derived value needed there, such as `--focus-ring` and `--focus-shadow`.
Keep the inherited `--lf-ground` surface contract described above so opaque nested
controls match their containing surface.
