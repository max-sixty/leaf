# Packages

A package is a directory Leaf adds to a page. It can hold a theme, widgets, helper
modules, libraries and external-data contracts. `page init` combines Leaf's kernel with
the page's packages, checks the result, and copies it into the page as the page's
layer. Packages need no browser build or npm command: write widgets and helpers as
JavaScript the browser loads directly, importing the shipped `/runtime/widget-api.js`.

This file covers what every package follows and how to declare a widget.
[package-themes.md](package-themes.md) covers packages that change the theme, and
[package-data.md](package-data.md) the state a widget records, references between
widgets, and external data.

## Package reach

Leaf's bundled `default` package is on every page; any other package is on only the
pages that select it. Presentation or behavior used by one page stays in that page's
`<style>`, inline modules or `page/`. Anything reused belongs in a package:

```bash
leaf package init PACKAGE
leaf package init PACKAGE --widget lf-callout
leaf package check PACKAGE
leaf package install PACKAGE
leaf package run NAME SCRIPT [ARGS]...
```

`package init` creates the package's directories, keeping anything already there.
`--widget TAG` also writes a registry example and a `widgets/TAG.js` module that
registers and upgrades the element; Leaf refuses a tag or module that already exists.
Check the package before adding it to a page:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
```

`--package` takes a bare name, which selects an installed or bundled package, or a
path relative to the project or starting with `~`, such as `./.leaf` or
`'~/.config/leaf'`. Absolute paths are refused, since the vendored registry is public.

`leaf package install SOURCE` checks the directory and copies it into
`~/.local/state/leaf/packages/`, so `--package NAME` selects it from any project on this
machine. The copy holds only the files in the package layout below, so a README and
tests stay behind. Installing again replaces the copy only if the new one passes its
check. An installed package overrides a bundled one of the same name. A page records
the bare name, so re-vendoring it on another machine needs the package installed there
too.

The optional bundled packages are:

| Package | Adds |
| --- | --- |
| `code-review` | Instructions for writing a review; select it with the evidence packages the page needs. |
| `diagram` | `lf-diagram` and its Mermaid renderer. |
| `diff` | `lf-diff`, its `unified-diff` data contract, and `lf-call-diff`, which links to exact patch lines. |
| `file-editor` | `lf-file-editor`, a CodeMirror editor for a bound local text file. |
| `playground` | Controls with shared state, preview and output, and typed submission of the configuration. |
| `monitoring` | Instructions for a release workspace: current state, checks, a run log and a rollback ask. |
| `visual-review` | Website cases with aligned before-and-after captures and a verdict per case. |
| `playwright` | Trace import and `lf-trace`, which steps through recorded actions and screenshots. |

Packages declare no dependencies on each other; a page lists every package it needs.

## Package contract

Every package uses this layout, and every file is optional:

```text
package/
├── registry.json       element declarations and shared $ declarations
├── theme.css           rules in the layer's shared cascade layer
├── shadow.css          rules that also reach declared shadow trees
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

A widget package's rules rank below the Layouts, a theme package's (one that declares
no widgets) above them, and the page's own `<style>` above both. In layer terms: Leaf
orders its cascade layers `lf-reset`, `lf-base`, `lf-layouts`, `lf-shadow`, `lf-theme`,
`lf-state`. In the document, a widget package's `theme.css` and `shadow.css` go in
`lf-base` and a theme package's in `lf-theme`. In a shadow root, each package's
`shadow.css` goes in `lf-shadow`, or `lf-theme` for a theme package, and Layout rules
don't reach inside. The page's own CSS is unlayered. `!important` and inline styles are not ways to customise a
widget.

An element with `hidden` is always `display: none`, in the document and in shadow
trees, except `hidden="until-found"`. Give a box that must stay laid out while unseen a
state of its own.

Leaf's own controls and comment marks are unlayered, and a theme package's rule for
`button` styles the page's buttons, not the controls widgets build (`page-layout.md`,
"Page CSS and Leaf's controls"). Change Leaf's colours and type through the theme
inputs below. Put a dependency's default styles in `lf-base` with `inBaseLayer(text)`
(`module-authoring.md`, "Shadow stages and styles").

Leaf wraps each widget package's sheets in `@scope`, rooted at the package's widget
tags, or at `:host` in a shadow root. A rule for `p` therefore styles paragraphs inside
that package's widgets, and a rule for `html`, `body` or the box around a widget
matches nothing. `:scope` is the widget itself, and `:scope:is(lf-tag)` picks one of
the package's widgets; in `shadow.css`, `:scope:host(.state)` reads the host's state.
Write outside conditions as a nested scope, such as
`@scope (html[data-lf-interactive] :scope)`. Page-wide rules belong in a theme package,
which is unscoped. Adjust another package's widget through its tokens or API, not its
private DOM.

Document selectors don't reach into a shadow root. A declared `x-shadow` root built with
`shadowStage` gets the shared styles and every package's `shadow.css`. Use theme inputs
for changes to both, `shadow.css` for a widget's internals, and `::part` to expose a
public control.

Custom properties come in four kinds:

