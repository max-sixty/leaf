# Package state and data

Read with [packages.md](packages.md), which holds the package contract and a widget's declaration. This file covers the user state a widget records, references between widgets, and external or derived data sources.

## User state

A widget whose user changes something records each change as an `action` event in the
page's append-only log. The package writes no storage or server code. It declares verbs
under the element's `x-state`, and Leaf validates each event at the log's one append
door, folds the log into current state, gives that state to the module, and lists it
for the agent under `state` in `leaf page state`.

The default board declares `move` as a position record in
`packages/default/registry.json`; its module subscribes to and dispatches that state:

```json
{
  "x-state": {
    "move": {
      "unit": "unit",
      "record": { "kind": "position", "within": "lf-column" }
    }
  }
}
```

The record determines the event's payload schema. A move sends
`detail: {unit: cardId, value: columnId, rank}`: the moved card, its destination column,
and its rank key. Leaf checks their types and ownership at admission. The package
declares no separate `detail` schema or input-field mapping for a recorded verb.

Each verb is its own piece of state: the owning element, the `unit`, and the verb together form the fold
coordinate. At each coordinate the latest surviving action stands, and different
coordinates stand side by side. Moving a card again therefore replaces that card's
earlier position, while positions of different cards coexist. Recorded body, attribute,
and value verbs use `unit: "widget"`; position verbs use `unit: "unit"`, naming the
canonical detail field for the moved element. `record` says how the current state reads in markup: here, the
card's position inside a column. Decisions in force supply the current state;
`restated` explicitly retracts a decision, and revisions may change their authored
baseline without a historical-state veto. The `$keys`
entries in `assets/registry.json` define each key exactly.

Recorded payloads are closed objects: all listed fields are required and extra fields
are refused. Their fields come from the effect:

| Record kind | Detail fields | Value validation |
| --- | --- | --- |
| `body` | `{value}` | String replacing the widget's body. |
| `attribute` | `{value}` | Array of distinct owned member ids; `record.attr` names the boolean attribute marking them. |
| `value` | `{value}` | The schema of the destination in the widget's `properties`; `record.attr` names that attribute. |
| `position` | `{unit, value, rank}` | Strings naming the owned element, valid destination container, and rank key; `record.within` names the container tag. |

`text: true` on an agent-written verb requires each report to carry non-empty
`detail.text`, the report's news. Omit `text` when the verb has no news. The effect
determines the complete payload; a recorded verb cannot add contextual fields or
independent schema refinements.

A verb with no record declares its own closed `detail` JSON Schema. Its `unit` is
`"widget"` or a required detail field naming the element it changes. This supports
custom actions, such as a playground's submitted settings, and generated children.

`x-awaits` registers an ask automatically for each matching widget. Its
required `value` names one `x-state` verb: recorded state supplies that verb's
typed value, and a verb without a record supplies its admitted action detail.
For example, `"value": "choose"` exposes selected option ids; a playground's
recordless `choose` exposes its submitted configuration. The source widget
continues to own that state and admit its commands.

`x-awaits.retired` names the flag an author sets to end an ask already
posed, such as a decision kept collapsed with its options; `when` must require
that flag absent. An ask context, such as `lf-ask`, must frame at least one
source that asks or was retired, and `page check` refuses one that frames none.

`x-awaits.answered` separately says when the ask is complete. `{}` holds
while the verb's state stands, `when` narrows a verb to instances with matching
attributes, and `empty` holds while the named container has no members. A
page-owned queue can declare:

```json
{
  "value": "move",
  "answered": {
    "move": {"empty": {"within": "lf-queue-column", "when": {"queued": [true]}}}
  }
}
```

The ask is answered when the marked column is empty; returning a card
reopens it. The package declares its own columns and cards, whose `x-owners`
name their containers. The default board's `lf-column` belongs only to
`lf-board`; ordinary boards pose no ask unless they declare one.

