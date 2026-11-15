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
disclosures, definitions, rules and pictures, with a wide table or code block
scrolling inside itself and a `language-…` code block coloured by its tokens) by
setting `--lf-reading-face: 1` on the root. The face's rules rank below every other
rule of `lf-base`, so a theme's or package's rule for one of those elements outranks
them whatever its weight. A new page takes it unless the user names another default.
A page that takes none (`--no-theme`) starts from the browser's defaults and Leaf's
tokens: nothing of the look reaches it, its tables and code blocks included, while
Leaf's widgets, threads and panel keep their own faces, in the browser's own canvas
and text colours until the page sets `--lf-paper` and `--lf-ink`. A page or a theme may still
set `--lf-reading-face: 1` on any box to give the markup in it that face, and
`--lf-reading-face: initial` on a box takes the face from the markup in it, as for
content with its own design inside a themed page; comments still anchor there.
Each of the face's rules reads the element's parent, so the box itself still wears
the face: set the input on a wrapper around the table or code block, not on it.

A user can also keep several named themes and choose one default. Each is an ordinary
installed package; its `instructions/author.md` describes the tasks it suits. Install
the package with `leaf package install <directory>`, then list its name in
`~/.config/leaf/themes.toml` (`$XDG_CONFIG_HOME/leaf/themes.toml` when set):

```toml
themes = ["editorial", "dense"]
default = "editorial"
```

A personal theme builds on the reading look: `reading` composes first and the theme
after it, so a theme states only what it changes, such as its three colours, a face
and a corner, and its pages keep the look's idioms, such as `.callout` and `.tag`. A
theme's rule wins a tie with the reading look's. A look that wants none of `reading`
is a content package on a page that takes no theme: `leaf page init <page> --no-theme
--package dense`.

`leaf theme list` returns the available choices, default and author instructions.
The author's selection follows the user's request first, then the task and those
instructions; leaving it unspecified uses the default on a new page. Select one with
`leaf page init <page> --theme dense`. Content packages remain independent; the
reading look and the selected theme compose right after Leaf's default package and
before them, so a
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

Shared tokens coordinate the page and its widgets ("Theme tokens" below). Three
colours carry a palette: `--lf-paper`, the page's ground, `--lf-ink`, its text, and
`--lf-accent`. Leaf steps the neutral colours of every surface from the paper toward
the ink, so a theme that sets the three recolours the page, its widgets and Leaf's
chrome together, and restates a neutral only where it wants another. The three faces
are `--lf-serif` for prose, `--lf-sans` for Leaf's chrome, injected controls and
notes on evidence, and `--lf-mono` for literal evidence, and `--lf-r` sets every
corner. An ordinary selector tunes one element. A
pattern the project reuses across pages, such as a callout, is an idiom: declare it
under its CSS selector in the package's `registry.json`, with a `description`, an
`x-example` and optional `x-instructions`, and style it in one of the package's sheets.

Where a Layout reads a page geometry token ("Theme tokens" below), set that token
rather than overriding the Layout.

A widget's rules depend only on the box it is given and the theme's tokens, never on
the Layout around it. A
size query on its own container gives its width. What a width can't say arrives as a
token from the box that knows it: `--lf-full-height` where the widget has a definite
height to fill (`module-scroll-and-motion.md`, "Reading regions"), and
`--lf-density: working` under the `density-working` style.

The root supplies `--lf-ground` to the page and Leaf's surfaces alike: the page's
`--lf-paper`, which is the browser's `Canvas` until a theme or the page sets it. The
reading theme paints the window that colour, and a look of your own on a page that
takes no theme paints `html` the same way. Each solid containing surface
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

Leaf rings every box that holds visible focus, at a control's gap outside it. A box
whose ring belongs elsewhere declares `--lf-ring-at` in its face's rule, as the token of
its kind (`styles/tokens.css`, "Where it stands"): `--lf-focus-region-gap` for a block of the page,
`0` for a box that draws its own edge, and `--lf-focus-ring-inset` for a row packed edge to
edge with others or a box whose clip leaves no room outside it. Leaf draws every mark
on a box as the box's own outline there, over any outline your rules give the box while
the mark shows, so a comment's or an aim's brackets stand where the ring does. The
brackets are a `clip-path` Leaf sets on the box, so a rule of yours that sets its
`clip-path` replaces them. The declaration does not inherit.

