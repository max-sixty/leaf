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

## Package reach

Leaf's bundled `default` package is on every page; any other package is on only the
pages that select it. Presentation or behavior used by one page stays in that page's
`<style>`, its scripts or `page/`. Anything reused belongs in a package:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
leaf package install packages/callout
leaf package run NAME SCRIPT [ARGS]...
```

`--package` takes a bare name, which selects an installed or bundled package, or a
path relative to the project or starting with `~`, such as `./.leaf` or
`'~/.config/leaf'`. Absolute paths are refused, since the page's registry is public.
`page init` copies a package selected by path into the page's `packages/`, so the
page reads the same wherever it is served; run `page init --package` again to take
in edits to the package.

`leaf package install SOURCE` checks the directory and copies it into
`~/.local/state/leaf/packages/`, so `--package NAME` selects it from any project on this
machine. The copy holds only the files in the package layout below, so a README and
tests stay behind. An installed package overrides a bundled one of the same name. A page records
the bare name, and every Leaf that reads the page composes the package it finds by
that name, so serving the page on another machine needs the package installed there
too.

The optional bundled packages are:

| Package         | Adds                                                                                                                                                        |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `code-review`   | Instructions for writing a review; select it with the evidence packages the page needs.                                                                     |
| `diagram`       | `lf-diagram`, rendering Mermaid syntax with Pele.                                                                                                           |
| `diff`          | `lf-diff` (`unified-diff` data) and `lf-call-diff` (`calldiff` JSON), linked to exact patch lines, and `lf-worktree-diffs` for a set of worktree snapshots. |
| `file-editor`   | `lf-file-editor`, a CodeMirror editor for a bound local text file.                                                                                          |
| `file-tree`     | `lf-file-tree`, a searchable navigator for a file list or another widget’s typed file inventory, following its opaque datum keys.                           |
| `playground`    | Controls with shared state, preview and output, and typed submission of the configuration.                                                                  |
| `monitoring`    | Instructions for a release workspace: current state, checks, a run log and a rollback decision.                                                             |
| `motion`        | `lf-motion`, shared playback and scrubbing for authored animations and video comparisons.                                                                   |
| `deck`          | `lf-deck`, a pile of decisions the user works through one card at a time.                                                                                   |
| `detail`        | `lf-dial`, which turns a page from each section's `.gist` to every closed detail, keeping the reader's place.                                               |
| `visual-review` | Website cases with aligned before-and-after captures and a verdict per case.                                                                                |
| `playwright`    | Trace import and `lf-trace`, which steps through recorded actions and screenshots.                                                                          |
| `timeline`      | `lf-timeline`, an authored sequence of events in lanes that the reader steps through, with a playhead and a step list.                                      |

Packages declare no dependencies on each other; a page lists every package it needs.

## Package contract

Every package uses this layout, and every file is optional:

```text
package/
├── registry.json       element declarations and shared $ declarations
├── defaults.css        defaults: its widgets', and a theme's element rules
├── widget-shadow.css   widget defaults also loaded in their shadow trees
├── overrides.css       page-wide rules that outrank every package's defaults
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
writing widget CSS, and reuse Leaf's thread symbol, comment box and keyboard hints
(`module-input.md`, "Commands and keyboard routes", and `module-annotations.md`,
"Widget-local Thread placement").

### Styles and composition

Choose a stylesheet by the contribution it makes. A package may supply any combination;
adding a widget does not change its theme styling.

| Sheet               | Document                    | Declared shadow trees |
| ------------------- | --------------------------- | --------------------- |
| `defaults.css`      | `lf-base`                   | —                     |
| `widget-shadow.css` | `lf-base`                   | `lf-shadow`           |
| `overrides.css`     | Page-wide in `lf-overrides` | —                     |

Defaults, a widget's own and a theme's element rules and idioms, go in `defaults.css`,
below Layouts; overrides, in `overrides.css`, rank above them. Leaf orders
the cascade layers `lf-reset`, `lf-base`, `lf-layouts`, `lf-shadow`, `lf-overrides`,
`lf-state`. A shared shadow sheet precedes its document-only sheet; later selected
packages win ties. The page's own CSS is unlayered above these normal rules. Layouts
do not reach inside shadow trees. A theme's rules, like the page's own, reach the
controls widgets build (`page-layout.md`, "Page CSS and Leaf's controls"). Being
layered, they also outrank the layered faces of the controls in Leaf's panel and thread
cards, so a theme's element rules name the content they style, such as `main button`. Use public inputs and selectors to customise a widget rather than
`!important` or inline overrides.