| Kind | Owner and supported use |
| --- | --- |
| Theme inputs | Page authors and themes set them on the root, or on a subtree: colours (`--paper`, `--ink`, `--muted`, `--accent`, `--ok`, `--danger`), faces (`--serif`, `--sans`, `--mono`), type scales, radius (`--r`), the code palette (`--code-*`), focus (`--focus-ring` and `--focus-shadow`, set together), and page geometry (`--col`, `--wide`, `--sidebar`, `--page-pad-start`, `--page-pad-end`). A value derived from an input is computed where it is declared, so setting the input on a subtree doesn't change a derived value it inherits. |
| Layout declarations | The box that allocates space sets `--lf-full-height`, `--lf-density`, `--lf-block-frame` and `--lf-holds-edge`, as `package-themes.md`, "A theme change", describes. |
| Runtime outputs | Leaf writes values such as `--lf-thread-panel-width` and anchor geometry. Read them; don't set them. |
| Vendor bridges | An adapter maps Leaf inputs to a dependency's properties, such as `--diffs-*` and `--plot-background`. Change the Leaf input, not each use. |

A `--lf-` prefix doesn't make a property an input; most are outputs. A package
documents any further inputs it supports. No type or colour override may shrink a
control below its touch target or focus clearance.

A package's `icon.svg`, `widgets/` and `vendor/` files replace files at the same path.
Import Leaf only through `/runtime/widget-api.js`; `package check` refuses an import of
any other kernel module, and `runtime/` modules can add paths but not replace the
kernel's.

Registries merge in order: kernel, `default`, then the selected packages in command
order, and a later package wins a collision. A later package replaces an element or
idiom entry whole and can't delete one. Shared `$` entries merge by member, and a map
member merges one level further by key; `null` deletes at either level if the merged
registry still validates. `page init` records the selected packages in
`$layer.packages`, and a plain re-init selects them again;
`page init --no-packages PAGE` clears the list.

Name each file directly under `instructions/` `<audience>.md`, matching
`[a-z][a-z0-9-]*\.md`, and start it with its first rule: Leaf adds a heading naming the
package. Packages define their own audiences, such as `author` or `worker`, and files
for the same audience join in package order. A data contract's `instructions` map holds
text per audience beside its schema, and a registry entry's `x-instructions` is one
string for the page author.

```bash
leaf page instructions PAGE | jq 'keys'
leaf page instructions PAGE --use lf-options --use .eyebrow | jq -r '.author // empty'
leaf page instructions PAGE --contract unified-diff | jq -er '.producer'
```

`leaf page instructions` returns a JSON map from audience to text. With no selection it
returns the packages' shared instructions. Each `--use ENTRY` adds that entry's
`x-instructions` to `author`, along with the entries its `x-example` uses and its
`x-data` contracts, whose instructions join their own audiences. It reads the layer
just vendored and any `page/registry.json`, so it works before the page has markup.
`page-authoring.md`, "Read the registry", says when an author reads each part.

A replacement `icon.svg` must contain an element with `class="lf-tone"`, which Leaf
colours with the page's status.

## A widget

An element declaration is a JSON Schema over the element's attributes, plus `x-` keys
that say how Leaf treats the tag, such as whether a module upgrades it, its action verbs
and whether it poses an ask. The merged registry's `$keys` entry defines each key;
`$state` defines the members of `x-state`, and `$awaits` an ask's answer. Every
declaration has a `description` saying what the widget is for and when to use it, and a
valid `x-example`. The optional `x-instructions` gives the choices and obligations of
using it.

A `boolean` attribute works as in HTML. Name it for what its presence means and make
absence the default, as in `lf-diff collapsed` or `lf-shot outlines`.

The shipped declarations are the worked examples. For the keys that change a widget's
role on the page:

| Key                  | Shipped example                                                |
| -------------------- | -------------------------------------------------------------- |
| `x-reading-role`     | `lf-pane`                                                      |
| `x-resident`         | `lf-toc`                                                       |
| `x-visual`           | `lf-chart` declares `whole`, `lf-diagram` in `diagram` `parts`  |
| `x-bound`            | `lf-activity`                                                  |
| `x-height`           | `lf-chart`                                                     |
| `x-history`          | `lf-activity`                                                  |
| `x-patch`            | `lf-tabs`                                                      |
| `x-views`            | `lf-tabs`                                                      |
| `x-thread-surface`   | `lf-diff` in `diff`, `lf-visual-review` in `visual-review`     |

A CSS-only widget is a registry entry and a theme rule; one with behavior adds a module,
following [module-authoring.md](module-authoring.md). Helper modules sit beside the
entry module, and third-party files go under `vendor/`. What declarations mean for user
state is in [package-data.md, "User state"](package-data.md#user-state).

## Seeing it

`leaf package check PACKAGE --render` draws the worked examples of the package's
widgets, once in a reading column and once in a workspace pane, and prints findings in
`page check`'s format. Widget findings are advice for the widget's author and don't
change the exit status; the command fails only when the package check fails or the
examples can't be drawn. The checks:

- `example`: no worked example shows the tag, so no other check can read it.
- `keeps-first-box`: the widget's box changed size after first paint. Size the widget
  for first paint as [module-authoring.md, "First paint"](module-authoring.md#first-paint)
  describes. A widget containing others is named only for the change left once its
  changed children are back at their first sizes.
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
  command such as a multiple-choice ask's Done needs an example in that state.

After `leaf page init` re-vendors a page with the package (`serving-pages.md`,
"Re-vendoring"), run `leaf page check <page> --render`, which reports a module's
mistakes on the page, such as an upgrade that defines no element or a widget with no
size, and note the re-vendor in the next stamped version's changelog.

Then put the widget on the page. A widget is reviewed in place: the version that
answers the user's comment uses it where they asked, and they comment on it there.
