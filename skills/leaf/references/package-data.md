# Package state and data

Read with [packages.md](packages.md), which holds the package contract and a widget's declaration. This file covers the user state a widget records, references between widgets, and external or derived data sources.

## User state

A widget records each change the user makes as an `action` event in the page's log;
the package writes no storage or server code. It declares each kind of change as a verb
under the element's `x-state`. Leaf validates each event, works out the current state,
hands it to the module, and shows it to the agent under `state` in `leaf page state`.

The default board declares `move` as a position record in
`packages/default/registry.json`:

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

Leaf keys each action by `[widget, unit, verb]`: the element, the part of it the action
changes, and the verb. For each key the latest action not taken back sets the state, so
moving a card again replaces that card's position while other cards keep theirs.
`record` says how the state shows in markup, here as the card's place in a column. A
new version may change the authored markup freely; the user's decisions still apply
over it until a `restated` event takes one back. The `$keys` entries in
`assets/registry.json` define each key exactly.

The record kind fixes the event's payload, a closed object with every field required:

- `body` sends `{value}`, a string that replaces the widget's body.
- `attribute` sends `{value}`, an array of distinct member ids, marked by the boolean
  attribute `record.attr` names.
- `value` sends `{value}`, matching the schema of the attribute `record.attr` names in
  the widget's `properties`.
- `position` sends `{unit, value, rank}`: the moved element, the destination container
  (of the tag `record.within` names), and its rank.

These verbs use `unit: "widget"`, except position verbs, whose `unit: "unit"` names the
detail field holding the moved element. A verb with no record declares its own closed
`detail` JSON Schema, with `unit` either `"widget"` or a required detail field naming
the element it changes, as a playground's submitted settings do.

A verb that lets the user add a child element declares `creates`, as `lf-options`' `add`
does with `{"child": "lf-option", "words": "text"}`. Its `unit` names the detail field
holding the new child's id, which must be one the document doesn't hold, and `words`
the field holding its text; its detail schema has just those two fields. Each added
child is its own key, so undoing the add removes it. The child's tag lists the widget in
`x-owners`, requires only an `id`, and has `x-content: markup`.

A verb the agent writes, such as the task `status` on the Atlas example page, declares
`"writer": "agent"`, `unit: "widget"`, and an `attribute` or `value` record. A worker sets
it with `leaf page report`; the page shows it at once, and it stays until a new version
answers it. `text: true` requires each report to carry short news for a person in
`detail.text`. Each verb has one writer, so no key holds both a user's action and an
agent's report. A widget with such a verb also declares a boolean `overruled` attribute,
which a version sets to keep its authored state over the report. A worker that reacts to
the user follows their actions with `leaf page events PAGE --follow`.

`x-awaits` makes each matching widget pose an ask. Its `value` names the verb whose
state is the answer: the recorded value, or a recordless verb's latest `detail`. An
options group uses `"value": "choose"` for the selected ids; a playground's unrecorded
`choose` gives its submitted settings. `x-awaits.answered` separately says when the ask
is complete: `{}` once the verb has a state, `when` for instances with matching
attributes, and `empty` while the named container has no members. A page-owned queue can
declare:

```json
{
  "value": "move",
  "answered": {
    "move": {"empty": {"within": "lf-queue-column", "when": {"queued": [true]}}}
  }
}
```

The ask is answered once the marked column is empty, and returning a card reopens it. A
draft declares `"value": "edit", "answered": {"edit": {}}`, and an options group answers
on `choose` for single choice and on Done's `answer` for multiple choice. A partial
choice can be open and an empty selection complete. If the ask's `when` stops holding,
a complete ask stays answered and an incomplete one is withdrawn.

`x-awaits.retired` names the attribute an author sets to close an ask but keep it on the
page, such as a decided question collapsed with its options; the ask's `when` must
require it to be absent. A wrapper like `lf-ask`, declared with `x-ask-context`, gives
a nested ask its heading and where the user lands, and must hold at least one widget
that asks or was retired.

