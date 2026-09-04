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
| a package selected with `--package` | pages that select its name or path |
| the project's `.leaf/` | pages initialized from the project |
| the user's `~/.config/leaf/` | pages initialized for that user |
| Leaf's bundled default package | every page |

Presentation used by only one page stays in that version's `<style>`. Everything
reusable belongs to a package. Leaf creates and validates the whole directory:

```bash
leaf package init PACKAGE
leaf package init PACKAGE --widget lf-callout
leaf package check PACKAGE
```

`package init` creates `registry.json`, `theme.css`, `guidance/`, `runtime/`,
`widgets/`, and `vendor/` without replacing existing contents. Add `--widget TAG` to
create one upgraded prose widget at the same time. Leaf adds a valid registry example
and the matching `widgets/TAG.js` registration/`once` module, checks the resulting
composition, and leaves a new package's empty theme ready for the widget's presentation.
An existing theme and other package files remain in place. Leaf refuses a tag or module
that already exists rather than replacing it. The package author edits that directory,
then checks its composition before adding the package to a page:

```bash
leaf package init packages/callout --widget lf-callout
leaf package check packages/callout
leaf page init --package packages/callout PAGE
```

An explicit directory keeps a contribution separately owned and selectable. `.leaf`
is the project package and `~/.config/leaf` is the user package. Inside a repository
dedicated to one package, use `.` as the package path.

Leaf also ships optional packages that select by bare name. `diagram` adds `lf-diagram`
and the Beautiful Mermaid renderer it draws with; `diff` adds `lf-diff`, the
`unified-diff` data contract, and the Pierre renderer; `swipe` adds a pass-or-keep
technical backlog deck; `command-hub` adds multi-agent orchestration widgets;
`pr-review` adds a typed pull-request brief with a safe Markdown description and compact
checks table, plus a data-backed unified call diff:

```bash
leaf page init --package diagram PAGE
leaf page init --package diff PAGE
leaf page init --package swipe PAGE
leaf page init --package command-hub PAGE
leaf page init --package diff --package pr-review PAGE
```

Those two renderers are about 3.2MB, and most pages draw neither, so they travel in
packages rather than in the default one. A plain `page init` writes about 2.7MB; a page
that wants a diagram or a diff selects it explicitly.

`lf-call-diff` binds a captured `text-document` containing CallDiff-style plain text.
The analysis host owns that source; the widget keeps unchanged tree items beside
additions and removals, folds the result by changed root, and projects every row as a
commentable datum. Its required `diff` target turns source coordinates into navigation
to matching lines in the exact patch — an `lf-diff`, which is why the command above
selects `diff` beside `pr-review`. Packages declare no dependencies on each other; a
page states the whole list it needs. For a large repository, capture one affected file
or entry point per source rather than one unbounded call graph.

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
a shared `$` entry. A tag can be added or replaced whole, but it has no deletion marker.
Shared `$` entries compose by member, and map-valued members compose one level further
by key; `null` deletes at either of those shared-entry grains when the merged registry
still validates. Guidance files with the same audience name concatenate in package order.
The merged vocabulary is validated before vendoring.

Each file directly under `guidance/` is named `<audience>.md`; the filename must match
`[a-z][a-z0-9-]*\.md`. Those files are for guidance that applies across the package.
A widget attaches its own guidance through `x-guidance`, while a data contract may
carry producer guidance beside its schema. Packages define audiences such as `author`,
`reviewer`, or `worker`; Leaf does not keep a role list. `leaf page guidance PAGE` lists
the audiences in the vendored page, and `leaf page guidance PAGE AUDIENCE` composes all
three sources. The page author reads the `author` audience when the list includes it.

Composition order is kernel, bundled default package, selected packages in command
order, user package, then project package. Later packages win collisions. `page init`
records package selections under `$layer.packages`; a plain re-init resolves them again
in the same order. `page init --no-packages PAGE` clears the explicit list.

