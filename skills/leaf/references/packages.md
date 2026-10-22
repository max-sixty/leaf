# Packages

A package is a directory Leaf adds to a page: a theme, widgets, helper modules,
libraries and external-data contracts. `page init` combines Leaf's kernel with the
page's packages, checks the result and copies it into the page as the page's layer.
Packages need no browser build or npm: write widgets and helpers as JavaScript the
browser loads directly, importing Leaf only through `/runtime/widget-api.js`.

This file covers what every package follows and how to declare a widget.
[package-themes.md](package-themes.md) covers theme rules, and
[package-data.md](package-data.md) the state a widget records, references between
widgets, and external data.

## Package reach

Leaf's bundled `default` package is on every page; any other package is on only the
pages that select it. Presentation or behavior one page uses stays in that page's
`<style>`, inline modules or `page/`. Anything reused belongs in a package:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
leaf package install packages/callout
leaf package run NAME SCRIPT [ARGS]...
```

`--package` takes a bare name, which selects an installed or bundled package, or a path
relative to the project or starting with `~`, such as `./.leaf` or `'~/.config/leaf'`;
absolute paths are refused, since the vendored registry is public. `package install`
copies the package's layout, without a README or tests, into
`~/.local/state/leaf/packages/`, where it overrides a bundled package of the same name.
A page records the bare name, so re-vendoring it on another machine needs the package
installed there too.

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
| `motion`        | `lf-motion`, a shared clock with playback and scrubbing for page-authored animation studies.                                                                |
| `visual-review` | Website cases with aligned before-and-after captures and a verdict per case.                                                                                |
| `playwright`    | Trace import and `lf-trace`, which steps through recorded actions and screenshots.                                                                          |

Packages declare no dependencies on each other; a page lists every package it needs.

## Package contract

Every package uses this layout, and every file is optional:

```text
package/
├── registry.json       element declarations and shared $ declarations
├── theme.css           rules in the layer's shared cascade layer
├── shadow.css          rules that also reach declared shadow trees
├── controls.css        deliberate control styling; theme packages grant access
├── instructions/       Markdown instructions named for their audiences
├── runtime/            package-owned browser modules
├── widgets/            entry modules and their private helpers
├── vendor/             third-party libraries or data files
├── scripts/            command-line tools `leaf package run` runs; never vendored
├── icon.svg            optional replacement by path
```

A package's `icon.svg`, `widgets/` and `vendor/` files replace files at the same path,
and `runtime/` modules can add paths but not replace the kernel's. A replacement
`icon.svg` must contain an element with `class="lf-tone"`, which Leaf colours with the
page's status.

Registries merge in order: kernel, `default`, then the selected packages in command
order. A later package replaces an element or idiom entry whole and can't delete one.
Shared `$` entries merge by member, and a map member merges one level further by key;
`null` deletes at either level if the merged registry still validates. `page init`
records the selected packages in `$layer.packages`, so a plain re-init selects them
again, and `page init --no-packages PAGE` clears the list.

Name each file directly under `instructions/` `<audience>.md`, such as `author.md` or
`worker.md`, and start it with its first rule, since Leaf adds a heading naming the
package. Files for the same audience join in package order. A data contract's
`instructions` map holds text per audience beside its schema, and a registry entry's
`x-instructions` is one string for the page author. `leaf page instructions` composes
them as a JSON map from audience to text (`page-authoring.md`, "Read the registry"),
and `--contract` selects a contract's instructions directly:

```bash
leaf page instructions PAGE --contract unified-diff | jq -er '.producer'
```

### Widget interface

Keep a widget simple: show the evidence and actions the reader needs, since every extra
control competes with them. Add an optional control when a caller needs it, and let
the page's author turn it on. Use the theme's tokens and shared control styles before
writing widget CSS, and reuse Leaf's thread symbol, comment box and keyboard hints
(`module-input.md`, "Commands and keyboard routes", and `module-annotations.md`,
"Widget-local Thread placement").

### Styles and composition

Leaf orders its cascade layers `lf-reset`, `lf-base`, `lf-layouts`, `lf-shadow`,
`lf-theme`, `lf-controls`, `lf-state`, and the page's own CSS is unlayered. A widget
package's `theme.css` and `shadow.css` go in `lf-base`, below the Layouts; a theme
package, one that declares no widgets, goes in `lf-theme`, above them. In a shadow root,
each package's `shadow.css` goes in `lf-shadow`, or `lf-theme` for a theme package, and
Layout rules don't reach inside. Put a dependency's default styles in `lf-base` with
`inBaseLayer(text)` (`module-authoring.md`, "Shadow stages and styles").

Leaf's own controls and comment marks are unlayered, so a theme package's rule for
`button` styles the page's buttons, not the controls widgets build. A theme package
reaches those controls only through `controls.css`, which goes in `lf-controls`, above
ordinary theme rules and below semantic state; a widget package styles its own controls
in `theme.css`. Page authors grant access per stylesheet (`page-layout.md`, "Page CSS
and Leaf's controls"). `!important` and inline styles are not ways to customise a
widget.

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

An element with `hidden` is always `display: none`, in the document and in shadow
trees, except `hidden="until-found"`. Give a box that must stay laid out while unseen a
state of its own.

Custom properties come in four kinds:

| Kind                | Owner and supported use                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Theme inputs        | Page authors and themes set them on the root or a subtree: colours (`--paper`, `--ink`, `--muted`, `--accent`, `--ok`, `--danger`), faces (`--serif`, `--sans`, `--mono`), type scales, radius (`--r`), the code palette (`--code-*`), focus (`--focus-ring` and `--focus-shadow`, set together), and page geometry (`--col`, `--wide`, `--sidebar`, `--page-pad-start`, `--page-pad-end`). A derived value is computed where it is declared, so setting an input on a subtree doesn't change a value derived from it above. |
| Layout declarations | The box that allocates space sets `--lf-full-height`, `--lf-density`, `--lf-block-frame` and `--lf-holds-edge` (`package-themes.md`, "A theme change").                                                                                                                                                                                                                                                                                                                                                                      |
| Runtime outputs     | Leaf writes values such as `--lf-root-headers` and anchor geometry. Read them; don't set them.                                                                                                                                                                                                                                                                                                                                                                                                                               |
| Vendor bridges      | An adapter maps Leaf inputs to a dependency's properties, such as `--diffs-*` and `--plot-background`. Change the Leaf input, not each use.                                                                                                                                                                                                                                                                                                                                                                                  |

A `--lf-` prefix doesn't make a property an input; most are outputs. A package
documents any further inputs it supports. No type or colour override may shrink a
control below its touch target or focus clearance.

## A widget

An element declaration is a JSON Schema over the element's attributes, plus `x-` keys
that say how Leaf treats the tag, such as whether a module upgrades it, its action verbs
and whether it puts an obligation on On me. The merged registry's `$keys` entry defines
each key; `$state` defines the members of `x-state`, and `$awaits` an obligation's
answer. Every declaration has a `description` saying what the widget is for and when to
use it, and a valid `x-example`. The optional `x-instructions` gives the markup choices
and obligations of using it. Guidance a workflow shares across elements, such as how to
word alternatives, goes in the instructions that own that workflow, because an author
revising a page re-reads those instructions, not the entry.

A `boolean` attribute works as in HTML. Name it for what its presence means and make
absence the default, as in `lf-diff collapsed` or `lf-shot outlines`.

The shipped declarations are the worked examples. For the keys that change a widget's
role on the page:

| Key                | Shipped example                                                |
| ------------------ | -------------------------------------------------------------- |
| `x-reading-role`   | `lf-pane`                                                      |
| `x-resident`       | `lf-toc`                                                       |
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
widgets, once in a reading column and once in a workspace pane. Its findings are advice
for the widget's author and leave the exit status alone:

- `example`: no worked example shows the tag, so no other check can read it.
- `keeps-first-box`: the widget's box changed size after first paint. Size it for first
  paint as [module-authoring.md, "First paint"](module-authoring.md#first-paint)
  describes. A widget containing others is named only for the change left once its
  changed children are back at their first sizes.
- `grows-with-content`: a box in the widget keeps a fixed height and scrolls inside it,
  or keeps one while the widget is empty, where a widget in normal flow should grow with
  its content (`page-layout.md`, "Bounds and widths"). A box that needs its own scroll,
  such as an inspector beside a playing recording, or a part that scrolls inside the
  height a workspace gives it, declares `--lf-holds-height: 1`.
- `shows-context-keys`: a command declares `contextKeys` but no `bindingBadge`, so its
  key works with nothing on the page showing it. Give the command a visible control, or
  set `bindingBadge: null` for a corner badge (`module-input.md`, "Commands and
  keyboard routes"). The check reads only the commands in the example's state, so a
  command that appears in another state, such as a multiple-choice decision's Done,
  needs an example in that state.

After `leaf page init` re-vendors a page with the package (`serving-pages.md`,
"Re-vendoring"), run `leaf page check <page> --render`, which reports a module's
mistakes on the page, such as an upgrade that defines no element or a widget with no
size, and note the re-vendor in the next stamped version's changelog. Then put the
widget where the user asked for it, in the version that answers their comment, so they
review it in place.
