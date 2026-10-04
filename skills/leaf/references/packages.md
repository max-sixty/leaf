# Packages

A package is the directory Leaf authors, shares, and adds to a page. It may hold a
theme, one widget, a family of widgets, helper modules, libraries, external-data
contracts, or any combination of them. The layer is different: it is the checked
result that `page init` vendors after composing the kernel and packages.

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
`~/.local/state/leaf/packages/`, where `--package NAME` reaches it by its directory
name from any project on this machine:

```bash
leaf package install packages/callout
leaf page init --package callout PAGE
```

The copy holds the package contract below, `scripts/` included, and nothing else in
the source directory, so a README and the author's own tests stay behind. A name that
a bundled or already installed package answers to is refused rather than replaced;
remove the installed directory to replace one. A page records the bare name, so
re-vendoring it on another machine needs the same package installed there.

The optional bundled packages are:

| Package | Adds |
| --- | --- |
| `code-review` | Review-authoring instructions; select alongside the evidence packages the page needs. |
| `diagram` | `lf-diagram` and its Agentic Mermaid renderer. |
| `diff` | `lf-diff`, the `unified-diff` data contract, and the Pierre renderer. |
| `swipe` | A pass-or-keep technical backlog deck. |
| `playground` | Controls and structured state with shared reset, restore, preview, output, and typed configuration submission. |
| `targeting` | Preview-element selection and structured, reversible change proposals. |
| `command-hub` | Multi-agent orchestration widgets. |
| `pr-review` | A typed pull-request brief with a safe Markdown description and compact checks table, plus a data-backed unified call diff. |
| `monitoring` | Release-workspace instructions for current state, checks, a run log, and a rollback Ask. |
| `visual-review` | Ordered website cases with aligned before-and-after evidence, automatic comparison orientation, authored focus and full-frame context, flip and overlay, fit and captured-size inspection, exact preview links, and dispositions. |
| `gallery` | Static action controls, disclosures, and status indicators for the developer feature gallery; ordinary pages do not select it. |

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
├── runtime/            browser modules and replacements by vendored path
├── widgets/            entry modules and their private helpers
├── vendor/             third-party libraries or data files
├── scripts/            command-line tools `leaf package run` runs; never vendored
├── icon.svg            optional replacement by path
└── leaf.js             optional runtime replacement
```

No individual file is required. The kernel supplies the files every complete layer
needs. Theme files concatenate into one cascade layer, `lf-base`; specificity,
native scope proximity, then source order decide between its rules. Layouts and
semantic state rank above package defaults; the page's unlayered stylesheet ranks
above all of them. In declared shadow trees, shared `shadow.css` rules rank above
widget defaults and below semantic state. A behavior module placing third-party
CSS in a `<style>` uses `inBaseLayer(text)` from `/runtime/widget-api.js`: it puts
the vendor's rules, including any nested layers, in the widget-default tier.
Composition wraps each widget package's sheets in native `@scope`: the document
roots are its declared widget tags, and shadow roots are their `:host`. Matching
stays inside those roots automatically. Ordinary selectors name descendants;
`:scope` names a root, with `:scope:is(lf-tag)` selecting one kind in a package.
In shadow CSS, `:scope:host(.state)` reads the host's state. Outside conditions
belong in nested scopes, such as `@scope (html[data-lf-interactive] :scope)`.
A rule for `p` styles only paragraphs inside the package's widgets. A rule for
`html`, `body`, or a widget's containing box matches nothing. Put shared page
vocabulary in the kernel; a package without widgets is an unscoped page theme.
A widget module's adopted sheet joins the same layer. Shadow files concatenate:
a declared `x-shadow` root built with `shadowStage` receives every package's `shadow.css`
in layer order, and the document reads each package's `shadow.css` just ahead of its
`theme.css`. Runtime, icon, widget,
and vendor files replace by path. A later package replaces a tag's complete element
declaration and one member inside a shared `$` declaration. A tag can be added or
replaced whole, but it has no deletion marker.
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
its schema. A widget's `x-instructions` is one non-empty string for the page author.

```bash
leaf page instructions PAGE
leaf page instructions PAGE author --widget lf-options --widget lf-chart
leaf page instructions PAGE producer --contract unified-diff
```

With no audience, the command lists the audiences available for that selection
as a JSON array.
With an audience, it prints shared package instructions and instructions for the
explicitly selected widgets and contracts. Without a selection, it prints only
shared package instructions. Each repeated `--widget TAG` includes the widget's
required members, custom tags in its worked example, and declared `x-data`
contracts; the reader derives those dependencies from the registry. Widget
instructions join the `author` audience. Contract instructions join their
declared audience. The author instructions name other available audiences so
an agent can assign work with the right instructions. "Read the registry" in
`page-authoring.md` owns when an author reads each part.

The reader uses the candidate vocabulary: the layer just vendored and any
`page/registry.json` declarations. It is available before the page has markup
and while an author revises markup against newly selected packages.

Composition order is kernel, bundled default package, selected packages in command
order. Later packages win collisions. `page init`
records package selections under `$layer.packages`; a plain re-init resolves them again
in the same order. `page init --no-packages PAGE` clears the explicit list.

A replacement `runtime/layer-client.js` must retain the quoted
`"__LEAF_LAYER_GENERATION__"` placeholder exactly once. `page init` replaces it
with the same fresh epoch it writes into the merged registry; without that pair,
a runtime loaded before a re-vendor could speak the replacement registry as though
the two files were one contract.

A replacement `icon.svg` must be valid SVG and contain an element with
`class="lf-tone"`. The runtime paints the page's status on that element; without it,
the tab mark cannot say whether the page is working, waiting, or offline.

## A theme change

Tokens change every surface that reads them: `--accent`, `--r`, the three faces
`--serif` (body prose), `--sans` (apparatus: chrome, injected controls, and annotations
embedded in evidence), and `--mono` (literal evidence). Ordinary selectors tune one
element or widget. A shape the project reuses across pages is an idiom — declare it
under `$idioms` in the package's
`registry.json` (a selector, a description, an example) and style it in the layer's
`theme.css`; the page's merged `registry.json` then carries it beside the shipped ones.

A rule that draws a box's inset — padding, border, or tinted field — declares
`--lf-block-frame: 1` in the same rule. The shared layout uses that declaration to trim child
margins and bound wide content. A box that is a section of the page's own flow rather than a
box on it, as a page tab's panel is, also declares `--lf-page-flow: 1`, so wide content in
it takes the page's room and a table in it keeps to its content. The trim follows the frame's edge down through each
first or last child, so a wrapper between the frame and the margin it trims declares
nothing. A box that lays its children
out side by side (a flex row, a grid) declares `--lf-holds-edge: 1`, so the trim stops at
it rather than taking one item's margin and leaving the others'.

Delivery paints declared layout facts into the served document as `[data-lf-inline]`,
`[data-lf-space]`, `[data-lf-bound]`, `[data-lf-height]`, `[data-lf-exhibit]`, and
`[data-lf-views]`; shared selectors read those attributes instead of naming widget
tags. The registry's `$keys` entries for `x-space`, `x-bound`, and `x-height` say what
each declaration requests; none of them chooses the widget's internal layout, which the
package arranges inside the allocation.
An element whose attributes name page media also arrives with the largest width and the
largest height among those images, read from their bytes, as `data-lf-media-width` and
`data-lf-media-height`, so a theme can give a frame the images' shape before they decode
(`aspect-ratio: attr(data-lf-media-width type(<number>)) / attr(data-lf-media-height
type(<number>))`, as `lf-shot` does).
How wide the page is, and how its blocks are arranged, is the page's choice, made with a
Layout class or its own CSS (`page-authoring.md`, "Layouts"); a package's element fills
the box it is given, and its `x-space` states the width it prefers, which a page may
override.
A widget that needs a minimum width to stay usable, such as a board's columns at a
readable size, states it as `min-inline-size` capped by the box it stands in:
`min(<its floor>, 100cqi, var(--lf-box-cap, 100vw))`. `100cqi` measures the nearest size
container, which is the page's shell or a framed box around the widget (a pane's body, a
card), and a sample, which cannot be one, states `--lf-box-cap`. So in a box
narrower than the floor the widget scrolls inside itself rather than widening the page.
When a bounded widget's scroller should be a box inside it, such as a listing under a
caption that stays in view, the package theme moves the bound there under
`[data-lf-bound]` and declares `--lf-bound-box: 1` on that box, which is the one Leaf
registers as the block's reading region and keeps on its newest entry. A box a
package scrolls sideways needs no declaration of its own: the runtime
measures every scroller on each layout and marks each edge with content beyond it.
Leaf fades the content at those edges, so a widget that has to scroll says so without
the package writing anything. An interactive
affordance stands down inside `[data-lf-exhibit]`, where the widget is quoted rather
than offered. The stylesheet is
inlined into an export, which opens offline, so use fonts available on the user's
machine rather than a remote font.

Startup behavior and transition protection follow
[module-authoring.md, "Startup and presentation"](module-authoring.md#startup-and-presentation).

## A widget

The element declaration is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the user sees as words, its action verbs and their record forms, whether it
stands as one of the page's Asks. The merged registry's `$keys` entry defines each key,
and `$state` defines each `x-state` verb member, including `creates` for user-added
children, while `$awaits` defines when a widget's Ask is answered. Every element
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
| `x-required-members` | `lf-swipe-deck` in `swipe`                                     |
| `x-visual`           | `lf-chart` declares `whole`, `lf-diagram` in `diagram` `parts`  |
| `x-bound`            | `lf-activity`                                                  |
| `x-height`           | `lf-chart`                                                     |
| `x-history`          | `lf-activity`                                                  |
| `x-patch`            | `lf-tabs`                                                      |
| `x-views`            | `lf-tabs`                                                      |
| `x-thread-surface`   | `lf-diff` in `diff`, `lf-visual-review` in `visual-review`     |
| `x-face`             | `lf-suggestion` (its slots), `lf-shot` in `default` (its rail) |

A CSS-only widget is an entry and a theme rule. One with reusable behavior takes a
module. The widget owns its implementation: supporting modules can sit beside its entry
module and use relative imports, while third-party or data files can live under
`vendor/`. `page init` carries both directories into the page with the registry and
theme.

Browser behavior follows [module-authoring.md](module-authoring.md), which owns module
obligations and the public browser API. Registry declarations and their state
meaning stay in the sections below.

## User state

A widget whose user changes something records each change as an `action` event in the
page's append-only log. The package writes no storage or server code. It declares verbs
under the element's `x-state`, and Leaf validates each event at the log's one append
door, folds the log into current state, gives that state to the module, and lists it
for the agent under `state` in `leaf page state`.

The swipe package is a small complete example. `packages/swipe/registry.json`
declares one verb on `lf-swipe-deck` and the condition that answers its Ask, and
`widgets/lf-swipe-deck.js` subscribes to and dispatches it:

```json
{
  "x-state": {
    "swipe": {
      "detail": {
        "type": "object",
        "properties": {
          "card": { "type": "string" },
          "to": { "type": "string" },
          "rank": { "type": "string" }
        },
        "required": ["card", "to", "rank"],
        "additionalProperties": false
      },
      "unit": "card",
      "record": { "kind": "position", "within": "lf-swipe-pile", "value": "to", "rank": "rank" }
    }
  },
  "x-awaits": {
    "answered": {
      "swipe": { "empty": { "within": "lf-swipe-pile", "when": { "verdict": ["unseen"] } } }
    }
  }
}
```

`detail` is the JSON Schema every event of that verb must satisfy. Each verb is its own
piece of state: the owning element, the `unit`, and the verb together form the fold
coordinate. At each coordinate the latest surviving action stands, and different
coordinates stand side by side. Swiping a card again therefore replaces that card's
earlier verdict, while verdicts on different cards coexist. `unit` is `"widget"` for a
verb that states the whole widget's value at once, or the detail field naming the
element it is per. `record` says how the standing state reads in markup: here, the
card's position inside a pile. `page check` refuses a version that contradicts
it without `restated`, and `authoring-revisions.md`, "Honor user state", says which
record forms the agent's next version writes back. The `$keys`
entries in `assets/registry.json` define each key exactly.

`x-awaits.answered` says when the widget's Ask is answered, as a condition on that
standing state for each verb that can answer it. `{}` holds while the verb's state
stands, `when` narrows a verb to instances with matching attributes, and `empty` holds
while the named container inside the widget has no members. Here the deck is answered
once its `unseen` pile is empty, so the swipe that empties it is the answer and
returning any card reopens the Ask. The one-line forms elsewhere follow the same
shape: `"answered": {"edit": {}}` answers a draft once an edit stands, and
`"answered": {"choose": {"when": {"multiple": [false]}}, "answer": {"when":
{"multiple": [true]}}}` answers a single-choice group by its pick and a `multiple` group
by its Done press.

The module reads and writes through `widgetController(owner)`, described in
[module-authoring.md, "The widget controller"](module-authoring.md#the-widget-controller): `subscribe` delivers the authored baseline with the fold applied, and
`dispatch({kind: "action", verb, detail})` sends a gesture whose result is on screen
before the server admits it.

A verb that lets the user add a real child declares `creates: {child, words}`.
Its fold unit names the detail field carrying the new child's canonical element id,
`words` names the field carrying its non-empty words, and the detail holds exactly those
two required fields with no record form. Each added child therefore stands on its own
coordinate: a later action of another verb leaves it in place, and undoing the `add`
removes it. The child tag admits the sender through `x-owners`, requires only its
canonical `id`, and has `x-content: markup`. The append door refuses an id the sending
document already holds, and `page check` enforces the declared tag and
direct-ownership relation once an author writes the child into the markup.

A verb whose state the agent writes rather than the user declares `"writer": "agent"`
beside its `detail`, `unit`, and `record`. A worker posts it with
`leaf page report`, the page paints it live, and it stands until a version
answers it; the user has no control for it. Its record is required and may not be `body`, and it may name the detail field
carrying its short human-readable news with `update`. Every verb has exactly one
writer, so a coordinate never holds a user's action and an agent's report at once.
Command Hub's `lf-task` `status` is the shipped example, and a widget declaring such a
verb also declares the boolean `overruled` attribute a version keeps its own state
with. A worker that reacts to the user's actions follows them as they land with
`leaf page events PAGE --follow`.

## References between widgets

Use `x-refers` when authored attributes point at other page objects. Its value is
a map from attribute names to target contracts. `{}` accepts any existing element id.
A typed contract uses `via` to name a package-owned shared registry map and `where` to
match a declaration there:

```json
{
  "x-refers": {
    "target": { "via": "$command.widgets", "where": { "role": "goal" } },
    "worker": { "via": "$command.widgets", "where": { "role": "worker" } }
  }
}
```

Add `"owns": true` to a typed contract whose referrer fills its target, as a command
fills the readings seat it names. `page check` then requires the target in the
referrer's own document, and every element there that the predicate selects named by
exactly one referrer, so no seat stands empty or holds two commands' readings.

Leaf validates the generic relation; the package owns the map, roles, and participating
widget tags. A later package can therefore add another goal or worker widget by merging
its entry into `$command.widgets`, without changing core.

## External or derived data

Authored markup says what a version begins with; the event log says what users and
agents did afterward. A current deployment, sensor reading, worktree, or query result
is neither. Leaf keeps that third authority as one replaceable JSON file per source.

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
Widget-specific authoring instructions travel in `x-instructions`;
contract-specific producer instructions travel beside the contract in the
`instructions` audience map. Shared package instructions apply to the package as
a whole. "Package contract" defines how a reader selects them.

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
    "x-content": "empty",
    "x-data": {
      "builds": {
        "contract": "build-status",
        "source": "source"
      }
    },
    "x-instructions": "Bind `source` to the build feed this page should show.",
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

The harness gathers the value; Leaf does not run a provider or fetch a package URL. Set a
complete value using the page's source id:

```bash
printf '%s' '{"main":"passing"}' | leaf data set PAGE release-ci
leaf data set PAGE release-ci --file build-state.json
sed -n '20,44p' CHANGELOG.md | jq -Rs . | leaf data set PAGE release-notes
leaf data clear PAGE release-ci
```

Each source's value is an ordinary JSON file at `data/<source>.json` in the page
directory, and `data.json` records the contract each source id was first set under.
`data set` checks the binding and validates the value before replacing that file
atomically; a rejected value leaves the file untouched. Once a source has been set,
any process may rewrite its file with plain JSON. Every reading validates the file
against the contract, so a value that fails it reaches users as that source's error
rather than as data, and `page check` and `page state` report it. Tabs hear a
rewritten file as they hear any other page change.

A source's revision is a digest of its file's bytes, and its `updated` instant is the
file's modification time. Nothing keeps a replaced value: every document that binds a
source reads its current value, including stamped versions and widgets frozen into
threads. A document that must keep one value binds its own source id and nothing
rewrites that source. Source revisions and event sequences are independent: an old poll
may contain new data, and a new event response may contain old data, so neither orders
the other.

Leaf derives no values: `data set` stores the value it is given. A value that has
to be derived from a file — a text excerpt, a patch split into files — is the
producer's to build, and a contract that needs more than `jq` says how in its
producer `instructions`. A package may ship that tool
as a Python file under `scripts/`, declaring its dependencies in inline script metadata
(PEP 723) with floors and no cap. `leaf package run NAME SCRIPT [ARGS]...` finds the
package by the name `--package` selects it by, bundled or installed, and runs the
script with `uv run --script` in the environment its header declares, apart from
Leaf's own. The script owns stdin, stdout, and the exit status, so the instructions state the
pipeline with no path in it:

```bash
git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE review-patch
```

`package check` and `package install` refuse a `scripts/*.py` without that header,
since uv would run it in whatever project the caller's directory reaches, and refuse a
constraint other than a `>=` floor. A subdirectory of `scripts/` holds helpers and is
not checked or run. A page never vendors `scripts/`. When a producer upstream of `data set` fails and
writes nothing, `data set` refuses the empty input and points back at that producer's
own error.

A source id keeps one contract for the lifetime of the page. `data clear` removes the
current value and keeps the recorded contract, so the id is never released for a new
meaning. Use a new source id for a new contract. Re-vendoring preserves each binding
and refuses an incoming registry that would change a bound contract's schema.
`leaf page state PAGE` exposes the complete `data_bindings` inventory so a producer can
discover the ids, contracts, widgets, and documents it needs without parsing markup.
Every source value goes to every user of the page, including fields a module does not
paint. Do not put credentials or private host state in it.

A contract whose value holds keyed rows declares `records`: the top-level array field
and each row's key field. A source replacement is accepted only when every row has a
non-empty, unique string key. Rows that each carry a large, independently useful
payload may name that field `deferred`. The source file still holds the complete value,
and readings validate all of it, but `/api/state` sends each row with that field
omitted; a widget uses `loadDeferred(snapshot, key)` to fetch one row's payload
using the delivery `watchData` handed it. A request naming a source revision the file
no longer holds is refused instead of combining a new payload with an old manifest.
This is how a collapsed `lf-diff` can show thousands of files without transferring or
rendering every patch first.

```json
{
  "records": { "items": "files", "key": "key", "deferred": "patch" },
  "schema": {
    "type": "object",
    "properties": {
      "files": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "key": { "type": "string" },
            "patch": { "type": "string" }
          },
          "required": ["key", "patch"]
        }
      }
    },
    "required": ["files"]
  }
}
```

Browser subscriptions and rendering follow [module-authoring.md, "Data subscriptions and
projections"](module-authoring.md#data-subscriptions-and-projections).

## Seeing it

Before a page uses the package, `leaf package check PACKAGE --render` draws the worked
examples of the widgets the package's own `registry.json` declares, in the browser
`page check --render` uses, and prints one line per finding: the widget, the check,
and what the check measured. A finding is advice for the widget's author: it refuses
nothing, and the exit status ignores it. The command fails only where the package
check does or the examples cannot be drawn; where no browser launches, it says the
examples were not drawn. Examples share a
page where their ids allow, so one example may point at an element another declares,
and a blank image stands in for any media an example names. The checks:

- `example`: no worked example shows the tag, so no other check reads it.
- `keeps-first-box`: the widget's box once the page presents differs from its box at
  first paint. Upgrade should add behavior and move nothing, so size the widget in
  the package theme, under `html[data-lf-interactive]`, which Leaf sets before first
  paint wherever its runtime will run, in a served page or an export, as its module
  will draw it. Where the markup cannot say how tall the drawing will
  be, declare `x-height`, add the class `lf-rendered` once the drawing is in, and
  draw at the stated height where the drawing can take any; `page check --render`
  advises a page's author the height to state for one that cannot. Where the widget
  shows one of its members at a time, declare `x-views`, open on `openingView`'s
  member, and show only the member marked `data-lf-opening` until the module upgrades
  the element, as `lf-tabs` does. A widget holding
  others is named only for the change left once the changed widgets inside it are put
  back to their first sizes. An inline widget's old lines are more than a size, so a
  widget holding a changed inline one is named beside it. A widget the page hides once
  presented, such as an inactive tab, is left to the widget that hid it.

After `leaf page init` re-vendors the page (`serving-pages.md`, "Re-vendoring and
layer epochs"), run `leaf page check <page> --render` on the version that uses
the replacement layer. Note the re-vendor in the next stamped version's changelog.

The render gate is where a module's mistakes surface — an upgrade that defines no element, a widget of no
size, a `x-verbatim` the rendered words contradict, a shadow root the declaration doesn't
declare, a word the registry promised that never reached the page, an attribute left on
the element that its declaration doesn't name, a `renderState` that changes the page when handed the same state again.

Then put it on the page. A widget is reviewed in place: the version that follows the
comment uses it where the comment asked, and the user comments on it there.