A bare package name selects an optional bundled package and never means a path; use
`./name` for a same-shaped project directory. Other package paths are project-relative
or start with `~`. Absolute paths are refused because the vendored registry is public.
The always-present `default` package cannot be selected explicitly. A package may
contain zero, one, or many widgets. Those cardinalities do not change its contract.

A replacement `leaf.js` must retain the quoted
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
Presentation unique to one page stays in that version's `<style>`.

A rule that draws a box's inset — padding, border, or tinted field — declares
`--lf-frame: 1` in the same rule. The shared layout uses that declaration to trim child
margins and bound wide content, and the render gate reports a frame that omits it. The
runtime exposes declared layout facts as `[data-lf-inline]`, `[data-lf-wide]`, and
`[data-lf-exhibit]`; shared selectors read those attributes instead of naming widget
tags. In particular, an interactive affordance stands down inside
`[data-lf-exhibit]`, where the widget is quoted rather than offered. The stylesheet is
inlined into an export, so use fonts available on the reader's machine rather than a
remote font a standalone copy would have to fetch.

`body[data-lf-presented]` means the initial authoritative projection, or the deliberate
offline fallback, is safe for recorded interaction. Authored content is already visible:
Leaf disables its arrival transitions and withholds dialogs, popovers, and durable widget
actions before that stamp. Package styles need no arrival guard. A declared `x-shadow`
widget gets the same transition and top-layer protection when it builds its root with
`shadowStage`. A module must guard every optimistic mutation with `actionAvailable` or
`requestAvailable`; the send door repeats the same check. Leaf's own anchored composer
uses the same stamp before it can capture or post a passage coordinate.

## A widget

The registry entry is JSON Schema over the element's attributes, plus the `x-` keys that
say how the layer treats the tag — its content model, whether a module upgrades it, which
attributes the reader sees as words, its action verbs and their record forms, whether it
stands as one of the page's decisions. The merged registry's `$keys` entry defines each key,
and the shipped widget entries are the worked examples. Every widget entry carries a
non-empty `description`. Its first plain sentence identifies the widget's purpose; the
rest explains its detailed contract. An entry's `x-example` must validate and is the
markup an author queries with that entry.

An items container that needs one child for every semantic role declares
`x-children: {"CHILD-TAG": {"one-each": "ATTRIBUTE"}}`. The child's attribute is a
required string enum, and the child admits the container through `x-parent`. `version
check` then refuses a missing or repeated enum value. This keeps fixed role sets in the
package contract without adding their tags or vocabulary to Leaf.

When a position action completes a Decision only after its own move empties a queue,
declare `completion: {empty: {within: "CONTAINER-TAG", when: {ATTRIBUTE: [VALUE]}}}`
on that x-state verb. `within` names an items container inside the answering widget and
`when` selects exactly one instance by static authored attributes. POST overlays the
candidate move on the authoritative holder relation before testing emptiness, and the
Decision projection uses the same condition for standing state. Do not add a second
completed attribute or trust the browser's optimistic item count.

A CSS-only widget is an entry and a theme rule. One with behavior takes a module. The
skill's own `CLAUDE.md`, one directory up from this file, defines what the module owes:
an absolute `applyAction`, `says()` over `textContent`, `offer()` and `relabel()` on anything
injected, `commands()` at upgrade — through `DISCLOSE(el)` over anything that folds, the
runtime owning those commands — `quoted()` before wiring input, `actionAvailable()` for
an x-state verb with `requires`, and durable state in attributes because export drops
the scripts. `/runtime/widget-api.js` is the whole Leaf API a behavior module gets.
The widget still owns its implementation: supporting modules can sit beside its entry
module and use relative imports, while third-party or data files can live under
`vendor/`. `page init` carries both directories into the page with the registry and
theme.

