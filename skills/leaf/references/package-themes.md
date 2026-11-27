# Theme packages

Read with [packages.md](packages.md), which holds the package contract and how styles
compose. A theme is a page's look: a package whose rules style the page as a whole,
whether or not it also declares widgets. Its rules for the page's own content, such
as element rules and the tokens it sets on `:root`, belong in `theme.css`, below
Layouts, Leaf's rules for what it draws and the page's `base` layer, so a page's CSS
framework outranks them as it would any site's theme. Its rules for what
Leaf draws, such as an idiom's or a widget's look, belong in `defaults.css`, and rules
meant to win over widget defaults and Layouts in `overrides.css`. Idioms are declared
in the package's registry.

## A page's theme

A page's theme is one of the packages it selects. Leaf composes the packages a page
lists, in that order, and adds no theme of its own, so a page that selects none starts
from the browser's defaults, as `page-authoring.md`, "Style the page", describes.

A theme styles the page's own native controls as well as its markup, so they stand
beside Leaf's controls as one set. Leaf bundles one theme, `reading`: the reading look,
which styles the body's type and colour and turns on the reading face markup wears in
Leaf's own surfaces (headings, prose, lists, tables,
code, quotes, figures, disclosures, definitions, rules and pictures, with a wide table
scrolling inside itself, a code block's long lines wrapping, and a `language-…` code
block coloured by its tokens) by setting `--lf-reading-face: 1` on the root. The face
also gives the page's own buttons, fields and labelled choices the faces of Leaf's own
controls (the vocabulary's `button` and `input, select` entries), while a control Leaf
builds keeps its own. The face's rules rank below every other rule of `lf-theme`, so a
theme's or package's rule for one of those elements outranks them whatever its weight,
and another theme restyles the page's controls through the tokens they read or with
rules of its own. A page or a theme may still set
`--lf-reading-face: 1` on any box to give the markup in it that face, and
`--lf-reading-face: initial` on a box takes the face from the markup in it, as for
content with its own design inside a themed page; comments still anchor there. Each of
the face's rules reads the element's parent, so the box itself still wears the face: set
the input on a wrapper around the table or code block, not on it.

A theme of your own is an ordinary package, often a single `theme.css`. How the
page selects it decides what the theme has to state:

- To build on `reading`, the page selects `reading` and then the theme: `leaf page init
  <page> --package reading --package dense`. A later package's rule wins a tie with an
  earlier one's, so the theme states only what it changes, such as its three colours, a
  face and a corner.
- To replace `reading`, the page selects the theme without it: `leaf page init <page>
  --package editorial`. The theme then states the whole look.

Either way its pages keep Leaf's idioms, such as `.lf-callout` and `.lf-tag`, which
Leaf draws on every page. Leaf's rules for them stand in `lf-base`, above the page's
`base` layer and every rule of a theme's `theme.css`, and below every other rule of
`lf-base`, so a theme restyles an idiom from its `defaults.css`, where a rule for the
idiom's element, such as `.lf-tag` or `dl.lf-facts dt`, outranks Leaf's whatever its
weight.

Select a page's theme ahead of its other packages, so that a package's rule wins a tie
with the theme's and a project package can restate what the theme declares.
Re-initializing a page with `--package` replaces every package it selects, its theme
among them, so name the theme again with each package the page keeps.

A theme's `instructions/author.md` opens by saying when to select it and whether it
follows `reading` or replaces it, and `leaf package list` prints that paragraph beside
every other package the machine can select. The author's selection follows the user's
request first, then the task and those instructions. A theme the user wants on every
page is one they install with `leaf package install <directory>`: have its `author.md`
say so, and save the preference in your harness's memory, where later sessions read it
(the main skill's "Follow the user's preferences").

To try a theme while writing it, select its directory, which needs no install: `leaf
page init <page> --package reading --package ./my-theme`.

A page records the names of the packages it selects, and the Leaf serving, checking or
exporting it composes the packages it finds by those names. So a theme selected by name
has to be installed wherever the page is served, checked or exported, while one
selected by path is copied into the page (`packages.md`, "Package reach"). An export
carries the theme's rules. Live samples inherit their parent's layer; a sample may
deliberately show different theme inputs as a style reference (`live-samples.md`).

## A theme change

Shared tokens coordinate the page and its widgets ("Theme tokens" below). Three colours
carry a palette: `--lf-paper`, the page's ground, `--lf-ink`, its text, and
`--lf-accent`. Leaf steps the neutral colours of every surface from the paper toward the
ink, so a theme that sets the three recolours the page, its widgets and Leaf's chrome
together, and restates a neutral only where it wants another. The three faces are
`--lf-serif` for prose, `--lf-sans` for Leaf's chrome, injected controls and notes on
evidence, and `--lf-mono` for literal evidence, and `--lf-r` sets every corner. An
ordinary selector tunes one element. A pattern the project reuses across pages, such as
a callout, is an idiom: declare it under its CSS selector in the package's
`registry.json`, with a `description`, an `example` and optional
`instructions`, and style it in one of the package's sheets.

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
selects no theme paints `html` the same way. The reading theme paints `body` in it too,
so a theme built on `reading` draws a texture behind the page on `body`, since one on
`html` alone lies under the body's ground. Each solid containing surface
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

A box that frames a drawing in the drawing's own coordinates, such as a capture shown
at full size or a timeline panned inside its viewport, declares `--lf-drawing: 1`. The
render check then reads content the box cuts as the drawing's framing, and still
reports a control the user can't reach there.

Shared CSS selects widgets by what their registry entries declare, which delivery
writes onto each element as `[data-lf-space]`, `[data-lf-bound]`, `[data-lf-height]`,
`[data-lf-exhibit]` and similar attributes, rather than by tag. An element that names
page media also arrives with `data-lf-media-width` and `data-lf-media-height`, the
largest width and height among its images, so a widget can size its frame before they
decode, as `lf-shot` does.

The page decides how wide it is and how its blocks are arranged (`page-layout.md`,
"Layouts"). A package's element fills its box. One that needs more room than the reading
measure, such as a board or a diagram, declares it in `space`: `wide` or
`available`. One read as lines of text, such as a list of choices, keeps the prose's
line length on a wide page with `max-inline-size: var(--lf-measure)` in its own
stylesheet, under `@media screen`. Only the column and sidebar Layouts apply
`space`. A workspace states no measure, so there every element fills its region.

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
needs nothing: Leaf fades its content at any edge with more beyond. A box can
change the fade, as a diagram does: `--lf-more-fade` sets how deep it runs, and
`--lf-more-fade-to`, a colour, sets by its alpha how much of the content still shows
at the edge.

Leaf rings every box that holds visible focus, at a control's gap outside it, and its
own word and symbol presses one band inside their edge. A box
whose ring belongs elsewhere declares `--lf-ring-at` in its face's rule, as the token of
its kind (`styles/tokens.css`, "Where it stands"): `--lf-focus-region-gap` for a block of the page,
`--lf-focus-ring-gap`, a control's gap, for a box on which a rule of yours draws a
control's ring, where the ring would otherwise stand on the box's edge,
`0` for a box that draws its own edge, and `--lf-focus-ring-inset` for a row packed edge to
edge with others or a box whose clip leaves no room outside it. Leaf draws every mark
on a box as the box's own outline there, over any outline your rules give the box while
the mark shows, so a comment's or an aim's brackets stand where the ring does. The
brackets are a `clip-path` Leaf sets on the box, so a rule of yours that sets its
`clip-path` replaces them. `--lf-ring-at` does not inherit. A rule that keeps room
for a ring reads how far the ring reaches outside its box: `--lf-focus-ring-room`
for a control's ring and `--lf-focus-region-room` for a block's.

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
link underline, which follows the root's `--lf-accent`, the focus ring, which follows
its `--lf-ok`, and the raise shadows, which follow its `--lf-shade`. Set the ones the
part should change beside the token they follow, such as `--lf-card` beside
`--lf-paper`, and `--lf-focus-ring` and `--lf-focus-shadow` beside `--lf-ok`. Leaf draws each
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
(`threadOutlets`), as `lf-diff` does, stand outside the chrome
and take the widget's look rather than the theme's `chrome.css`. The part names are
the chrome's public interface. Its classes are private and change between Leaf
versions, so a rule naming one can stop applying after an update. A page that restyles
the chrome beyond tokens does it through a package of its own, named beside every
package the page keeps: `leaf page init <page> --package reading --package diff
--package ./chrome-look`.

## Theme tokens

These are the custom properties a page, a theme or a package sets or reads to share
Leaf's look. Leaf declares each on the root (`browser/styles/tokens.css`). Set one
there to change it for the page and everything Leaf draws on it, or on a subtree to
change it for that subtree. Any other `--lf-` property is Leaf's own. `leaf package check`
advises on each property a package's sheet reads with `var()` and no fallback that
nothing in Leaf, the package or the layer it composes sets, as a renamed token leaves.

A theme sets these colours. Where the foreground and background need a deliberate
contrast choice, they are independent tokens:

| Role             | Tokens                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| The page         | `--lf-paper`, its ground; `--lf-ink`, its text; `--lf-accent`, for links and the chosen item. With no theme the first two are the browser's canvas and text                                                                                                                                                                                                                                                    |
| Status           | `--lf-ok`, `--lf-warn`, `--lf-danger` for markers; `--lf-ok-ink`, `--lf-warn-ink`, `--lf-danger-ink` for text                                                                                                                                                                                                                                                                                                  |
| Code             | `--lf-pre-bg`, `--lf-code-chrome`, `--lf-code-ink`, `--lf-code-muted`, `--lf-code-border` for a block, while inline code stands on `--lf-chip`; `--lf-code-scheme`, `dark` or `light`, draws every code block in that scheme whatever the page's, each token in it taking that scheme's `light-dark()` branch; setting the code tokens alone leaves the status inks and highlights inside in the page's scheme |
| Syntax           | `--lf-syn-comment`, `--lf-syn-keyword`, `--lf-syn-string`, `--lf-syn-number`, `--lf-syn-name`, `--lf-syn-type`                                                                                                                                                                                                                                                                                                 |
| A chart's series | `--lf-series-1`, `--lf-series-2`, `--lf-series-3`, `--lf-series-4`, `--lf-series-5`                                                                                                                                                                                                                                                                                                                            |

Leaf derives these from the colours above, the neutrals as steps from `--lf-paper`
toward `--lf-ink`, so they follow a palette that sets those. A page's or package's
rules read them, and a theme restates one it wants otherwise:

| Token                                                | Draws                                                                                                      |
| ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `--lf-card`                                          | A raised surface: a card, a panel, a control                                                               |
| `--lf-field`                                         | A tinted ground: a field, a callout                                                                        |
| `--lf-chip`                                          | A neutral chip's ground, and inline code's                                                                 |
| `--lf-rule`                                          | A hairline between rows or parts                                                                           |
| `--lf-border`                                        | A control's or a box's edge                                                                                |
| `--lf-muted`                                         | Words that qualify a line: a caption, a status, a hint                                                     |
| `--lf-quiet`                                         | Words standing in for what isn't there yet: an empty box's hint                                            |
| `--lf-ink-2`                                         | Secondary text, between the ink and `--lf-muted`                                                           |
| `--lf-accent-tint`                                   | The ground under an accented press, from `--lf-accent`                                                     |
| `--lf-link-underline`                                | A link's underline, which stands `--lf-link-underline-offset` below its words                              |
| `--lf-offer-hover-shadow`                            | The wash under a press the pointer is over, as an inset `box-shadow`                                       |
| `--lf-ok-tint`, `--lf-warn-tint`, `--lf-danger-tint` | A status's ground, from the paper and that status's colour, which an added and a removed line stand on too |
| `--lf-hi-tint`                                       | The ground of a highlighted line                                                                           |

Leaf's own marks wear these roles rather than tokens of their own, so a theme recolours
a mark by setting its role. The user's marks wear `--lf-ok`: focus, the location ring,
the aim, a thread in their turn and what is On me, whose count on the folded leaf
carries `--lf-paper` digits on `--lf-ok-ink`. The agent's wear `--lf-accent`: a
thread's marker, the agent at work and a reply the user hasn't read. What changed since
the version compared wears `--lf-muted`, and what the user chose or finished wears
`--lf-ink-2`, with `--lf-ink` words on `--lf-chip`. A pin wears a margin entry's paper,
`--lf-border` and the status inks.

Type, space and shape:

| Role             | Tokens                                                                                                                                                                                                                                                                                                                                                         |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Faces            | `--lf-serif` for prose, `--lf-sans` for labels and controls, `--lf-mono` for code                                                                                                                                                                                                                                                                              |
| Sizes            | `--lf-t-1`, the title's, down through `--lf-t-2`, `--lf-t-3`, `--lf-t-4`, the body's, `--lf-t-5`, `--lf-t-working-label`, `--lf-t-6` and `--lf-t-7`, in `rem`; `--lf-code-size` and `--lf-code-line` for source; `--lf-code-inline-size`, inline code's size against the words around it                                                                       |
| A widget's words | A whole font for the `font` shorthand, by kind (`packages.md`, "Styles and composition"): `--lf-font-ui`, `--lf-font-widget`, `--lf-font-small`, `--lf-font-title`, `--lf-font-heading`, `--lf-font-status`, `--lf-font-compact`, `--lf-font-choice`, `--lf-font-chip`, `--lf-font-fine`, `--lf-font-code`, `--lf-font-message`                                |
| Spacing          | `--lf-sp-1` to `--lf-sp-5`: 4, 8, 16, 24 and 32px, through `--lf-sp-2`, `--lf-sp-3` and `--lf-sp-4`; `--lf-clear`, the least room that stands a box clear of its frame's edge; `--lf-list-inset`, how far a list's items stand in; `--lf-chip-pad`, a chip's padding                                                                                           |
| Corners          | `--lf-r`, a control's or box's; `--lf-r-s`, half of it, for a mark no taller than a line; `--lf-r-l`, twice it, for a surface floating over the page; `--lf-r-in`, for a box that meets a hairline frame's edge from inside it                                                                                                                                 |
| Lift             | `--lf-raise-1`, `--lf-raise-2`, `--lf-raise-3`, the shadow of a box lying on the page, opening over it, or standing over it for a task, each cast in `--lf-shade`; `--lf-raise-1-drop` and `--lf-raise-1-blur`, how far the first falls and spreads: a theme changes that lift by setting them, and a box reads them to keep room for it                       |
| Controls         | `--lf-line`, a one-line control's height; `--lf-aim-floor`, the smallest box a user aims at, larger under a finger; `--lf-reach-room`, the room a control's reach takes past its face; `--lf-choice-gap`, the room between a radio's or checkbox's mark and its words; `--lf-chooser`, the height of a radio group drawn as buttons, such as a choice of views |
| Focus            | `--lf-focus-ring` as an outline and `--lf-focus-shadow` as a shadow, set together; where a ring stands is `--lf-ring-at` ("A theme change")                                                                                                                                                                                                                    |
| Page geometry    | `--lf-col`, the reading column; `--lf-wide`, a wide block; `--lf-sidebar` and `--lf-aside`, a sidebar's and a note's track; `--lf-page-pad-start` and `--lf-page-pad-end`, the room above and below the page; `--lf-view-height`, the window's height less `--lf-head-room`                                                                                    |
| Motion           | `--lf-motion-fold`, the time a removed item's room takes to close or a frame takes to return from an editor to its reading; `--lf-motion-disclosure`, a disclosure opening or a control fading in; `--lf-motion-mark`, a mark moving to where it now stands                                                                                                    |

Changing `--lf-accent` does not choose the status palette. Check
the foreground against each ground where it is used, in both color schemes. `page check
--render` draws the light scheme only, so read the dark one on the served page in a
browser set to dark. A theme may set `light-dark()` values so the browser's scheme
preference selects the palette. Subtree overrides follow normal CSS inheritance: when
changing a token locally, redeclare any value stepped from it that is needed there,
such as `--lf-card` after `--lf-paper`, and `--lf-focus-ring` and `--lf-focus-shadow`
after `--lf-ok`. Keep the inherited `--lf-ground` surface contract described above
so opaque nested controls match their containing surface.