A package's sheet can be split into files: `@import "./styles/tabs.css";`, optionally
with `layer(name)`, names a file inside the package, and composition puts that file's
rules where the import stands, so the page receives one sheet and edits need no build.

An element with `hidden` is always `display: none`, in the document and in shadow
trees, except `hidden="until-found"`. Give a box that must stay laid out while unseen a
state of its own.

Leaf's chrome and comment marks are unlayered, so change their colours and type
through the theme inputs below. Put a dependency's default styles in `lf-base` with
`inBaseLayer(text)` (`module-authoring.md`, "Shadow stages and styles").

Leaf places each sheet in its tier and changes none of its rules, so a sheet names
the widgets it styles: `lf-tag .part` in the document, and `:host(lf-tag) .part` in a
shadow tree, where `:host(lf-tag.ready)` reads the host's state. A bare `p { … }`
reaches every paragraph on the page, and in a shadow sheet everything the tree holds,
including Leaf's views placed there, such as a diff's threads. A rule naming a widget
also reaches a foreign widget nested inside it, so style structure a nested widget may
share through a child combinator or the package's own classes. Replacing a widget's
declaration or module does not withdraw the selected package's stylesheet
contribution. Inherited values cross every widget boundary. Adjust another widget's
internals through its inputs or API; overrides are deliberately page-wide.

Document selectors don't reach into a shadow root. A declared `x-shadow` root gets
the composed shared stylesheet through `LeafElement` for `x-shadow`, or through
`shadowStage` for an imperative renderer. Use theme inputs for changes across
both trees, `widget-shadow.css` for owned internals, and `::part` to expose a public
control.

Custom properties come in four kinds:

| Kind                | Owner and supported use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Theme inputs        | Page authors and themes set them on the root, or on a subtree: colours and semantic pairs (`package-themes.md`, "Theme colors"), faces (`--serif`, `--sans`, `--mono`), markup's reading face (`--lf-reading-face: 1`, `package-themes.md`, "Personal themes"), type scales (`--t-*`, expressed in `rem` by default), code typography (`--code-size` for font size and `--code-line` for line-height, both CSS lengths), radius (`--r`), code and syntax palettes (`--code-*`, `--syn-*`), focus (`--focus-ring` and `--focus-shadow`, set together), and page geometry (`--col`, `--wide`, `--sidebar`, `--page-pad-start`, `--page-pad-end`). A value derived from an input is computed where it is declared, so setting the input on a subtree doesn't change a derived value it inherits. |
| Layout declarations | The box that allocates space sets `--lf-full-height`, `--lf-density`, `--lf-block-frame` and `--lf-holds-edge`, as `package-themes.md`, "A theme change", describes.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| Runtime outputs     | Leaf writes values such as `--lf-root-headers` and anchor geometry. Read them; don't set them.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| Vendor bridges      | An adapter maps Leaf inputs to a dependency's properties, such as `--diffs-*` and `--plot-background`. Change the Leaf input, not each use.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |

Leaf's own interface sets its words in fonts derived from those inputs, each a whole
value for the `font` shorthand (`--font-ui`, `--font-small` and the rest, listed in
`browser/base.css`); a widget's controls that name one match Leaf's at every density.

A `--lf-` prefix doesn't make a property an input; most are outputs. A package
documents any further inputs it supports. No type or colour override may shrink a
control below its touch target or focus clearance.

A package's `icon.svg`, `widgets/` and `vendor/` files replace files at the same path.
Import Leaf behavior through `/runtime/widget-api.js`, or its portable part
`/runtime/portable-api.js` (module-authoring.md, "A widget that also runs off Leaf").
Package `runtime/` modules can add paths but not replace the kernel's. The Leaf serving a page supplies its runtime,
`widget-api.js` and the kernel's `vendor/` modules included, and composes the page's
packages from its own catalogue, so a package runs against the runtime of whichever
Leaf serves its page, and a package's `vendor/` file at one of those paths replaces it
there. `widget-api.js` can change in any update; `leaf package check --render` and
`leaf page check --render` report a module it breaks.