A widget contributes each capability once with `commands(source, title, rows, options)`.
The dispatcher, key line, `?` reference, `aria-keyshortcuts`, and Ask projection all
consume those same live rows. Mark a row or route with `decision: true` and give it
`control` and `label` when that control answers, advances, or revises the Ask containing
`source`. A row may have zero or one live binding in that role: zero receives the Ask's
next free contextual `1` through `9`, while one keeps its canonical binding, such as
`ArrowLeft`. Each action keeps its command id as an exact route; that route is the one
binding-to-control identity used by dispatch, the reference, the key line, its address, and
`aria-keyshortcuts`. `address` may name an empty face a widget already positions; core
writes the resolved binding there, so the package does not keep a second key map.
Otherwise core paints the binding at the visible control. Routes let one parameterized
row contribute distinct controls and bindings. The control's own `click()` remains the
single activation path.

When the scope belongs to an Ask, `options.answer` may read its concise current answer for
the answered row in the Asks tray. Leaf normalizes whitespace and bounds the displayed
answer; the package owns its meaning and words. Attach the answer reader to one stable scope
owned by the Ask, even when several descendant scopes contribute controls. Answer metadata
stays readable after a scope's capability gate closes, while the command rows remain gated.

Register the semantic capability, not every nearby button. Evidence nested inside an
option is not an answer, and a shared-margin Button may sit outside the Ask source. When
controls or availability change, keep the row fields computed and call `paintKeys()`;
every command projection then updates together. A package that needs the page-wide open
Ask set calls `watchDecisions(owner, callback)`. It invokes `callback(openDecisions)`
immediately, invokes it again after a complete decision projection reconciles, binds the
subscription lifetime to `owner`, and returns an explicit cleanup function. Packages do
not listen to Leaf's internal `lf-actions` invalidation event.

An `x-state` verb that lets the reader add real children declares
`creates: {field, child}`. The named optional detail field has the canonical
`{element-id: non-empty words}` map schema. The child tag admits the sender through
`x-parent`, requires only its canonical `id`, and has `x-content: prose`. `sendAction`
then records the map's sorted ids in `generated`, allowing registry-free historical
folds to retain their liveness while version checks enforce the declared tag and
direct-parent relation.

Every row passed to `commands()` has a stable dotted `id`, such as `draft.save`. Keep that
identity when its key or wording changes: the command browser and repeated widget
instances use it instead of display prose. If one compact row binds keys with different
meanings, add `routes` with an `id`, `binding`, and action sentence for each meaning. The
key line stays compact, while the complete reference lists and runs each route on its own.
Use `runFromReference: false` only for a parameterized step that cannot be run without a
choice the reference does not have, such as the member digit of a numbered address. An
optional `reach` on a row or scope supplies the short place phrase shown when a command
is not available (for example, `in an open draft editor`).

## External requests and receipts

Use `x-request` when a reader asks the host to perform a consequential one-shot
operation. Leaf records and validates the instruction; it never interprets the verb or
calls a provider. The package owns the verbs, controls, presentation, and guidance that
tells the host how to execute and recover them.

`offers` maps each direct child widget to the string-enum attribute that names its verb.
Every live request holder must contain at least one matching direct child and may offer
each verb only once; two differently worded controls that send the same instruction
cannot produce distinguishable requests. When a later revision has carried out the
instruction, remove the holder rather than leaving an empty Decision with no possible answer.
`verbs` gives each operation a closed detail schema. Optional `bind` entries require a
detail field to equal an authored string attribute on the holder, so a crafted event
cannot retarget the operation. Every bound detail field and holder attribute is required,
string-valued, and immutable through `x-state` or `x-report`; every offer attribute is a
required string enum on its child. These constraints make the same declaration usable at
authoring, browser, and server boundaries rather than leaving a partial bind to runtime
guesswork.

Use `x-refers` when those authored attributes point at other page objects. Its value is
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

Leaf validates the generic relation; the package owns the map, roles, and participating
widget tags. A later package can therefore add another goal or worker widget by merging
its entry into `$command.widgets`, without changing core.

