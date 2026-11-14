# Package state and data

Read with [packages.md](packages.md), which holds the package contract and a widget's declaration. This file covers how widgets work together, the user state a widget records, references between widgets, work roles, and external or derived data sources.

## Widgets working together

A widget shares what it has the way its element would in plain HTML, so two widgets
whose authors never met work together on a Leaf page and on a page without Leaf. One
names the other by id in an attribute it declares under `x-refers`, `for` by
convention ("References between widgets"), and then:

| To                                                      | Use                                                                                                                                            | `page check` holds                                           |
| ------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| read what the other holds, such as a film's step        | its output, a property its element holds and says `change` for, which an `x-data` input binds by contract ("Widget outputs")                    | that the named widget declares one output of that contract   |
| ask it to act, such as "hold this step"                 | an HTML invoker command, `commandfor` with `command="--name"` ("Asking another widget to act")                                                 | that an authored button names an element                     |
| take the user to a part of it                           | `navigateToDatum` with the part's key, or a link to `#id:key` ([module-reading.md, "Following a reference"](module-reading.md#following-a-reference)) | that the id names an element                                 |

A recorded answer stays its owner's, and only the owner's module records it
("User state"). Another widget shows that answer by reading an output the owner holds,
and changes it by asking the owner with a command the owner turns into its own verb. The
log then holds one answer whichever widget the user changed it in, Undo takes back
that one action, and the same two modules work off Leaf, where the owner keeps the
answer itself. A view whose own place on the page is that answer, as a board card
stands in the column of a pick, declares `x-shows` instead ("Views of an answer"),
since the server has to place it.

Packages declare no dependency on each other, so two that share a contract each
declare it in their own `$data.contracts`, word for word; a page composing both keeps
one copy, and `page check --render` holds what the producer holds to it. What a
provider of the contract must take as commands goes in the contract's `instructions`.

### Asking another widget to act

A request from one element to another, such as a step list asking its film to hold a
step, is an HTML invoker command: a button names its target and a custom command, and
the target hears a `command` event.

```html
<button commandfor="merge-film" command="--seek" value="squash">Squash</button>
```

```js
this.addEventListener("command", (event) => {
  if (event.command === "--seek") this.hold(event.source.value);
});
```

A custom command's name starts with `--`; HTML's own, such as `show-modal` and
`toggle-popover`, act on dialogs and popovers. An argument rides on the button's
`value`. The target's `description` says which commands it takes and what each
value means, since nothing else tells a page's author. `page check` refuses an
authored button whose `commandfor` names no element, or whose `command` is neither
kind; a custom command the target doesn't handle does nothing, with no error.

A module that draws the button writes the same attributes, taking the id from its own
reference attribute, as in `commandfor=${this.getAttribute("for")}`. Inside a shadow
tree the attribute can't name a page element, so set the element instead
(`button.commandForElement = this.getRootNode().getElementById(id)`); the target then
sees the button's host as `event.source`, so the host holds the argument as its
`value`.

The browser makes the press, so the button needs no click listener and no `lfCommands`
row, a key and a finger press it as a pointer does, and it works the same on a page
without Leaf. A press does nothing until the target's module has loaded, as with any
control a module wires. The target decides whether to act, as it does for its own
controls.

## User state

A widget records each change the user makes as an `action` event in the page's log;
the package writes no storage or server code. It declares each kind of change as a verb
under the element's `x-state`. Leaf validates each event, works out the current state,
hands it to the module, and shows it to the agent under `state` in `leaf page state`.

A verb declaring `decides: true` selects which of its widget's members retire. It
folds by widget and requires a string-enum `outcome` field. `x-retired-when` and
`x-withdrawn-as` refer to those outcomes. An `outcome` field on any other verb is
ordinary domain data; whether an action answers an obligation is separately
declared by `x-awaits`.

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
`browser/registry.json` define each key exactly.

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
`detail` JSON Schema, with `unit` either `"widget"` or a required string detail field
naming what the verb's state is about, by element id or by data key, as a playground's
submitted settings do.