The module reads and records this state through `widgetController(owner)`
([module-state.md, "The widget controller"](module-state.md#the-widget-controller)),
words answers with `static answerWords` ([module-state.md, "Declared widget
state"](module-state.md#declared-widget-state)), and reads asks with `readAsks()`
([module-reading.md, "Reading asks and obligation
queues"](module-reading.md#reading-asks-and-obligation-queues)).

## References between widgets

When an attribute names another element, declare it in `x-refers`, mapping the
attribute to a target contract. `{}` accepts any element id. A typed contract names a
package's shared registry map with `via` and the entries it accepts with `where`:

```json
{
  "x-refers": {
    "target": { "via": "$work.widgets", "where": { "role": "goal" } },
    "worker": { "via": "$work.widgets", "where": { "role": "worker" } }
  }
}
```

Leaf checks only the relation; the package owns the map and its roles, so a later
package adds a goal or worker widget by adding its entry to `$work.widgets`.

Add `"owns": true` when the referring widget draws into its target, as a command widget
draws its readings into the element its `readings` attribute names. `page check` then
requires the target in the referrer's own document, the page or the message holding it,
and every element there matching `where` to be named by exactly one referrer, so no
target is empty or filled twice.

Members of one owner can name each other by a word instead of an id. A playground's
setting names its control by `name`:

```json
{
  "lf-playground-control": { "x-unique": { "name": "lf-playground" } },
  "lf-playground-setting": {
    "x-refers": { "for": { "tag": "lf-playground-control", "key": "name" } }
  }
}
```

`x-unique` makes `name` unique within each `lf-playground`, and the keyed contract
`{tag, key}` looks `for` up only inside the setting's own playground. `page check`
refuses a repeated name, or a `for` naming no control there. Rules about content, such as
a value within its range, belong to the widget and `page check --render`.

## External or derived data

A current deployment, sensor reading, worktree or query result belongs neither in the
page's markup nor in its log. Leaf keeps each as a source: one replaceable JSON file.

A named contract under `$data.contracts`, which any package can declare and several
widgets share, says what a source's data means:

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

Put every rule the widget relies on into the schema, such as `if`/`then` for a field
one kind of record needs, so `data set` refuses a value the widget couldn't show and
the widget needn't check it again. A `format` must be one Leaf checks: `date-time` is a
timezone-aware instant, `uri` an absolute URL, and `package check` lists the rest.

A widget declares the inputs it can show under `x-data`, each naming its contract and
the attribute that carries the page's source id. Make that attribute required when the
widget can't work without the input; an unbound optional input delivers `null`. Tell
page authors how to bind it in `x-instructions`, and whoever produces the data in the
contract's `instructions` (`packages.md`, "Package contract").

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

The page binds a source by id in its markup, and widgets reading the same contract can
share one:

```html
<lf-builds id="release-builds" source="release-ci"></lf-builds>
```

The agent gathers the value and sets it whole; Leaf fetches nothing:

```bash
printf '%s' '{"main":"passing"}' | leaf data set PAGE release-ci
leaf data set PAGE release-ci --file build-state.json
sed -n '20,44p' CHANGELOG.md | jq -Rs . | leaf data set PAGE release-notes
leaf data clear PAGE release-ci
```

`leaf data set` validates the value against the source's contract and replaces
`data/<source>.json` in one step, or leaves it untouched. Open tabs pick up the new
value at once. `leaf data clear` removes the value, and each bound widget receives
`null`. A value that stops fitting a later contract shows users an error for that
source, and `page check` and `page state` report it. A stamped version keeps the
contract it was stamped with, so a value written for a changed contract shows there as
a source error. `leaf page state PAGE` lists
every binding under `data_bindings`, so a producer needn't parse markup. Every value
goes to every user of the page, so never put credentials or private host state in one.

Leaf keeps no old values: every document bound to a source, stamped versions and
widgets in Threads included, shows its current value. A document that must keep one
value binds a source id nothing rewrites. Each value has a `revision`, which identifies
the value, and a `run`, which identifies the write. They don't order against the page's
events: an old poll may hold new data.

A contract whose value has media URLs selects them in `resources`, a list of
[JMESPath expressions](https://jmespath.org/tutorial.html), such as `"images[].url"`.
Each must be a `/media/` URL from `page media`, or an HTTP(S) URL; snapshots and offline
exports carry the local ones.

Leaf derives nothing: `data set` stores the value it is given, and a producer builds
anything derived, such as a patch split into files. A package may ship that tool as a
Python file under `scripts/` with PEP 723 inline metadata naming its dependencies, which
`package check` requires. `leaf package run NAME SCRIPT` runs it with `uv run --script`,
so the contract's instructions give a pipeline with no paths:

```bash
git diff main... | leaf package run diff patch_manifest.py | leaf data set PAGE review-patch
```

If a producer fails and writes nothing, `data set` refuses the empty input and points
back at that producer's error.

A contract whose value holds keyed rows declares `records`, naming the array and each
row's key, which must be a unique non-empty string. A row's large payload can be
`deferred`: the file keeps it, but the page receives rows without it, and a widget
fetches one with `loadDeferred(snapshot, key)`. That is how a collapsed `lf-diff` lists
thousands of files without loading every patch:

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