Registries merge in order: kernel, `default`, the page's theme, then the selected
packages in command order, and a later package wins a collision. A later package replaces an element or
idiom entry whole and can't delete one. Shared `$` entries merge by member, and a map
member merges one level further by key; `null` deletes at either level if the merged
registry still validates. `page init` records the selected packages in
`$layer.packages`, and a plain re-init selects them again. Re-initializing with
`--package` replaces that list, so name every package the page keeps.
`page init --no-packages PAGE` clears the list and keeps the page's theme, which
`--theme` and `--no-theme` choose
([package-themes.md, "Personal themes"](package-themes.md#personal-themes)).

Name each file directly under `instructions/` `<audience>.md`, matching
`[a-z][a-z0-9-]*\.md`, and start it with its first rule: Leaf adds a heading naming the
package. Packages define their own audiences, such as `author` or `worker`, and files
for the same audience join in package order. A data contract's `instructions` map holds
text per audience beside its schema, and a registry entry's `x-instructions` is one
string for the page author.

```bash
leaf page instructions PAGE --contract unified-diff | jq -er '.producer'
```

`leaf page instructions` returns a JSON map from audience to text. With no selection it
returns the packages' shared instructions. Each `--use ENTRY` adds that entry's
`x-instructions` to `author`, along with the entries its `x-example` uses and its
`x-data` contracts, whose instructions join their own audiences. It reads the layer
the page selects and any `page/registry.json`, so it works before the page has markup.
`page-authoring.md`, "Read the registry", says when an author reads each part.

A replacement `icon.svg` must contain an element with `class="lf-tone"`, which Leaf
colours with the page's status.

## A widget

An element declaration is a JSON Schema over the element's attributes, plus `x-` keys
that say how Leaf treats the tag, such as whether a module upgrades it, its action verbs
and whether it puts an obligation on On me. The merged registry's `$keys` entry defines each
key; `$state` defines the members of `x-state`, and `$awaits` an obligation's answer. Every
declaration has a `description` saying what the widget is for and when to use it, and a
valid `x-example`. The optional `x-instructions` gives the choices and obligations of
using it. Guidance a workflow shares across elements, such as how to word
alternatives, goes in the instructions that own that workflow, and the entry points to
them: an author revising a page re-reads those instructions, not the entry.

A `boolean` attribute works as in HTML. Name it for what its presence means and make
absence the default, as in `lf-diff collapsed`.

The shipped declarations are the worked examples. For the keys that change a widget's
role on the page:

| Key                | Shipped example                                                |
| ------------------ | -------------------------------------------------------------- |
| `x-reading-role`   | `lf-pane`                                                      |
| `x-visual`         | `lf-chart` declares `whole`, `lf-diagram` in `diagram` `parts` |
| `x-bound`          | `lf-activity`                                                  |
| `x-height`         | `lf-chart`                                                     |
| `x-history`        | `lf-activity`                                                  |
| `x-patch`          | `lf-tabs`                                                      |
| `x-views`          | `lf-tabs`                                                      |
| `x-thread-surface` | `lf-diff` in `diff`, `lf-visual-review` in `visual-review`     |

A CSS-only widget is a registry entry and a theme rule; one with behavior adds a module,
following [module-authoring.md](module-authoring.md). Helper modules sit beside the
entry module, and third-party files go under `vendor/`. What declarations mean for user
state is in [package-data.md, "User state"](package-data.md#user-state).

## Seeing it

`leaf package check PACKAGE --render` draws the worked examples of the package's
widgets, once in a reading column and once in a workspace pane, and prints findings in
`page check`'s format. Presentation findings are advice for the widget's author.
The command fails when the package check fails, the examples can't be drawn, or an
exercised output violates its [declared data contract](package-data.md#widget-outputs).

For a data-bound example, add `x-example-data` beside `x-example`, mapping each
source id in that markup to its sample JSON value. For example,
`"x-example-data": {"release-ci": {"main": "passing"}}` supplies the source in
`<lf-builds id="builds" source="release-ci"></lf-builds>` when its contract accepts
that value. Package checks validate these values against the bound contracts; a
source without a sample stays unset. The render check supplies the values through
ordinary bound data in both Layouts. Examples that reuse a source id render on
separate pages, so each keeps its own values.

The presentation checks:

- `example`: no worked example shows the tag, so no other check can read it.
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