For an optional command the agent should act on, such as Archive, declare
`attention: true` on its user verb (`$state.attention` in the registry). Changes to
that verb's state reach the agent without putting a question on the user's On Me list.
Use `x-awaits` below when the widget instead asks the user for an answer. A verb that
records what the user is working on before they send it, as a playground's `tune` keeps
its settings, declares `unsent: true`: it reaches every tab and the agent's page
state but asks the agent for nothing, and a message the user writes about the widget
reaches the agent with it.

Only one widget records each attribute. A member's `value` record can't use the same
attribute as an `attribute` record on a widget around it; `page check` refuses that in
the markup, and Leaf refuses a move that would put the member under such a widget.

A verb that lets the user add a child element declares `creates`, as `lf-options`' `add`
does with `{"child": "lf-option", "words": "text"}`. Its `unit` names the detail field
holding the new child's id, which must be one no page or Thread markup holds, created
members included, and `words` the field holding its text; its detail schema has just
those two fields. Each added child is its own key, so undoing the add removes it. The
child's tag lists the widget in `x-owners`, requires only an `id`, and has
`x-content: markup`.

The added child belongs to its parent. Its entry may have a module and a shadow root for
presentation, but `package check` refuses one that declares state, obligations, work, history,
data, visual parts, or a thread seat or surface of its own; the parent's controller
records and presents
it. Removing the child doesn't withdraw the parent's actions, so a parent selection
still in force selects the same id if it returns. A widget that needs its own actions
or services belongs in authored markup.

A verb the agent writes, such as the task `status` on the Atlas example page, declares
`"writer": "agent"`, `unit: "widget"`, and an `attribute` or `value` record. A worker sets
it with `leaf page report`; the page shows it at once, and it stays until a new version
answers it. `text: true` requires each report to carry short news for a person in
`detail.text`. Each verb has one writer, so no key holds both a user's action and an
agent's report. A widget with such a verb also declares a boolean `overruled` attribute,
which a version sets to keep its authored state over the report.

`x-awaits` puts a widget's obligations on the user's list, On Me. Its
`value` names the verb whose
state is the answer: the recorded value, or a recordless verb's latest `detail`. A
playground's unrecorded `choose` gives its submitted settings. `x-awaits.answered` separately says when the obligation
is complete: `{}` once the verb has a state, `when` for instances with matching
attributes, and `empty` while the named container has no members. A page-owned queue can
declare:

```json
{
  "value": "move",
  "answered": {
    "move": { "empty": { "within": "lf-queue-column", "when": { "queued": [true] } } }
  }
}
```

The obligation is answered once the marked column is empty, and returning a card reopens it. If
the widget's `when` stops holding, a complete obligation stays answered and an incomplete one is withdrawn.