A draft declares `"value": "edit", "answered": {"edit": {}}`. An options group
keeps `"value": "choose"` for both forms, while `answered` selects `choose` for
single choice and `answer` for multiple choice's Done. Completion never depends
on the answer's truthiness: partial choices can be open, and an empty selected
set can be complete. If the ask's `when` stops holding, a complete source
remains answered and an incomplete one becomes withdrawn.

`x-ask-context` contributes the leading heading and arrival target to a
nested ask. It does not replace its source identity or own the answer.
`lf-ask` is the default context adapter. The module's `static answerWords(value,
element)` formats values for presentation ([module-state.md, "Declared widget
state"](module-state.md#declared-widget-state)); `readAsks()` exposes
typed values directly ([module-reading.md, "Reading asks and obligation
queues"](module-reading.md#reading-asks-and-obligation-queues)).

The module reads and writes through `widgetController(owner)`, described in
[module-state.md, "The widget controller"](module-state.md#the-widget-controller): `subscribe` delivers the authored baseline with the fold applied, and
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
beside its `unit` and `record`. A worker posts it with
`leaf page report`, the page paints it live, and it stands until a version
answers it; the user has no control for it. It uses `unit: "widget"` and a required
`attribute` or `value` record. It declares `text: true` when each report must also
carry short human-readable news in `detail.text`. Every verb has exactly one
writer, so a coordinate never holds a user's action and an agent's report at once.
The Atlas example's page-owned task `status` is one example. A widget declaring
such a verb also declares the boolean `overruled` attribute a version keeps its own
state with. A worker that reacts to the user's actions follows them as they land with
`leaf page events PAGE --follow`.

## References between widgets

Use `x-refers` when authored attributes point at other page objects. Its value is
a map from attribute names to target contracts. `{}` accepts any existing element id.
A typed contract uses `via` to name a package-owned shared registry map and `where` to
match a declaration there:

```json
{
  "x-refers": {
    "target": { "via": "$work.widgets", "where": { "role": "goal" } },
    "worker": { "via": "$work.widgets", "where": { "role": "worker" } }
  }
}
```

Add `"owns": true` to a typed contract whose referrer fills its target, as a command
fills the readings seat it names. `page check` then requires the target in the
referrer's own document, and every element there that the predicate selects named by
exactly one referrer, so no seat stands empty or holds two commands' readings.

Where members of one owner name each other by a word rather than an id, declare the
word unique within the owner with `x-unique`, a map from the member's attribute to the
owner's tag, and refer to it with a keyed contract, `{tag, key}`:

```json
{
  "lf-playground-control": { "x-unique": { "name": "lf-playground" } },
  "lf-playground-setting": {
    "x-refers": { "for": { "tag": "lf-playground-control", "key": "name" } }
  }
}
```

`page check` and message markup validation then refuse two controls of one playground
sharing a `name`, and a setting whose `for` names no control of its own playground. A
keyed contract resolves inside the referrer's nearest enclosing owner of the tag its
target's `x-unique` names for `key`, so the same name in another playground never
answers it. Rules that need the content itself, such as a range value within its
bounds, stay with the widget and `page check --render`.

Leaf validates the generic relation; the package owns the map, roles, and participating
widget tags. A later package can therefore add another goal or worker widget by merging
its entry into `$work.widgets`, without changing core.

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

State in the contract every rule the widget relies on, such as `records` for unique
keys or `if`/`then` for a field one kind of record requires, so `data set` refuses a
value the widget could not present instead of storing it for the page to fail on. A
widget then reads its value without checking it again. A schema may name a `format`
only where Leaf checks one: `date-time` is an absolute, timezone-aware instant, `uri`
is an absolute URL the browser's URL parser accepts, and `package check` lists the
others and refuses any it does not check.

A widget declares the inputs it knows how to present. Each input names its contract and
the attribute that will carry the page's source id. Make that attribute required when
the widget cannot work without the input; an optional unbound input delivers `null`.
Widget-specific authoring instructions travel in `x-instructions`;
contract-specific producer instructions travel beside the contract in the
`instructions` audience map. Shared package instructions apply to the package as
a whole. `packages.md`, "Package contract", defines how a reader selects them.

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

Each source is one JSON publication at `data/<source>.json`, holding its opaque
`run` receipt, `updated` instant, and complete `value`; `data.json` records its
contract. Write a value through `leaf data set`, which checks the binding, validates
the value and replaces the publication atomically. A rejected value leaves it
untouched. Every reading validates the value against the contract the source is
bound to now, so a value that no longer fits it reaches users as that source's error,
and `page check` and `page state` report it. Tabs hear a new publication as they hear any page change.

A contract that carries media URLs declares `resources`, a list of
[JMESPath expressions](https://jmespath.org/tutorial.html) selecting each URL string
or array of URL strings. For example, `"resources": ["images[].url"]` names the
`url` fields of an `images` array. An absent optional field may select null.
Selected URLs must be canonical `/media/` URLs returned by `page media`, or
HTTP(S) URLs. Leaf does not interpret ordinary strings elsewhere as references.
Snapshots capture the selected local media with the current data value; offline
exports embed those bytes. Remote media stays remote. These resources belong to
the data reading, so capturing them does not change a stored authored revision.

A source's revision identifies its encoded value, its `run` receipt identifies the
write, and `updated` records when it was written. A rerun with the same value keeps
its revision and produces a new run. Copying a page preserves those identities.
Nothing keeps a replaced value: every document that binds a
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
(PEP 723). `leaf package run NAME SCRIPT [ARGS]...` finds the
package by the name `--package` selects it by, bundled or installed, and runs the
script with `uv run --script` in the environment its header declares, apart from
Leaf's own. The script owns stdin, stdout, and the exit status, so the instructions state the
pipeline with no path in it:

```bash
git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE review-patch
```

`package check` and `package install` refuse a `scripts/*.py` without that header,
since uv would run it in whatever project the caller's directory reaches. A
subdirectory of `scripts/` holds helpers and is not checked or run. A page never
vendors `scripts/`. When a producer upstream of `data set` fails and writes nothing,
`data set` refuses the empty input and points back at that producer's own error.

A revision may replace a source's contract, including its schema, record declaration,
and resource selectors. `data set` validates against the current binding and replaces
its stored contract and value together. `data clear` removes the value; retaining
its last stored contract does not reserve the source id. Archived documents retain
their captured vocabulary and validate incoming values against that contract; an
incompatible value is shown as a source error rather than passed to its renderer.
`leaf page state PAGE` exposes the complete `data_bindings` inventory so a producer can
discover the ids, contracts, widgets, and documents it needs without parsing markup.
Every source value goes to every user of the page, including fields a module does not
paint. Do not put credentials or private host state in it.

A contract whose value holds keyed rows declares `records`: the top-level array field
and each row's key field. A source replacement is accepted only when every row has a
non-empty, unique string key. Rows that each carry a large, independently useful
payload may name that field `deferred`; the item schema decides which rows carry it.
The source file still holds the complete value, and readings validate all of it,
but `/api/state` sends each row with that field
omitted; a widget uses `loadDeferred(snapshot, key)` to fetch one row's payload
using the delivery `watchData` handed it. A request naming a source revision the file
no longer holds is refused instead of combining a new payload with an old manifest.
This is how a collapsed `lf-diff` can show thousands of files without transferring or
rendering every patch first.

```json
{
  "records": { "items": "files", "key": "path", "deferred": "patch" },
  "schema": {
    "type": "object",
    "properties": {
      "files": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "path": { "type": "string" },
            "patch": { "type": "string" }
          },
          "required": ["path", "patch"]
        }
      }
    },
    "required": ["files"]
  }
}
```

Browser subscriptions and rendering follow [module-state.md, "Data subscriptions and
projections"](module-state.md#data-subscriptions-and-projections).
