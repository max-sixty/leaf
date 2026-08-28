# Packages

A package is the directory Leaf authors, shares, and adds to a page. It may hold a
theme, one widget, a family of widgets, helper modules, libraries, external-data
contracts, or any combination of them. The layer is different: it is the checked
result that `page init` vendors after composing the kernel and packages.

Read this reference when a design comment arrives with `"about": "layer"`, or
when `/leaf` is invoked on a widget to build or a look to change.

## Package roles

| Package | Reaches |
| --- | --- |
| a package selected with `--package` | pages that select its path |
| the project's `.leaf/` | pages initialized from the project |
| the user's `~/.config/leaf/` | pages initialized for that user |
| Leaf's bundled default package | every page |

Presentation used by only one page stays in that version's `<style>`. Everything
reusable belongs to a package. Leaf creates and validates the whole directory:

```bash
leaf package init PACKAGE
leaf package check PACKAGE
```

`package init` creates `registry.json`, `theme.css`, `guidance/`, `runtime/`,
`widgets/`, and `vendor/` without replacing existing contents. The package author
edits that directory, then checks its composition before adding the package to a page:

```bash
leaf package init packages/callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
```

An explicit directory keeps a contribution separately owned and selectable. `.leaf`
is the project package and `~/.config/leaf` is the user package. Inside a repository
dedicated to one package, use `.` as the package path.

## Package contract

Every package has the same partial layout:

```text
package/
├── registry.json       widget entries and shared $ declarations
├── theme.css           rules appended to the cascade
├── guidance/           Markdown guides named for their audiences
├── runtime/            browser modules and replacements by vendored path
├── widgets/            entry modules and their private helpers
├── vendor/             third-party libraries or data files
├── icon.svg            optional replacement by path
└── leaf.js             optional runtime replacement
```

No individual file is required. The kernel supplies the files every complete layer
needs. Theme files concatenate. Runtime, icon, widget, and vendor files replace by
path. A later package replaces a tag's complete registry entry and one member inside
a shared `$` entry. Guidance files with the same audience name concatenate in package
order. The merged vocabulary is validated before vendoring.

Each file directly under `guidance/` is named `<audience>.md`; the filename must match
`[a-z][a-z0-9-]*\.md`. Those files are for guidance that applies across the package.
A widget attaches its own guidance through `x-guidance`, while a data contract may
carry producer guidance beside its schema. Packages define audiences such as `author`,
`reviewer`, or `worker`; Leaf does not keep a role list. `leaf page guidance PAGE` lists
the audiences in the vendored page, and `leaf page guidance PAGE AUDIENCE` composes all
three sources. `page catalog` also prints the complete `author` reading after the merged
vocabulary.

Composition order is kernel, bundled default package, explicit packages in command
order, user package, then project package. Later packages win collisions. `page init`
records explicit paths under `$layer.packages`; a plain re-init resolves those paths
again in the same order. `page init --no-packages PAGE` clears the explicit list.

Explicit package paths are project-relative or start with `~`. Absolute paths are
refused because the vendored registry is public. A package may contain zero, one, or
many widgets. Those cardinalities do not change its contract.

A replacement `leaf.js` must retain the quoted
`"__LEAF_LAYER_GENERATION__"` placeholder exactly once. `page init` replaces it
with the same fresh epoch it writes into the merged registry; without that pair,
a runtime loaded before a re-vendor could speak the replacement registry as though
the two files were one contract.

## A theme change