A widget whose bound data contains independently answered records declares
`records: {"input": "run", "label": "title"}` in `x-awaits`. The input binds to a stored
source, which the server can read; widget outputs remain browser-local. The input's contract
supplies `records.items` and `records.key`; each record's key identifies its obligation
and its answering action's unit. The named label field supplies the prompt. For example,
`value: "review"` with `answered: {"review": {"detail": {"approved": true}}}` completes
each record's obligation while that unit's latest review approves it. Clearing or undoing
approval reopens it. Source reordering preserves these identities; removing a record
removes its obligation. The widget marks those same keys as its drawn data
([module-state.md, "Marking drawn data"](module-state.md#marking-drawn-data)) so Leaf's
On Me navigation can reveal each record.

`x-awaits.retired` names the attribute an author sets to close an obligation but keep its
widget on the page, such as a decided question collapsed with its options; `when` must
require it to be absent. `x-encloses`, which `lf-ask` declares, makes a wrapper give
the obligations inside it its heading and where the user lands; it asks nothing itself.

The module reads and records this state through `widgetController(owner)`
([module-state.md, "The widget controller"](module-state.md#the-widget-controller)),
words answers with `static answerWords` ([module-state.md, "Declared widget
state"](module-state.md#declared-widget-state)), and reads obligations with `readObligations()`
([module-reading.md, "Reading obligations and the
On lists"](module-reading.md#reading-obligations-and-the-on-lists)).

### Views of an answer

An answer has one owner, the widget whose `x-awaits.value` verb records it, but the
user may want to see and change it from another view, as a board gathers the picks of
proposals answered in their own sections. The view's element declares `x-shows`, as
`lf-card` does:

```json
{
  "x-refers": { "shows": {} },
  "x-shows": { "attr": "shows", "value": "value" }
}
```

`attr` names the attribute holding the widget's id, which must be in the view's own
page or message, and `value` the attribute on the view's compound owner (its
`x-owners` tag, here `lf-column`) naming the answer that owner holds. The view stands
in the owner holding the value the answer names, or in one without `value` while the
answer names none, or one no owner holds. A `value` record's answer names its attribute's value. An
`attribute` record's answer names a value when every member it picks carries the same
value in the attribute `x-awaits.key` names, as `lf-options` declares `"key":
"value"` and each `lf-option` a `value` unique within its group (`x-unique`); an empty
pick, an option the user added, or picks of different values name none.

The view keeps no state of its own about the answer. It reads and changes the answer
through `shownAnswer` ([module-reading.md, "Reading obligations and the On
lists"](module-reading.md#reading-obligations-and-the-on-lists)), which sends the
widget's own command, so the log holds one answer whichever view the user changed it
in. The append door refuses a position move of a view, and `page check` refuses
markup that puts a view apart from its widget's authored answer, owners that all
hold a value, leaving nowhere for an answer that names none, or an owner value the
widget can't answer.

## Instance input contracts

A custom-detail verb can declare `contract: {"field": "values", "attribute": "contract"}`.
The widget declares its `contract` attribute a string, and Leaf gives it the data
contract name grammar ([packages.md, "A widget"](packages.md#a-widget)). Its authored
value selects a `$data.contracts` entry whose `schema` validates the complete
`detail.values`, alongside the package's base schema. The field and attribute names
belong to the package; core reads the declaration.

For example, two Playgrounds can use `contract="release-query"` and
`contract="notification"`. Their page declares those contracts in
`page/registry.json`, with each complete values schema covering scalar controls,
structured editor values, required names and bounds. The widget declaration stays
with its package. Without the attribute, the base payload schema applies.

Page checks refuse unknown contract names. Admission reads the attribute from the
authored revision, or from the frozen message holding a thread widget, and resolves
it using the command’s revision registry. Changing only the selected contract keeps
any earlier action whose value fits the new schema. The log keeps the original action
and its schema.

## References between widgets

When an attribute names another element, declare it in `x-refers`, mapping the
attribute to `{}`, which accepts any element id. `page check` refuses an id that names
no element.

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

`x-unique` makes `name` unique within each `lf-playground`, and the keyed reference
`{tag, key}` looks `for` up only inside the setting's own playground. Rules about content, such as
a value within its range, belong to the widget and `page check --render`.

## Work roles

Leaf owns four work roles and reads a hierarchy of work from them
([module-reading.md, "Work hierarchies"](module-reading.md#work-hierarchies)). A
package maps its tags onto them in `$work.widgets`:

- `scope` bounds a hierarchy; a reading stops at a nested scope.
- `goal` is a piece of work. `state` names the attribute holding its state, which
  exactly one `unit: "widget"` value verb records, and `done` and `stopped` list the
  values that mean finished and stopped. `stoppedAt` may name an attribute saying
  when it stopped.
- `worker` is an agent doing the work, with `state`, the values that mean `running`
  and `retired`, and optionally `on`, an `x-refers` attribute naming the goal it works
  on.
- `evidence` marks an element that shows observed data.

```json
{
  "$work": {
    "widgets": {
      "lf-atlas-task": {
        "role": "goal",
        "state": "status",
        "done": ["done"],
        "stopped": ["blocked"]
      },
      "lf-atlas-worker": {
        "role": "worker",
        "state": "state",
        "running": ["working"],
        "retired": ["done"],
        "on": "on"
      }
    }
  }
}
```

`page init`, `page check` and `package check` hold each entry to its tag's
declaration, refusing a mistake with a finding that names the tag and key, and `page
check` refuses a worker whose `on` names anything but a goal. Atlas in
`examples/command-hub.page/` is the worked example.

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

A widget declares the inputs it can show under `x-data`, each naming its contract, the
attribute that carries the page's source id, and the element `property` Leaf sets to the
value. Make that attribute required when the widget can't work without the input. A
widget with `x-content: data` declares at most one input and can take its text from
its `<pre>` instead: where the markup binds the input to nothing, Leaf sets its
property to the `<pre>`'s text, a string, so the widget reads one property either way,
as `lf-text-document` and `lf-diff` do. Give such an input a contract that admits a
string; `page check` refuses a `<pre>` on a bound one. Leaf leaves the property of any
other unbound input to the widget. Tell page authors how to bind it in
`x-instructions`, and whoever produces the data in the contract's `instructions`
(`packages.md`, "Package contract").

```json
{
  "lf-builds": {
    "type": "object",
    "properties": {
      "id": { "type": "string" },
      "source": { "type": "string" }
    },
    "required": ["id", "source"],
    "additionalProperties": false,
    "x-content": "empty",
    "x-data": {
      "builds": {
        "contract": "build-status",
        "source": "source",
        "property": "value"
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

### Widget outputs

A widget may also hold a typed value for other widgets to read, such as the files a
diff lists or the step a film shows. Its registry entry declares
`"x-output": {"files": {"contract": "file-list"}}`; the contract is an ordinary
`$data.contracts` entry, and the output's name is the element property that holds it.
The module sets that property to the complete value, or `null` while it has none, and
then dispatches `change` on the element, as a form control does for `value`:

```js
this.files = { files: entries };
this.dispatchEvent(new Event("change"));
```

A consumer uses the same `x-data` input for an external source or another widget's
output, declaring `source`, `reference` or both:

```json
"x-data": {
  "files": {
    "contract": "file-list",
    "source": "source",
    "reference": "for",
    "property": "value"
  }
},
"x-refers": {"for": {}}
```

The input's `reference` names its ordinary element relation, and the consumer
declares both attributes in `properties`. A page binds either
`source="project-files"` or `for="review"`, where `review` is a widget holding a
`file-list`. The input binds by contract: it reads the one output of its contract the
named widget declares, whatever that widget calls it, so a consumer never names a
producer's tag or its output and works beside any producer of the contract. `page
check` refuses a `for` naming a widget with no output of the contract, or with more
than one.

Leaf reads the property when the consumer first draws, again each time the producer
says `change`, and from the new element when a revision replaces the producer, so a
consumer draws the current value whichever module loaded first. The consumer gets its
own copy and redraws only when the value differs. Assign a new value rather than
editing the held one, and say `change` after each assignment. Dispatch it on the
element itself: a control inside the element says a bubbling `change` of its own,
which Leaf doesn't count, and which a module listening on its own element tells apart
by `event.target`.

A consumer draws after the producer's `change`, in the same frame, not inside it. A
producer that goes on to act on the page as its consumers leave it, such as scrolling
to a place, does that in the next frame (`frameFor`).

On a page without Leaf the same module needs no import for this, and the host does
the binding itself: `review.addEventListener("change", () => (tree.value = review.files))`.

`page check --render` and `package check --render` validate every value an output
holds as it says `change` during their render, including values later withdrawn or
replaced and values from contained samples whose frames are later disposed. A
mismatch is an error naming the producer, output, contract and value path. Captured
provenance names the implementation owner and, when different, the output declaration
and data contract owners: a page can change each independently. These checks cover
the paths the examples exercise, not every possible later value. The running browser
does not load a schema validator.

An output belongs to its element and lives only in the browser: it reaches neither
the server nor the agent, and has no source revision or run receipt. Record what the
agent or another device should see ("User state"). Data reading, projection, and
presentation follow [module-state.md, "Bound data and
projections"](module-state.md#bound-data-and-projections).

The agent gathers the value and sets it whole; Leaf fetches nothing:

```bash
leaf data set PAGE release-ci --text '{"main":"passing"}'
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
a source error. `leaf page state PAGE` lists every binding under `data_bindings`, so a
producer needn't parse markup. Every value goes to every user of the page, so never put
credentials or private host state in one.

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

A contract whose value holds keyed rows declares `records`, naming the array and each
row's key. `data set` refuses a value in which two rows share a key, or a row's key is
missing, empty or not a string, and an `x-awaits.records` input
([User state](#user-state)) keys each row's obligation by it. `lf-diff`'s contract, whose value has a `files` array of
`{path, patch}` objects, declares `{ "records": { "items": "files", "key": "path" } }`.