A rule that draws a control's focus ring on a box around it, such as a choice's face
holding its radio and words, reads the box's `data-lf-control-focus-visible`, which Leaf
writes on the box the control names with `--lf-focus-box`
([module-input.md, "Focus and layers"](module-input.md#focus-and-layers)). It declares
`--lf-wears-ring: 1` beside the ring, so Leaf scrolls that box rather than the control
into view with room for its ring.

Where the positioned content a box holds would paint over its own ring, as a scroller's
positioned lines do, Leaf can draw the ring one band inside the box's edge on a later
box, its `::after`. Give the box the class `lf-ring-overlay` to ring it there when it
holds focus itself, or give the box around it the class `lf-ring-frame` to ring it
there when that box's child holds focus; a frame declares `--lf-wears-ring` itself.
Either box must be positioned, such as `position: relative`, or the ring covers the
nearest positioned box around it instead. A rule of yours on its `::after` sets the
ring's `z-index` over what the box holds, and where the ring stands when that isn't
the box's edge.

Turn off a widget's interactive styling inside `[data-lf-exhibit]`, where it is quoted
rather than offered. An export inlines the stylesheet and opens offline, so use fonts on
the user's machine, not remote ones.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).

## Leaf's chrome

Leaf's panel, thread cards and comment box take the page's look through its tokens, so
a theme or page that sets `--lf-paper`, `--lf-ink`, `--lf-sans` or `--lf-r` on `:root` changes them
with the page. To restyle one of them alone, name it by its part:

| Part       | Surface                                             |
| ---------- | --------------------------------------------------- |
| `panel`    | the floating panel at the window's foot             |
| `card`     | a thread card                                       |
| `composer` | the comment box, and the choices a selection offers |

Tokens set on a part change that surface alone, whether a theme's sheet or the page's
own CSS sets them: `[part~="card"] { --lf-paper: #fffdf5; --lf-r-l: 4px; }` gives thread
cards their own ground and corners. Each part resolves the chrome's fonts again
(`--lf-font-*`, `styles/tokens.css`), so a face or rung set on it, such as `--lf-sans` or `--lf-t-5`,
reaches every word the surface shows. Other values Leaf derives on the root keep the
root's reading on a part: the neutrals stepped from the root's paper and ink, the
focus ring and link underline, which follow the root's `--lf-accent`, and the raise
shadows, which follow its `--lf-shade`. Set the ones the part should change beside
the token they follow, such as `--lf-card` beside `--lf-paper`, and
`--lf-focus-ring` and `--lf-focus-shadow` beside `--lf-accent`. Leaf draws each
surface's ground, ring, corners and shadow from these tokens, and places and sizes the
surface itself, so restyle those through tokens rather than `background`, `border`, a
position or a transform. The panel's ground is a second box carrying the `panel`
part, so a property such as `opacity` or `backdrop-filter` set on the part applies to both.

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
  --lf-sans: var(--lf-mono);
  --lf-r-l: 0;
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

## Theme tokens

These are the custom properties a page, a theme or a package sets or reads to share
Leaf's look. Leaf declares each on the root (`browser/styles/tokens.css`). Set one
there to change it for the page and everything Leaf draws on it, or on a subtree to
change it for that subtree. Any other `--lf-` property is Leaf's own.

A theme sets these colours. Where the foreground and background need a deliberate
contrast choice, they are independent tokens:

| Role             | Tokens                                                                                                                                                             |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| The page         | `--lf-paper`, its ground; `--lf-ink`, its text; `--lf-accent`, for links, focus and the chosen item. With no theme the first two are the browser's canvas and text |
| Status           | `--lf-ok`, `--lf-warn`, `--lf-danger` for markers; `--lf-ok-ink`, `--lf-warn-ink`, `--lf-danger-ink` for text                                                      |
| Counts           | `--lf-badge-fill` with `--lf-badge-ink`, for the count on the folded leaf; pins wear the margin entries' paper, `--lf-border` and status inks                      |
| Code             | `--lf-code-bg` for inline code; `--lf-pre-bg`, `--lf-code-chrome`, `--lf-code-ink`, `--lf-code-muted`, `--lf-code-border` for a block                              |
| Syntax           | `--lf-syn-comment`, `--lf-syn-keyword`, `--lf-syn-string`, `--lf-syn-number`, `--lf-syn-name`, `--lf-syn-type`                                                     |
| A chart's series | `--lf-series-1`, `--lf-series-2`, `--lf-series-3`, `--lf-series-4`, `--lf-series-5`                                                                                |

Leaf derives these from the colours above, the neutrals as steps from `--lf-paper`
toward `--lf-ink`, so they follow a palette that sets those. A page's or package's
rules read them, and a theme restates one it wants otherwise:

| Token                                                | Draws                                                      |
| ---------------------------------------------------- | ---------------------------------------------------------- |
| `--lf-card`                                          | A raised surface: a card, a panel, a control               |
| `--lf-field`                                         | A tinted ground: a field, a callout                        |
| `--lf-chip`                                          | A neutral chip's ground                                    |
| `--lf-rule`                                          | A hairline between rows or parts                           |
| `--lf-border`                                        | A control's or a box's edge                                |
| `--lf-muted`                                         | Words that qualify a line: a caption, a status, a hint     |
| `--lf-ink-2`                                         | Secondary text, between the ink and `--lf-muted`           |
| `--lf-accent-tint`                                   | The ground under an accented press, from `--lf-accent`     |
| `--lf-ok-tint`, `--lf-warn-tint`, `--lf-danger-tint` | A status's ground, from the paper and that status's colour |
| `--lf-add-tint`, `--lf-del-tint`, `--lf-hi-tint`     | The ground of an added, a removed and a highlighted line   |

Type, space and shape:

| Role             | Tokens                                                                                                                                                                                                                                                                                                                                                                |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Faces            | `--lf-serif` for prose, `--lf-sans` for labels and controls, `--lf-mono` for code                                                                                                                                                                                                                                                                                     |
| Sizes            | `--lf-t-1`, the title's, down through `--lf-t-2`, `--lf-t-3`, `--lf-t-4`, the body's, `--lf-t-5`, `--lf-t-working-label`, `--lf-t-6` and `--lf-t-7`, in `rem`; `--lf-code-size` and `--lf-code-line` for source                                                                                                                                                       |
| A widget's words | A whole font for the `font` shorthand, by kind (`packages.md`, "Styles and composition"): `--lf-font-ui`, `--lf-font-widget`, `--lf-font-small`, `--lf-font-title`, `--lf-font-heading`, `--lf-font-label`, `--lf-font-status`, `--lf-font-compact`, `--lf-font-choice`, `--lf-font-chip`, `--lf-font-count`, `--lf-font-fine`, `--lf-font-code`, `--lf-font-message` |
| Spacing          | `--lf-sp-1` to `--lf-sp-5`: 4, 8, 16, 24 and 32px, through `--lf-sp-2`, `--lf-sp-3` and `--lf-sp-4`                                                                                                                                                                                                                                                                   |
| Corners          | `--lf-r`, a control's or box's; `--lf-r-s`, half of it, for a mark no taller than a line; `--lf-r-l`, twice it, for a surface floating over the page                                                                                                                                                                                                                  |
| Lift             | `--lf-raise-1`, `--lf-raise-2`, `--lf-raise-3`, the shadow of a box lying on the page, opening over it, or standing over it for a task, each cast in `--lf-shade`                                                                                                                                                                                                     |
| Controls         | `--lf-line`, a one-line control's height; `--lf-aim-floor`, the smallest box a user aims at, larger under a finger; `--lf-reach-room`, the room a control's reach takes past its face                                                                                                                                                                                 |
| Focus            | `--lf-focus-ring` as an outline and `--lf-focus-shadow` as a shadow, set together; where a ring stands is `--lf-ring-at` ("A theme change")                                                                                                                                                                                                                           |
| Page geometry    | `--lf-col`, the reading column; `--lf-wide`, a wide block; `--lf-sidebar` and `--lf-aside`, a sidebar's and a note's track; `--lf-page-pad-start` and `--lf-page-pad-end`, the room above and below the page                                                                                                                                                          |

Changing `--lf-accent` does not choose the count's pair or the status palette. Check
the foreground against each ground where it is used, in both color schemes. A theme
may set `light-dark()` values so the browser's scheme preference selects the palette.
Subtree overrides follow normal CSS inheritance: when changing a token locally,
redeclare any value stepped from it that is needed there, such as `--lf-card` after
`--lf-paper`, and `--lf-focus-ring` and `--lf-focus-shadow` after `--lf-accent`. Keep
the inherited `--lf-ground` surface contract described above so opaque nested controls
match their containing surface.