Tokens change every surface that reads them: `--accent`, `--r`, the three faces
`--serif` (the page's prose), `--sans` (the chrome and every injected control) and
`--mono` (evidence). Ordinary selectors tune one element or widget. A shape the project
reuses across pages is an idiom — declare it under `$idioms` in the package's
`registry.json` (a selector, a description, an example) and style it in the layer's
`theme.css`; `page catalog` then lists it beside the shipped ones. Presentation unique to
one page stays in that version's `<style>`.

## A widget

The registry entry is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the reader sees as words, its action verbs and their record forms, whether it
stands as one of the page's asks. `page catalog` prints what each key means (`$keys`) and
the shipped entries are the worked examples; the entry's `x-example` must validate, and
is what the catalog shows.

A CSS-only widget is an entry and a theme rule. One with behavior takes a module. The
skill's own `CLAUDE.md`, one directory up from this file, defines what the module owes:
an absolute `applyAction`, `says()` over `textContent`, `offer()` and `relabel()` on anything
injected, `keys()` at upgrade — through `DISCLOSE(el)` over anything that folds, the
runtime owning those keys — `quoted()` before wiring input, `actionAvailable()` for
an x-state verb with `requires`, and durable state in attributes because export drops
the scripts. `/runtime/widget-api.js` is the whole Leaf API a behavior module gets.
The widget still owns its implementation: supporting modules can sit beside its entry
module and use relative imports, while third-party or data files can live under
`vendor/`. `page init` carries both directories into the page with the registry and
theme.

Every row passed to `keys()` has a stable dotted `id`, such as `draft.save`. Keep that
identity when its key or wording changes: the command browser and repeated widget
instances use it instead of display prose. If one compact row binds keys with different
meanings, add `routes` with an `id`, `binding`, and action sentence for each meaning. The
key line stays compact, while the `?` command browser lists and runs each route on its own.
Use `runFromReference: false` only for a parameterized step that cannot be run without a
choice the reference does not have, such as the partly entered digits of an address. An
optional `reach` on a row or scope supplies the short place phrase shown when a command is
not available (for example, `in an open draft editor`).

## External or derived data

Authored markup says what a version begins with; the event log says what readers and
agents did afterward. A current deployment, sensor reading, worktree, or query result
is neither. Leaf keeps that third authority in replace-in-place source snapshots.

The source id belongs to the page: it says which concrete feed this page uses. Its
meaning comes from a named contract under `$data.contracts`, which can travel in any
package and be shared by more than one widget:

```json
{
  "$data": {
    "description": "Reusable build-data contracts.",
    "contracts": {
      "build-status": {
        "description": "Current result keyed by branch.",
        "schema": {
          "type": "object",
          "additionalProperties": { "enum": ["passing", "failing"] }
        }
      }
    }
  }
}
```

A widget declares the inputs it knows how to present. Each input names its contract and
the attribute that will carry the page's source id. Make that attribute required when
the widget cannot work without the input; an optional unbound input delivers `null`.
Widget-specific operating
instructions can travel in `x-guidance`; contract-specific producer instructions can
travel beside the contract in `guidance`. Package guidance files are for instructions
that really apply to the package as a whole.

```json
{
  "lf-builds": {
    "type": "object",
    "properties": {
      "id": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
      "source": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" }
    },
    "required": ["id", "source"],
    "additionalProperties": false,
    "x-content": "none",
    "x-data": {
      "builds": { "contract": "build-status", "source": "source" }
    },
    "x-guidance": {
      "author": "Bind `source` to the build feed this page should show."
    },
    "x-upgrade": true
  }
}
```

The page makes the concrete binding in ordinary authored markup. Several widgets may
share one source when they read the same contract; two independent feeds use different
ids.

```html
<lf-builds id="release-builds" source="release-ci"></lf-builds>
```

The host gathers the value; Leaf does not run a provider or fetch a package URL. Set a
complete snapshot using the page's source id:

```bash
printf '%s' '{"main":"passing"}' | leaf data set PAGE release-ci
leaf data set PAGE release-ci --file build-state.json
leaf data clear PAGE release-ci
```

`data set` validates before replacing the source atomically. A rejected value leaves
the prior revision untouched. Source revisions and event sequences are independent:
an old poll may contain new data, and a new event response may contain old data, so
neither orders the other.

A source id keeps one contract for the lifetime of the page. Every immutable version
and every widget frozen into a thread shares the page's current data store, so a later
document cannot reuse an old id with a new meaning. `data clear` removes the current
value, not that identity. Use a new source id for a new contract. Re-vendoring preserves
this mapping as well as validating any standing values against the incoming schemas.
`leaf page state PAGE` exposes the complete `data_bindings` inventory so a producer can
discover the ids, contracts, widgets, and documents it needs without parsing markup.
Every source value goes to every reader of the page, including fields a module does not
paint. Do not put credentials or private host state in it.

A module subscribes through its own input declaration:

```js
this.stopWatching = watchData(this, "builds", (snapshot) => {
  render(snapshot?.value ?? {});
});
```

The callback receives `null` before the host has supplied a value, otherwise a clone of
`{contract, updated, value}`. It runs immediately and again when Leaf asks subscribers
to restate their view. Return the cleanup function from the element's disconnect path.
The callback must state the whole rendering and remain idempotent.

Render the value with `projectData(root, records, keyOf, render)`. The root is an
id-bearing authored seat and owns the projection's children. `keyOf` returns a stable
non-empty string for the logical datum; `render` receives
`(record, priorNode, index)` and returns its element, reusing `priorNode` where that
preserves a focused control or selection. Leaf marks those words as readable data
rather than authored prose, reconciles their order, and keeps comments attached by the
projection/key pair even when a refresh replaces the text nodes. Export keeps the last
rendering as a labelled snapshot and drops the code that could refresh it.

## Seeing it

After the main skill's re-vendoring route restores the recorded URL, run
`leaf version check <page> --render` on the version that uses the replacement
layer. Note the re-vendor in the next stamped version's changelog.

The render gate is where a module's mistakes surface — an upgrade that defines no element, a widget of no
size, a `x-verbatim` the rendered words contradict, a shadow root the entry doesn't
declare, a word the registry promised that never reached the page, an attribute left on
the element that its entry doesn't declare, an `applyAction` that moves under
re-application.

Then put it on the page. A widget is reviewed in place: the version that follows the
comment uses it where the comment asked, and the reader comments on it there. From the
terminal, `/leaf build a timeline widget for the release page` names the layer as its
subject, and the page it makes shows the widget in use.

## A design comment

The reader's design mode (`i` in the browser) posts a comment about the layer rather
than the page: `"about": "layer"`, anchored on the element they clicked or the words they
selected. The anchor's `section` is a widget's id, or the id of a runtime part —
`lf-banner`, `lf-comments` (the panel), `lf-leaves` (the leaves panel), `lf-versions`,
`lf-composer`, `lf-comment-button` (the margin's 💬), `lf-keyline`, `lf-help` — and
`part` names the control the click landed on, where it landed on one (`✓ Accept`,
`Comments (2)`).

```json
{"kind": "comment", "about": "layer", "version": 3, "anchor": {"section": "feeder-board"}, "text": "cards are cramped — give the column a floor"}
```

Answer it with the layer: change it where the table above says, `page init` the page,
stamp the version, and reply in-thread saying where the fix landed. The new version is
the answer, on the element the comment was made on. A comment naming leaf itself is the
hand-off above.