Set `decision: true` when the ready operation is a question the reader must answer. Leaf then
puts that holder in the canonical Asks projection only while its lifecycle is `ready`.
Acceptance hands the turn to the host, so `pending` and `completed` holders leave the
reader's list; a failed receipt returns the lifecycle to `ready` and reopens the decision. A
parent `x-awaits.rollup` reads that same lifecycle, so nested task and header projections
do not need package-specific request bookkeeping.

```json
{
  "x-request": {
    "decision": true,
    "offers": { "lf-operation": "verb" },
    "verbs": {
      "restart": {
        "detail": {
          "type": "object",
          "properties": { "target": { "type": "string" } },
          "required": ["target"],
          "additionalProperties": false
        },
        "bind": { "target": "target" }
      }
    }
  }
}
```

The module imports `sendRequest`, `requestAvailable`, and
`watchRequestLifecycle` from `/runtime/widget-api.js`. The watcher receives the
server-projected seat, ordered `{request, receipt}` attempts, latest attempt, and
`ready`, `pending`, or `completed` phase. A failed receipt makes the seat ready again;
a successful receipt completes it. A page holder gets a new seat in a new authored
revision, while a holder in frozen thread markup keeps one seat for that document's
whole lifetime.

```js
const stop = watchRequestLifecycle(this, (lifecycle) => render(lifecycle));
if (requestAvailable(this, "restart"))
  await sendRequest(this, "restart", { target: this.getAttribute("target") });
```

