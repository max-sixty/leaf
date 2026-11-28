# Packages

A package is a directory Leaf adds to a page. It can hold a theme, widgets, helper
modules, libraries and external-data contracts. `page init` records the selected
packages and checks their composition. The Leaf serving, checking or exporting a page
composes its layer from that selection ("Package reach", below).
Packages need no browser build or npm command: write widgets and helpers as
JavaScript the browser loads directly, importing the shipped `/runtime/widget-api.js`.
[Rendering](module-authoring.md#rendering) describes the widget lifecycle.

This file covers what every package follows and how to declare a widget.
[package-themes.md](package-themes.md) covers packages that change the theme, and
[package-data.md](package-data.md) the state a widget records, references between
widgets, and external data.
[module-authoring.md, "The interface"](module-authoring.md#the-interface) maps each
kind of thing a package leans on Leaf for to the reference that describes it.

## Package reach

Leaf's bundled `default` package is on every page; any other package is on only the
pages that select it. Presentation or behavior used by one page stays in that page's
`<style>`, its scripts or `page/`. Anything reused belongs in a package:

```bash
leaf package init packages/signoff --widget lf-signoff
leaf package check packages/signoff
leaf page init --package reading --package packages/signoff PAGE
leaf package install packages/signoff
leaf package list
leaf package run NAME SCRIPT [ARGS]...
```

`package init` creates the package's `registry.json` and `defaults.css`, which are all
a CSS-only widget needs, and often all a theme does. Each `--widget TAG` adds a
working starter under that tag, a yes-or-no choice: its declaration, its module at
`widgets/<tag>.js` and its rule in `defaults.css`. The starter is a small widget that
records what the user presses (`module-widgets.md`), there to be changed into
the widget you need: each of its three parts is yours to rewrite, or to delete where
your widget needs none.

`--package` takes a name of lowercase letters, digits and hyphens, which selects an
installed or bundled package, or a path. A path is relative to the directory `page
init` runs in or starts with `~`, as `./pkg`, `pkg/` and `'~/.config/leaf'` do; a bare
`pkg` reads as a name. Absolute paths are refused, since the page's registry is public.
`page init` copies a package selected by path into the page's `packages/`, so the
page reads the same wherever it is served; run `page init --package` again to take
in edits to the package.

`leaf package install SOURCE` checks the directory and copies it into
`~/.local/state/leaf/packages/` under the directory's own name, so `--package NAME`
selects it by that name from any project on this machine. The copy holds only the files
in the package layout below, so a README and tests stay behind. An installed package
overrides a bundled one of the same name. A page records the bare name, and every Leaf
that reads the page composes the package it finds by that name, so serving the page on
another machine needs the package installed there too.

`leaf package list` prints each package a page can select by name, bundled or
installed: its `description`, the first paragraph of its author instructions, and the
description of each entry it declares. Choose a package by what those say it is for.

Packages declare no dependencies on each other; a page lists every package it needs.

## Package contract

Every package uses this layout, and every file is optional:

```text
package/
├── registry.json       element declarations and shared $ declarations
├── theme.css           a theme's rules for the page's own content
├── defaults.css        defaults for what Leaf draws, its widgets' among them
├── widget-shadow.css   widget defaults also loaded in their shadow trees
├── overrides.css       page-wide rules that outrank every package's defaults
├── chrome.css          rules restyling Leaf's panel, thread cards and comment box
├── instructions/       Markdown instructions named for their audiences
├── runtime/            package-owned browser modules
├── widgets/            entry modules and their private helpers
├── vendor/             third-party libraries or data files
├── scripts/            command-line tools `leaf package run` runs; never vendored
├── icon.svg            optional replacement by path
```

### Widget interface

Keep a widget simple: show the evidence and actions the reader needs, since every extra
control competes with them. Add an optional control when a caller needs it, and let
the page's author turn it on. Use the theme's tokens and shared control styles before
writing widget CSS, build each press by its role so it wears Leaf's face
(`module-controls.md`), give its other parts Leaf's faces by their classes
(`module-controls.md`, "Faces for a widget's parts"), and reuse Leaf's thread symbol, comment
box and keyboard hints (`module-input.md`, "Commands and keyboard routes", and
`module-annotations.md`, "Widget-local Thread placement").

### Styles and composition

Choose a stylesheet by the contribution it makes. A package may supply any combination;
adding a widget does not change its theme styling.

| Sheet               | Document                           | Declared shadow trees                 | A page without Leaf |
| ------------------- | ---------------------------------- | ------------------------------------- | ------------------- |
| `theme.css`         | `lf-theme`                         | A thread's transcript, in `lf-shadow` | —                   |
| `defaults.css`      | `lf-base`                          | A thread's transcript, in `lf-shadow` | `lf-base`           |
| `widget-shadow.css` | `lf-base`                          | `lf-shadow`                           | `lf-base`           |
| `overrides.css`     | Page-wide in `lf-overrides`        | —                                     | —                   |
| `chrome.css`        | Leaf's chrome, above its own rules | —                                     | —                   |

A widget can seat a thread in its shadow tree, as a diff does a line's, so a declared
shadow tree takes `theme.css` and `defaults.css` within `@scope (.lf-thread-transcript)`,
in `lf-shadow` after its `widget-shadow.css`, as they follow that sheet in the document: a message's
markup wears the same look there as in the document, and the widget's own elements take
none of it.

A page without Leaf links the layer's `portable.css`, served beside `/widgets/`, for
its widgets' look (`module-authoring.md`, "A widget that also runs off Leaf"). It holds
the theme's tokens, Web Awesome's tokens that Leaf's faces read, Leaf's faces for what
widgets build, kept to the widgets' insides,
and the `defaults.css` and `widget-shadow.css` of each package that ships widgets, so
a theme's rules stay out and the page's own markup keeps its look. The rules stand in `lf-base`, so the page's
own unlayered CSS outranks them and restyles its widgets by restating a token such as
`--lf-accent`, and its `color-scheme` picks their colours. A page with a ground and
text colour of its own sets `--lf-paper` and `--lf-ink` to them, from which the
widgets' neutral colours step (`package-themes.md`, "Theme tokens").

Leaf ranks a rule by whose element it styles. A theme's rules for the page's own
content go in `theme.css`, in `lf-theme`, below the page's `base` layer.
Defaults for what Leaf draws, a widget's own and a theme's for an idiom, go in
`defaults.css`, in `lf-base`; `overrides.css` ranks above them and the Layouts. The
document orders the page's `reset`, `lf-reset`, `lf-theme`, the page's `base`,
`lf-base`, `lf-layouts`, `lf-overrides`, `lf-state`, then the page's other layers and
unlayered rules (`page-layout.md`, "Page CSS and Leaf's controls"). A shadow tree orders `lf-reset`, `lf-base`, `lf-layouts`,
`lf-shadow`, `lf-overrides`, `lf-state`; Layouts don't reach inside it. A shared
shadow sheet precedes its document-only sheet; later selected packages win ties. A
package's `defaults.css` and `overrides.css` reach the controls in Leaf's panel and
thread cards too, so a rule there names what it styles, such as `body button`. Use
public inputs and selectors to customise a widget, not `!important` or inline styles.

A package's sheet can be split into files: `@import "./styles/tabs.css";`, optionally
with `layer(name)`, names a file inside the package, and composition puts that file's
rules where the import stands, so the page receives one sheet and edits need no build.

An element with `hidden` is always `display: none`, in the document and in shadow
trees, except `hidden="until-found"`. Give a box that must stay laid out while unseen a
state of its own.

Leaf's chrome and comment marks are unlayered, so change their colours and type
through the theme inputs below, and restyle the chrome's surfaces by part in
`chrome.css` (`package-themes.md`, "Leaf's chrome"). Put a dependency's default styles in
`@layer lf-base { … }` (`module-authoring.md`, "Shadow stages and styles").

Leaf places each sheet in its tier and changes none of its rules but `chrome.css`'s,
which it nests in the chrome, so a sheet names
the widgets it styles: `lf-tag .part` in the document, and `:host(lf-tag) .part` in a
shadow tree, where `:host(lf-tag.ready)` reads the host's state. A bare `p { … }`
reaches every paragraph on the page, and in a shadow sheet everything the tree holds,
including Leaf's views placed there, such as a diff's threads. A rule naming a widget
also reaches a foreign widget nested inside it, so style structure a nested widget may
share through a child combinator or the package's own classes. Replacing a widget's
declaration or module does not withdraw the selected package's stylesheet
contribution. Inherited values cross every widget boundary. Adjust another widget's
internals through its inputs or API; overrides are deliberately page-wide.

Document selectors don't reach into a shadow root. A declared `shadow` root gets
the composed shared stylesheet when its element says `lf-connect`, or through
`shadowStage` for an imperative renderer (`module-authoring.md`, "Shadow stages and
styles"). Use theme inputs for changes across
both trees, `widget-shadow.css` for owned internals, and `::part` to expose a public
control.

Custom properties come in four kinds:

| Kind                 | Owner and supported use                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Theme tokens         | Page authors and themes set them on the root, or on a subtree, and a page's or package's rules read them: colours, faces, type, spacing, corners and page geometry, listed in `package-themes.md`, "Theme tokens". Markup's reading face is the declaration `--lf-reading-face: 1` (`package-themes.md`, "A page's theme"). A value Leaf steps from another token is computed on the root, so setting the token on a subtree doesn't change a stepped value it inherits. |
| Facts about a box    | The box that allocates space sets them for what it holds, and a rule inside reads them: `--lf-full-height` and `--lf-density`, as `package-themes.md`, "A theme change", describes, and a Layout's facts below. Leaf also writes values it measures, such as `--lf-root-headers` and anchor geometry. Read those; don't set them.                                                                                                                                        |
| Declarations to Leaf | A rule sets them on its own box for Leaf to read, such as `--lf-block-frame` and `--lf-holds-edge`, as `package-themes.md`, "A theme change", describes.                                                                                                                                                                                                                                                                                                                 |
| Vendor bridges       | An adapter maps Leaf inputs to a dependency's properties, such as `--diffs-*` and `--plot-background`. Change the Leaf input, not each use.                                                                                                                                                                                                                                                                                                                              |

A Layout declares further facts about the boxes it arranges. A rule reads one with a
style query on a container of the element it styles, or with `var()` where it is a
length. `--lf-layout-box` doesn't inherit, so a module reads it off the box itself.
The page's body is the size container `lf-shell`, whose width a rule asks with
`@container lf-shell (width < 640px)`.

| Declaration            | The Layout declares it on                                            | It says                                                   |
| ---------------------- | -------------------------------------------------------------------- | --------------------------------------------------------- |
| `--lf-layout-box: 1`   | the box it arranges                                                  | the box carries a Layout                                  |
| `--lf-wide-page: 1`    | a sidebar page, with `0` on a reading column inside it               | the box is as wide as the window                          |
| `--lf-track-beside: 1` | a sidebar's `layout-track`                                           | the track stands beside the body; `0` once it has wrapped |
| `--lf-track-room`      | a sidebar, and the parent of a track, in a window 480px tall or more | the height a track that sticks may take                   |

Leaf's interface sets its words in a closed set of fonts derived from those tokens,
each a whole value for the `font` shorthand, declared together in
`browser/styles/tokens.css` beside what each one sets. A widget's own words, such as
its controls, statuses, counts, labels and readouts, and the sentences it holds, such
as a card's, name the font for their kind (`font: var(--lf-font-small)`,
`font: var(--lf-font-widget)`) rather than a size, line height or family of their own. They then match Leaf's at
every density and under every theme, and a page doesn't collect faces a pixel or a
weight apart from the ones Leaf already draws. The fonts for one line of words, such as
`--lf-font-ui`, `--lf-font-compact` and `--lf-font-small`, share one line height, the
number `--lf-ui-lh`, which a box multiplies by the font's size to keep room for a line.

Every custom property Leaf declares starts with `--lf-`, so none meets a name a page
or its framework coins. A page, theme or package may rely on those these references
name; any other is Leaf's own and can change in any update. A package
documents any further inputs it supports. No type or colour override may shrink a
control below its touch target or focus clearance.

A package's `icon.svg`, `widgets/` and `vendor/` files replace files at the same path.
Import Leaf behavior through `/runtime/widget-api.js`, or its portable part
`/runtime/portable-api.js` (module-authoring.md, "A widget that also runs off Leaf"),
and shared web code from the library under `/runtime/lib/` (module-authoring.md,
"Shared web code"). All are files of the install: `leaf --root` prints its directory, which holds them in
`browser/runtime/` and Leaf's `/vendor/` modules in `browser/vendor/`. A link from
these references to a file under `browser/` or `src/` leads into that directory.
Package `runtime/` modules can add paths but not replace the kernel's. The Leaf serving a page supplies its runtime,
`widget-api.js` and the kernel's `vendor/` modules included, and composes the page's
packages from its own catalogue, so a package runs against the runtime of whichever
Leaf serves its page, and a package's `vendor/` file at one of those paths replaces it
there. `widget-api.js` can change in any update; `leaf package check --render` and
`leaf page check --render` report a module it breaks.

Registries merge in order: kernel, `default`, then the selected packages in command
order, and a later package wins a collision. A later package replaces an element or
idiom entry whole and can't delete one. Shared `$` entries merge by member, and a map
member merges one level further by key; `null` deletes at either level if the merged
registry still validates. `page init` records the selected packages in
`$layer.packages`, and a plain re-init selects them again. Re-initializing with
`--package` replaces that list, so name every package the page keeps.
`page init --no-packages PAGE` clears the list. A page's theme is one of the
packages it selects
([package-themes.md, "A page's theme"](package-themes.md#a-pages-theme)).

Name each file directly under `instructions/` `<audience>.md`, matching
`[a-z][a-z0-9-]*\.md`, and start it with its text rather than a title: Leaf adds a
heading naming the package. `author.md` opens with a paragraph saying when to select
the package; `leaf package list` prints it as the package's `description`. Packages
define their own audiences, such as `author` or `worker`, and files for the same
audience join in package order. A data contract's `instructions` map holds text per
audience beside its schema, and a registry entry's `instructions` is one string for
the page author.

```bash
leaf page instructions PAGE --contract unified-diff | jq -er '.producer'
```

`leaf page instructions` returns a JSON map from audience to text. With no selection it
returns the packages' shared instructions. Each `--use ENTRY` adds that entry's
`instructions` to `author`, along with the entries its `example` uses and the
contracts its `inputs` and `outputs` name, whose instructions join their own
audiences. It reads the layer the page selects and any `page/registry.json`, so it
works before the page has markup. `page-authoring.md`, "Read the registry", says when
an author reads each part.

A replacement `icon.svg` must contain an element with `class="lf-tone"`, which Leaf
colours with the page's status.

## A widget

A registry key declares a widget when it is `lf-` followed by hyphen-separated words of
lowercase letters and digits, such as `lf-merge-film`. Leaf reads any other key that
doesn't start with `$` as an idiom's CSS selector, so a widget declared as `merge-film`
is refused as an idiom holding keys an idiom can't have.

An element declaration holds the JSON Schema of the element's attributes under
`attributes`, and beside it each fact that says how Leaf treats the tag, such as
`content`, its action `verbs`, whether it `awaits` the user on On Me, its `owners`, and
its typed `inputs`. Each is declared because some part of Leaf, such as the server or
`page check`, needs it without running the widget's module:

```json
"lf-merge-film": {
  "description": "A merge replayed frame by frame.",
  "attributes": { "required": ["id"] },
  "content": "members",
  "example": "<lf-merge-film id=\"film\">…</lf-merge-film>"
}
```

The merged registry's `$keys` entry defines each fact by its name and the values it
takes (`leaf page vocabulary PAGE | jq '."$keys"'`); `$verbs` defines the members of
`verbs`, and `$awaits` an obligation's answer. What the module alone can answer stays in the module, as a word
for its kind that depends on the element is its `lfWord()`. So does a rule about the
widget's markup that no declared fact states: the module checks it as it draws and
reports a breach with an `error` event
([module-authoring.md, "Upgrade"](module-authoring.md#upgrade)). Every declaration has
a `description` saying what the widget is for and when to use it, and a valid
`example`. The optional `instructions` gives the choices and obligations
of using it; a package's shared author instructions own guidance spanning its widgets.
General workflow guidance, such as how to word alternatives or when a decision becomes a
record, goes in the reference that owns that workflow. Keep widget-specific markup and
behavior in the widget or package instructions, with a pointer from the workflow where
an author needs them. `page-authoring.md`, "Read the registry", owns loading both on
each version.

A `boolean` attribute works as in HTML. Name it for what its presence means and make
absence the default, as in `lf-diff collapsed`. Every other attribute's value is a
string, so the schema of one that holds a number is a string with a `pattern`.

A tag that stands only inside another widget, as `lf-option` does inside `lf-options`,
is declared like any other and lists the tags that may hold it in `owners`; the holder
declares `content: members`, and the tag's `example` writes it inside a holder.

`verbatim: true` says the upgraded element still shows its authored words where they
stand, so a comment can quote across them as across any prose. Declare it on a wrapper
round authored content, and leave it off a widget whose module rewrites or reorders
what it holds: a comment's quote then stays inside one of its authored children, which
keeps it on its words when the module moves them. Whatever the module adds to a
verbatim widget stands inside a box of controls the library built
(`module-controls.md`), with no words marked `data-lf-said`, which would make them the
page's (`module-widgets.md`, "Words it writes").

A declaration names each of its element's attributes in `properties`, and the schema's
other keywords, such as `required`, constrain the attributes named there. `page check`
refuses an attribute `properties` doesn't name, such as a misspelt one. Composition
writes `"type": "object"` and `"additionalProperties": false` into the attribute schema
and into each verb's `detail` schema
([package-data.md, "User state"](package-data.md#user-state)), so a declaration leaves
both out of each. An attribute schema may write `"additionalProperties": true` to admit
attributes it doesn't name, as a widget that passes them to an inner element does. A
`detail` schema that writes any other value for either keyword is refused. A
declaration with nothing to say about its element's attributes leaves `attributes` out,
and the element then takes only the attributes composition writes for it, such as an
optional `id`. The attributes any element takes (`class`, `style`, `title`, `lang`,
`dir`, `aria-*` and the page's own `data-*`) stand outside the schema unless it names
one.

Every element takes an `id`. Composition writes it into the merged registry as a string,
so a declaration leaves `id` out of `properties` and says only whether the element
requires one, by listing `id` in `required`. Composition writes the attributes an input
binds by into `properties` too, as the registry's `$keys.inputs` defines.

Leaf owns the grammar of each name it looks up: an element's `id`, an input's source
attribute (`inputs`) and a verb's `contract` attribute. Declare a verb's `contract`
attribute as `{"type": "string"}`; composition writes each name's `pattern` into the
merged registry, replacing any the declaration gives. A `refers` attribute needs no
pattern either, since `page check` requires its value to name an element the page holds.

The shipped declarations are the worked examples. For the keys that change a widget's
role on the page:

| Fact           | Shipped example                                   |
| -------------- | ------------------------------------------------- |
| `reading-role` | `lf-pane`                                         |
| `visual`       | `lf-shot` declares `whole`, `lf-chart` `prefixes` |
| `bound`        | `lf-activity`                                     |
| `height`       | `lf-chart`                                        |
| `history`      | `lf-activity`                                     |
| `views`        | `lf-tabs`                                         |

A CSS-only widget is a registry entry and a theme rule; one with behavior adds a module
at `widgets/<tag>.js`, following [module-authoring.md](module-authoring.md). The file's
presence is what makes the tag an upgraded widget: Leaf loads it only where a page's
markup uses the tag, no declaration names it, and the composed registry lists each
tag's module under `$modules`. Helper modules sit beside the
entry module under names that aren't a declared tag's, and third-party files go under
`vendor/`. A module named like a widget (`lf-…`) that no tag declares and no module
imports is refused, since it is usually a widget's module under a mistyped name. What declarations mean for user
state is in [package-data.md, "User state"](package-data.md#user-state).

## Seeing it

`leaf package check PACKAGE --render` draws the worked examples of the package's
widgets, once in a reading column and once in a workspace pane, and prints findings in
`page check`'s format. Presentation findings are advice for the widget's author.
The command fails when the package check fails, the examples can't be drawn, or an
exercised output violates its [declared data contract](package-data.md#widget-outputs).
The examples are drawn as written, with no data set, so a widget bound to a source
draws its state for no value, and a package that declares no widget, such as a theme,
has nothing to draw. To see a widget with its data, or a theme, run `leaf page check
PAGE --render` on a page that selects the package.

The presentation checks:

- `example`: no worked example shows the tag, so no other check can read it.
- `keeps-first-box`: the widget's box changed size between first paint, before its
  module loaded, and presentation, so what follows it moved (`module-authoring.md`,
  "First paint"). A custom element is inline until a rule gives it a `display`, so give
  the tag its `display` in `defaults.css`, and reserve there the room of what the module
  adds, from the theme's tokens (`package-themes.md`, "Theme tokens"): an empty `::before` block on
  `lf-rating:not(:defined)` with `block-size: var(--lf-line)` holds one row of
  controls. A drawing the markup can't size declares `height`: a number where the
  module draws at any height, or `true` to reserve the `data-height` each occurrence
  states in CSS pixels, with no entry in `attributes`. Where that height follows the
  data, the widget's `instructions` say how the author works it out. A widget
  containing others is named only for the change left once its changed children are
  back at their first sizes. The advice may stand where the size follows content no
  rule can know, such as words drawn from bound data.
- `grows-with-content`: a box in the widget keeps a fixed height and scrolls inside
  it, where a widget in normal flow should grow with its content (`page-layout.md`,
  "Bounds and widths"). The check also finds a fixed height while the widget is empty,
  by adding a tall block. A box that needs its own scroll, such as an inspector beside a
  playing recording, or a part that scrolls inside the height a workspace gives it,
  declares `--lf-holds-height: 1`.
- `shows-context-keys`: a command declares `contextKeys` but no `bindingBadge`, so its
  key works with nothing on the page showing it. Give the command a visible control, or
  set `bindingBadge: null` for a corner badge (`module-input.md`, "Commands and
  keyboard routes"). The check reads only the commands in the example's state, so a
  command such as a multiple-choice decision's Done needs an example in that state.

After `leaf page init --package` adds the package to a page, run `leaf page check
<page> --render`, which reports a module's mistakes on the page, such as an upgrade
that defines no element or a widget with no size, and note the change in the next
stamped version's changelog. A served page takes later edits to an installed package
when its server next starts.

Then put the widget on the page. A widget is reviewed in place: the version that
answers the user's comment uses it where they asked, and they comment on it there.
