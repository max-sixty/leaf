# Packages

A package is the directory Leaf authors, shares, and adds to a page. It may hold a
theme, one widget, a family of widgets, helper modules, libraries, external-data
contracts, or any combination of them. The layer is different: it is the checked
result that `page init` vendors after composing the kernel and packages.
Creating, checking, installing, and using a package requires no browser build or
npm command. Write widgets and helper modules as browser-loadable JavaScript;
Leaf copies them directly and they use the shipped `/runtime/widget-api.js`.

This file holds the contract every package keeps and how to declare a widget.
[package-themes.md](package-themes.md) covers a package that changes the theme, and
[package-data.md](package-data.md) the user state a widget records, references between
widgets, and external or derived data.

## Package reach

Leaf's bundled `default` package reaches every page. Any other package reaches only the
pages that select it by name or path. Presentation or behavior used by only one page
stays in that version, in its `<style>` and its inline modules or `page/`. Everything
reusable belongs to a package. Leaf creates, checks, installs, and runs the whole
directory:

```bash
leaf package init PACKAGE
leaf package init PACKAGE --widget lf-callout
leaf package check PACKAGE
leaf package install PACKAGE
leaf package run NAME SCRIPT [ARGS]...
```

`package init` creates `registry.json`, `theme.css`, `instructions/`, `runtime/`,
`widgets/`, and `vendor/` without replacing existing contents. Add `--widget TAG` to
create one upgraded prose widget at the same time. Leaf adds a valid registry example
and the matching `widgets/TAG.js` module, which registers the element and upgrades it
`once`; it then checks the resulting composition, and leaves a new package's empty
theme ready for the widget's presentation.
An existing theme and other package files remain in place. Leaf refuses a tag or module
that already exists rather than replacing it. The package author edits that directory,
then checks its composition before adding the package to a page:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
```

Every package beyond the bundled default is selected explicitly, and the
always-present `default` package cannot be. A bare name selects an installed or
bundled package and never means a path. A path is project-relative or starts with
`~`: `--package ./.leaf`, `--package '~/.config/leaf'`, or `.` inside a repository
dedicated to one package. Absolute paths are refused because the vendored registry
is public.

`leaf package install SOURCE` checks that directory and copies it into
`~/.local/state/leaf/packages/`, where `--package NAME` reaches a checked snapshot
by the source directory's name from any project on this machine:

```bash
leaf package install packages/callout
leaf page init --package callout PAGE
```

The copy holds the package contract below, `scripts/` included, and nothing else in
the source directory, so a README and the author's own tests stay behind. Installing
again atomically replaces the name's snapshot after validation; a failed replacement
keeps the previous installation. An installed package overrides a bundled package of
the same name. Readers already using a snapshot retain its complete contents. A page
records the bare name, so re-vendoring it on another machine needs the same package
installed there.

The optional bundled packages are:

| Package | Adds |
| --- | --- |
| `code-review` | Review-authoring instructions; select alongside the evidence packages the page needs. |
| `diagram` | `lf-diagram` and its Mermaid renderer. |
| `diff` | `lf-diff`, its `unified-diff` data contract and Pierre renderer, and `lf-call-diff` with links to exact patch evidence. |
| `file-editor` | `lf-file-editor`, a CodeMirror editor for an explicitly bound local text file, with quiet automatic saving and inline conflict recovery. |
| `playground` | Controls and structured state with shared reset, restore, preview, output, and typed configuration submission. |
| `monitoring` | Release-workspace instructions for current state, checks, a run log, and a rollback ask. |
| `visual-review` | Ordered website cases with aligned before-and-after evidence, automatic comparison orientation, authored focus and full-frame context, flip and overlay, fit and captured-size inspection, exact preview links, and dispositions. |
| `playwright` | Native trace import and `lf-trace` review of actions, checkpoint images, captured frames and saved accessibility elements, with comments that restore their recorded moment and a link to Playwright's full viewer. |

The diagram and diff renderers are large and most pages draw neither, so they travel in
their own packages rather than in `default`. Packages declare no dependencies on each
other; a page states the whole list it needs.

## Package contract

Every package has the same partial layout:

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

No individual file is required. The kernel supplies the files every complete layer
needs.

### Widget interface

Keep a widget's interface clear and simple: show the evidence and the actions the
reader needs for the task. Each extra control competes with that work. Add optional
controls when a caller needs them; let the author choose those options for the page.

Use the inherited type, color and spacing tokens and shared control styles before
adding widget-specific CSS. Declared shadow roots receive the shared `shadow.css`
sheets too. Reuse Leaf's thread symbol, composer and keyboard hints so the same
action looks and behaves the same across widgets. `module-input.md`, "Commands
and keyboard routes", and `module-annotations.md`, "Widget-local Thread placement", describe those shared mechanisms.

### Styles and composition

CSS has three independent boundaries: the component that owns a rule, the roots
its selectors reach, and the cascade tier that decides competing declarations.
A shared face has one owner, even when composition includes it in both document
and shadow sheets. A package supplies complete `theme.css` and `shadow.css` files;
composition reads those files directly. Custom packages require no npm command or
CSS build. Leaf's shared reading, controls and response primitives are already
included in the roots described below.

Composition declares the order `lf-reset`, `lf-base`, `lf-layouts`, `lf-shadow`,
`lf-theme`, `lf-state`. In the document, the kernel's and every widget package's
theme/shadow sheets share `lf-base`; Layouts occupy `lf-layouts`, a theme package's
sheets (a package that declares no widgets) occupy `lf-theme`, and semantic state
occupies `lf-state`. In declared shadow roots, adopted widget defaults occupy
`lf-base`, shared and widget package shadow sheets occupy `lf-shadow`, a theme
package's shadow sheet occupies `lf-theme`, and state occupies `lf-state`; document
Layout rules do not cross the root. Normal declarations in the page's
unlayered stylesheet outrank these defaults. Within a tier, specificity, native scope
proximity, then source order decide. `!important` reverses layer priority, and inline
styles outrank ordinary stylesheet declarations; neither is a customization API.
An important rule ahead of every tier but `lf-reset` holds `hidden` (except
`until-found`) at `display: none` in the document and in each shadow tree, its host
included, whatever display another rule states, so no rule restores it; a box that
stays laid out while unseen wears a state of its own, not `hidden`.
Runtime chrome and annotation marks remain unlayered and own their apparatus paint.
The generic indication contour is a default in `lf-base`, so a widget can style its
indicated parts in its own sheets.
`page-layout.md`, "Page CSS and Leaf's controls", describes how page selectors opt into
Leaf controls; broad content selectors leave that apparatus alone. A theme package's
document rules are read the same way, so its rule for `button` dresses the page's own
buttons and not the controls widgets build. Inherited theme
inputs are the supported way to change its shared colors and type.
Keep dependency defaults in the same tier with `inBaseLayer(text)` from
`/runtime/widget-api.js`. Bundled CodeMirror applies this at its style provider;
Plot and trace apply it to generated styles. Preserve explicitly authored inline
options, whose priority the author chose.

Composition wraps each widget package's sheets in native `@scope`: document roots
are its declared widget tags, and shadow roots are their `:host`. Ordinary selectors
name descendants; `:scope` names a root, with `:scope:is(lf-tag)` selecting one kind
in a package. In shadow CSS, `:scope:host(.state)` reads the host's state. Outside
conditions belong in nested scopes, such as `@scope (html[data-lf-interactive] :scope)`.
A rule for `p` styles paragraphs inside that package's widgets. A rule for `html`,
`body`, or a widget's containing box matches nothing. Put page vocabulary in the
kernel; a package without widgets is an unscoped page theme. Later packages refine
a face through tokens or rules in their own scope, rather than reaching into another
widget's private DOM. For example, `lf-shot` owns image modes, crop and scale;
visual-review allocates its pane and requests inspection through the image owner's API.

Document selectors do not cross a shadow root. A declared `x-shadow` root built
with `shadowStage` receives shared primitives and every package's `shadow.css` in
layer order. The document reads each package's `shadow.css` just ahead of its
`theme.css`, in `lf-base` for a widget package and `lf-theme` for a theme package; an
adopted widget default sheet also uses `lf-base`. Use inherited
theme inputs for changes that should reach both roots, a package shadow sheet for
its internal selectors, or an explicitly exported `::part` for a public control.
A page selector alone cannot restyle private shadow descendants.

The override contract distinguishes four kinds of custom property:

| Kind | Owner and supported use |
| --- | --- |
| Theme inputs | Page authors and themes may set semantic colors (`--paper`, `--ink`, `--muted`, `--accent`, `--ok`, `--danger`), type faces (`--serif`, `--sans`, `--mono`), type/reading scales, radius (`--r`), code palette (`--code-*`), focus inputs, and page geometry, which Layouts read: the column's widths (`--col`, `--wide`), the sidebar's width (`--sidebar`), and the room above and below the page (`--page-pad-start`, `--page-pad-end`). Set them on the document root for a page-wide change; inherited inputs can also style a local subtree. The theme owns shared defaults and derivations; diff additions and deletions derive from the widget's local `--ok`, `--danger` and `--pre-bg`. Derived custom properties resolve where declared, so changing a local base color does not recompute an inherited derived token. `--focus-ring` draws outlines; `--focus-shadow` draws the equivalent shadow-based cue, so a custom complete ring updates both. Shared duration inputs `--lf-motion-flash`, `--lf-motion-fold`, and `--lf-motion-agent-arrival` are nonnegative document-root time values. `--lf-thread-panel-default-width` is a root length input until the user chooses a panel width. |
| Layout declarations | The allocating box sets `--lf-full-height`, `--lf-density`, `--lf-block-frame`, and `--lf-holds-edge` according to the contracts in `package-themes.md`, "A theme change". These express room or layout behavior; they are not palette knobs. |
| Runtime outputs | Runtime owners write measurements and choices such as `--lf-thread-panel-width`, banner row counts, anchor geometry, and retained body extents. Consumers read them; themes do not set them. `--lf-banner-face` is a stylesheet-owned responsive decision consumed by chrome and JavaScript. |
| Vendor bridges | The dependency adapter maps Leaf inputs to provider properties such as `--wa-*`, `--diffs-*`, and `--plot-background`. Change the Leaf input or the owning adapter, rather than repeating a provider recipe in each consumer. |

A `--lf-` prefix alone does not identify an input: most such values are private
outputs. A package documents any additional supported inputs beside its component.
A control's geometry remains constrained by its touch target and focus clearance;
a typography or color override does not remove those requirements.

Icon, widget,
and vendor files replace by path. Runtime modules add package-owned paths; they
cannot replace the kernel's JavaScript, including `leaf.js`.
Those modules are private, and Leaf compiles them together into one kernel.
Package checks refuse imports of private kernel modules as well as replacements,
so source modules and the compiled kernel expose the same extension contract.
`/runtime/widget-api.js` is the public behavior-module interface, shared with
the running kernel rather than copied into each widget.
A later package replaces a complete ordinary vocabulary entry, whether an element
or an idiom, and one member inside a shared `$` declaration. An ordinary entry can
be added or replaced whole, but it has no deletion marker.
Shared `$` entries compose by member, and map-valued members compose one level further
by key; `null` deletes at either of those shared-entry grains when the merged registry
still validates. Instructions files with the same audience name concatenate in package order.
The merged vocabulary is validated before vendoring.

Each file directly under `instructions/` is named `<audience>.md`; the filename must
match `[a-z][a-z0-9-]*\.md`. These instructions apply across the package. The
composed text sets each package's passage under a heading naming the package, so
a file begins with its first rule rather than a title of its own. Packages define
audiences such as `author`, `coordinator`, or `worker`; Leaf does not keep a role
list. A data contract's `instructions` map holds audience-specific text beside
its schema. An ordinary vocabulary entry's `x-instructions` is one non-empty string for the page author.

```bash
leaf page instructions PAGE | jq 'keys'
leaf page instructions PAGE --use lf-options --use .eyebrow | jq -r '.author // empty'
leaf page instructions PAGE --contract unified-diff | jq -er '.producer'
```

The command returns a JSON map from audience to complete instructions; no
instructions is `{}`. Without a selection, it includes only shared package
instructions. Each repeated `--use ENTRY` selects an ordinary registry entry,
including an idiom. Its `x-instructions` joins the `author` audience. Elements and idioms used
in its `x-example` and its declared `x-data` contracts join the selection
recursively, once each. Contract instructions join their declared audiences.
Whoever takes a role reads that audience's value for the same selection before
acting. "Read the registry" in `page-authoring.md` owns when an author reads each
part.

The reader uses the candidate vocabulary: the layer just vendored and any
`page/registry.json` declarations. It is available before the page has markup
and while an author revises markup against newly selected packages.

Composition order is kernel, bundled default package, selected packages in command
order. Later packages win collisions. `page init`
records package selections under `$layer.packages`; a plain re-init resolves them again
in the same order. `page init --no-packages PAGE` clears the explicit list.

A replacement `icon.svg` must be valid SVG and contain an element with
`class="lf-tone"`. The runtime paints the page's status on that element; without it,
the tab mark cannot say whether the page is working, waiting, or offline.

## A widget

The element declaration is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the user sees as words, its action verbs and their record forms, whether it
stands as one of the page's asks. The merged registry's `$keys` entry defines each key,
and `$state` defines each `x-state` verb member, including `creates` for user-added
children, while `$awaits` defines its ask's typed value and completion. Every element
declaration carries a non-empty `description`: short prose stating the widget's
purpose and when to use it. The attribute schema and valid `x-example` describe
its form. Optional `x-instructions` states the authoring choices and obligations
needed when the widget is selected. Page-wide composition and selection rules
belong in the authoring reference or shared package instructions; implementation
mechanics belong in the owning module's contract.

A `boolean` attribute is present or absent, as in HTML, so it names what its presence
means, and the widget's default is its absence: `lf-diff collapsed`,
`lf-options multiple`, `lf-shot outlines`. A feature a page usually wants is still
off until the author asks for it, and the instructions that route to the widget say
when to ask.

The shipped element declarations are the worked examples. For the keys that reshape a
widget's role on the page:

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

A CSS-only widget is an entry and a theme rule. One with reusable behavior takes a
module. The widget owns its implementation: supporting modules can sit beside its entry
module and use relative imports, while third-party or data files can live under
`vendor/`. `page init` carries both directories into the page with the registry and
theme.

Browser behavior follows [module-authoring.md](module-authoring.md), which owns module
obligations and the public browser API. The state meaning of registry declarations
is in [package-data.md, "User state"](package-data.md#user-state).

## Seeing it

Before a page uses the package, `leaf package check PACKAGE --render` draws the worked
examples of the widgets the package's own `registry.json` declares, in the browser
`page check --render` uses, and prints one line per finding: the widget, the check,
and what the check measured. A finding is advice for the widget's author: it refuses
nothing, and the exit status ignores it. The command fails only where the package
check does or the examples cannot be drawn; where no browser launches, it says the
examples were not drawn. Examples share a
page where their ids allow, so one example may point at an element another declares,
and a blank image stands in for any media an example names. `--json` prints the
result as one object in the shape `page check --json` prints, each finding a record
with its `code`, the element it names as `at`, and the measured `values`; a package
the check refuses is reported as its one `package` finding. The checks:

- `example`: no worked example shows the tag, so no other check reads it.
- `keeps-first-box`: the widget's box once the page presents differs from its box at
  first paint. Size the widget for first paint as
  [module-authoring.md, "First paint"](module-authoring.md#first-paint) describes. A
  widget holding others is named only for the change left once the changed widgets
  inside it are put back to their first sizes. An inline widget's old lines are more
  than a size, so a widget holding a changed inline one is named beside it. A widget
  the page hides once presented, such as an inactive tab, is left to the widget that
  hid it.
- `grows-with-content`: a box in the widget holds its own height and scrolls inside
  it. In ordinary flow a widget grows with what it holds, and a long one is read in
  the page's scroll (`page-layout.md`, "Bounds and widths"). The check names a box
  that scrolls vertically, and one whose CSS asks to and that overflows once a tall
  block is added to it, so a height the theme sets is found even while the widget's
  rows are empty. A
  box whose task needs its own scroll, such as an inspector whose contents change
  under a playing recording, declares `--lf-holds-height: 1` on itself; a bounded
  block's theme and the workspace Layout's scrolling regions already declare it. A
  widget that scrolls a part within the height a workspace gives it
  (`--lf-full-height`) declares it on that part too, though this check never sees
  that part scroll, since a worked example stands outside a workspace. A box that
  asks to scroll only sideways is named only while its content runs past its height.
- `shows-context-keys`: a command declares `contextKeys` and no `bindingBadge`, so its
  key works with nothing on the page showing it. Lend the
  command a face, or ask for a corner badge with `bindingBadge: null`
  (module-input.md, "Commands and keyboard routes"). The check reads the commands
  the example declares, so a command only another state declares, such as a
  multiple-choice ask's Done, needs an example in that state to be read.

After `leaf page init` re-vendors the page (`serving-pages.md`, "Re-vendoring and
layer epochs"), run `leaf page check <page> --render` on the version that uses
the replacement layer. Note the re-vendor in the next stamped version's changelog.

The render gate is where a module's mistakes surface — an upgrade that defines no element, a widget of no
size, a `x-verbatim` the rendered words contradict, a shadow root the declaration doesn't
declare, a word the registry promised that never reached the page, an attribute left on
the element that its declaration doesn't name, a `renderState` that changes the page when handed the same state again.

Then put it on the page. A widget is reviewed in place: the version that follows the
comment uses it where the comment asked, and the user comments on it there.