The host uses the durable request id as its idempotency and recovery key, then records
exactly one outcome with `leaf receipt`. External evidence produced by the operation
belongs in typed page data; the authored page changes only when the author saves the
resulting plan revision.

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
      "source": { "type": "string", "pattern": "^[a-z][a-z0-9-]*$" },
      "snapshot": { "type": "string", "pattern": "^[1-9][0-9]*$" }
    },
    "required": ["id", "source"],
    "additionalProperties": false,
    "x-content": "none",
    "x-data": {
      "builds": {
        "contract": "build-status",
        "source": "source",
        "snapshot": "snapshot"
      }
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
<lf-source id="release-notes-source" source="release-notes" language="markdown"></lf-source>
```

The host gathers the value; Leaf does not run a provider or fetch a package URL. Set a
complete snapshot using the page's source id:

```bash
printf '%s' '{"main":"passing"}' | leaf data set PAGE release-ci
leaf data set PAGE release-ci --file build-state.json
leaf data set PAGE release-ci --file signed-build-state.json --capture-label "release candidate"
leaf data capture PAGE release-notes --file CHANGELOG.md --lines 20:44
leaf data capture PAGE review-patch --file change.patch --format unified-diff \
  --label "PR at 8f61c2a"
leaf data clear PAGE release-ci
```

`data set` validates before replacing the source atomically. Add `--capture-label` when
that structured value should also be retained as an immutable snapshot; `data capture`
reads a UTF-8 file into the same lifecycle. A rejected value leaves the
prior revision untouched. Source revisions and event sequences are independent:
an old poll may contain new data, and a new event response may contain old data, so
neither orders the other.

`data capture` reads a UTF-8 file without making the author copy it into markup.
The default `text` format can select an inclusive `START:END` line range. The
`unified-diff` format validates a Git patch and builds the file-fragmented manifest the
diff widget consumes; binary, mode-only, empty added or deleted, copy, and malformed
hunk entries are rejected rather than silently omitted. Both formats may attach a
display label. A capture
both replaces the source's current value and retains that value under the reported data
revision. A widget without its snapshot attribute follows the current value; a widget with
`snapshot="REVISION"` keeps reading that immutable capture. The captured source path is
never stored or sent to readers.

A source id keeps one contract for the lifetime of the page. Documents without a
snapshot selection share the page's current value; stamped versions and widgets
frozen into threads may instead select a retained capture. `data clear` removes the
current value and unreferenced captures, but keeps captures selected by those durable
documents and a contract-only tombstone that never releases the source id for a new
meaning. Use a new source id for a new contract. Re-vendoring preserves this mapping and
each standing widget selection while validating current values and captures against the
incoming schemas.
`leaf page state PAGE` exposes the complete `data_bindings` inventory so a producer can
discover the ids, contracts, widgets, and documents it needs without parsing markup.
Every source value goes to every reader of the page, including fields a module does not
paint. Do not put credentials or private host state in it.

A contract whose values contain large independently useful payloads may declare a
`fragments` coordinate: the top-level array field, each item's unique key field, and the
payload field. `data.json` still keeps and validates the complete value. `/api/state`
sends the array as a lightweight manifest with that payload field omitted; a widget uses
`loadDataFragment(element, input, key)` to fetch one payload from the exact data revision
and optional snapshot it already accepted. A stale revision is refused instead of
combining a new payload with an old manifest. This is how a collapsed `lf-diff` can show
thousands of files without transferring or rendering every patch first.

```json
{
  "fragments": { "items": "files", "key": "key", "value": "patch" },
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

A module subscribes through its own input declaration:

```js
this.stopWatching = watchData(this, "builds", (snapshot) => {
  render(snapshot?.value ?? {});
});
```

The callback receives `null` before the host has supplied a current value, otherwise a
clone of `{contract, revision, updated, value}`. `revision` is the data revision that
wrote that source value, so a renderer can distinguish two writes even when their wall
clock timestamps coincide. A selected capture additionally carries
`snapshot`, `label`, and optional `lines`; a captured current value may carry its label
and line range. It runs immediately and again when Leaf asks subscribers to restate its
view. Return the cleanup function from the element's disconnect path. The callback must
state the whole rendering and remain idempotent.

Render the value with `projectData(root, records, keyOf, render)`. The root is an
id-bearing authored seat and owns the projection's children. `keyOf` returns a stable
non-empty string for the logical datum; `render` receives
`(record, priorNode, index)` and returns its element, reusing `priorNode` where that
preserves a focused control or selection. Leaf marks those words as readable data
rather than authored prose, reconciles their order, and keeps comments attached by the
projection/key pair even when a refresh replaces the text nodes. Export keeps the last
rendering as a labelled snapshot and drops the code that could refresh it. A renderer
that owns a nested layout passes `{nested: true}` and returns its existing descendants;
Leaf labels those nodes without moving them. Add `labelOf(record, index)` when a thread
should name a projected datum with a human coordinate; the stable key remains opaque to
the runtime. If a `watchData` callback renders asynchronously, return that promise so
Leaf does not publish the source revision as ready before the projection settles. A
rejection is reported as that subscriber's page error; it does not make later state
reads repeat the same page-wide failure. A rejection from the callback's first run is
stronger: Leaf drops that subscription, so the callback is not asked to restate again
until the element is reconnected.

`navigateToDatum(widget, attribute, key, messages)` follows an `x-refers` attribute to
another projection and travels to its opaque datum key. Leaf resolves declared shadow
trees, asks the target to hydrate lazy data, opens its containing disclosure, focuses
that disclosure, updates the fragment, and announces the supplied `success` or `missing`
message. A lazy target may implement `lfRevealDatum(key)` to return its hydration promise
and `lfDataDatum(key)` to map a semantic key to the rendered projected element.

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
`lf-banner`, `lf-threads-toggle` (the panel), `lf-leaves` (the leaves panel), `lf-versions`,
`lf-composer`, `lf-comment-button` (the margin's Comment Button), `lf-keyline`, `lf-help` — and
`part` names the control the click landed on, where it landed on one (`Accept`,
`Threads (2)`).

```json
{"kind": "comment", "about": "layer", "version": 3, "anchor": {"section": "feeder-board"}, "text": "cards are cramped — give the column a floor"}
```

Answer it with the layer: change it where the table above says, `page init` the page,
stamp the version, and reply in-thread saying where the fix landed. The new version is
the answer, on the element the comment was made on. A comment naming leaf itself is the
hand-off above.
