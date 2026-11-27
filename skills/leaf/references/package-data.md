# Package state and data

Read with [packages.md](packages.md), which holds the package contract and a widget's declaration. This file covers how widgets work together, the user state a widget records, references between widgets, work roles, and external or derived data sources.

## Widgets working together

A widget shares what it has the way its element would in plain HTML, so two widgets
whose authors never met work together on a Leaf page and on a page without Leaf. One
names the other by id in an attribute its declaration says names an element, `for` by
convention ("References between widgets"), and then:

| To                                               | Use                                                                                                                                                   | `page check` holds                                                |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| read what the other holds, such as a film's step | its output, a property its element holds and says `change` for, which an input (`inputs`) binds by contract ("Widget outputs")                        | that the named widget declares one output of that contract        |
| ask it to act, such as "hold this step"          | an HTML invoker command, `commandfor` with `command="--name"` ("Asking another widget to act")                                                        | that an authored button names an element                          |
| take the user to a part of it                    | `navigateToDatum` with the part's key, or a link to `#id:key` ([module-reading.md, "Following a reference"](module-reading.md#following-a-reference)) | that the `refers` attribute names an element; a link is unchecked |

Point when the result belongs in the address: the user goes to the part, Back returns,
and a reload or a copied link reaches it again. Ask when the user stays where they are
and the owner changes something it keeps: a recorded change Undo takes back, or a view
only this tab holds. Either way the shared contract's `producer` instructions say what
the target takes: the invoker commands it answers and the keys it reveals.

A recorded answer stays its owner's: only the owner's module records it ("User
state"), and no module records another widget's verb. Another widget shows that answer
by reading an output the owner holds, and changes it by asking the owner with an
invoker command the owner turns into its own verb. The log then holds one answer
whichever widget the user changed it in, and Undo takes back that one action. A board
card shows an `lf-options` pick this way: its `shows` binds the `choice` the
`lf-options` holds, and a drop asks the `lf-options` to `--choose` the column's value.
Two modules written this way also work on a page without Leaf, where the owner keeps
the answer itself and the host sets the reader's input ("Widget outputs").

Packages declare no dependency on each other. A widget that holds a value names a
contract that its own package or Leaf's `default` package declares in
`$data.contracts`. So does a widget whose input takes a `source`, since `leaf data
set` validates a source's value against the contract. A widget whose input binds only
by `reference` names the producer's contract, and its package doesn't declare it:
`page check` matches the input to the output by the contract's name, and `page check
--render` holds what the producer holds to the contract. Two packages that both
declare a contract declare it word for word, and a page composing both keeps one copy.
On a page that selects a package declaring the contract, `leaf page instructions --use`
returns its `producer` instructions for a widget on either side.

`package check` reads one package, so check a pair on a page. Start one in a directory
outside both packages that selects them by path, write both widgets into its
`index.html`, and run the render check, which draws the pair:

```bash
leaf page init --package reading --package ./shortlist --package ./finalists <page>
leaf page check <page> --render
```

Serve that page to try recording and Undo by hand.

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
`toggle-popover`, act on dialogs and popovers. The request's argument is the button's
plain `value`, JSON text only where a request needs several fields, and the button's
words name the gesture, as Undo shows it. `type="button"` keeps a button inside a form from
submitting it instead. `page check` refuses an authored button whose `commandfor`
names no element, or whose `command` is neither kind; a custom command the target
doesn't handle does nothing, with no error.

The target decides what a request does: it takes the request as its own change,
adjusts it, or refuses it with `event.preventDefault()`. So the asker draws the
target's value, never what it asked for, and draws again from that value after every
request, taken or not. Where the target sets its value inside its `command` listener,
Leaf has set the asker's input by the time `dispatchEvent` returns, and where the value
stays as it was, Leaf sets nothing. So a rent slider that asks a budget table for 60,
when the table already holds rent at its cap of 40, gets no set, and one that kept
its thumb where the user dragged it would show 60 beside 40.

A request no button on the page makes, such as a dragged handle, a typed number or a
drop on a board, is the same event. The module dispatches it on the target, found
with `elementById`, from a button it makes and keeps out of the page, since `click()`
on that button would send nothing. It sends the event `cancelable`, as the browser
does, so the target can refuse it:

```js
const taken = elementById(this.getAttribute("for"), this)?.dispatchEvent(
  new CommandEvent("command", {
    command: "--set-amount",
    source: Object.assign(document.createElement("button"), {
      value: "60",
      textContent: "Set rent to 60",
    }),
    cancelable: true,
  }),
);
```

A module that draws a button in the page writes the same attributes as an authored
one, taking the id from its own reference attribute, as in
`commandfor=${this.getAttribute("for")}`. The browser makes the press, so the button
needs no click listener and no `lfCommands` row, a key and a finger press it as a
pointer does, and it works the same on a page without Leaf. A press does nothing until
the target's module has loaded, as with any control a module wires. A button in a
shadow tree can't send a request to a target outside that tree this way, since the
target sees the shadow's host as `event.source`, so a module drawing there sends from
its button's click listener as above.

## User state

A widget records each change the user makes as an `action` event in the page's log; the
package writes no storage or server code. It declares each kind of change as a verb
under the element's `verbs`. Leaf validates each event, works out the current
state, hands it to the module, and shows it to the agent under `state` in `leaf page
state`.

A verb declaring `decides: true` selects which of its widget's members retire. It
folds by widget and requires a string-enum `outcome` field. A member's
`retired-when` and the verb's own `withdraws` name those outcomes. An `outcome`
field on any other verb is ordinary domain data; whether an action answers an
obligation is separately declared by `awaits`.

The default board declares `move` as a position record in
`packages/default/registry.json`:

```json
{
  "verbs": {
    "move": {
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
over it until a `restated` event takes one back. A version takes a decision back by
setting the boolean `restated` attribute on the element it rests on, and stamping that
version records the retraction (the registry's `$restated`). The `$keys` entries in
`browser/registry.json` define each key exactly.

The record kind fixes the event's payload, a closed object with every field required:

- `body` sends `{value}`, a string that replaces the widget's body.
- `attribute` sends `{value}`, an array of distinct member ids, marked by the boolean
  attribute `record.attr` names (`module-plain-elements.md`, "Members").
- `value` sends `{value}`, matching the schema of the attribute `record.attr` names in
  the widget's `attributes`. That schema is a string or a string enum, since an
  attribute holds no other JSON type, so a number is recorded as its digits. It is
  the kind of a record that names none, so `{ "attr": "verdict" }` is a value record.
  The record may also name the element's property that holds the value, so that Leaf
  records it with no module code (`module-plain-elements.md`,
  "`record.property`").
- `position` sends `{unit, value, rank}`: the moved element's id, the destination
  container's id, and the element's rank there. A container is an element of the tag `record.within` names, a declared
  one, with an id of its own, and its members are its children that have ids. It is
  the widget itself where `within` names the widget's own tag, as for a list the user
  reorders, or an element inside the widget, as each column of a board is.

`leaf page state` lists each move in force with its container and rank, and gives the
order that results on the widget's entry in `elements`: `order` maps each position verb
to each container's member ids in the order the page draws them. Authored members rank
`1`, `2`, `3` and on in authored order, in base 36, a move gives its member the rank it
names, and each container lists its members by rank, compared as strings (the
registry's `$verbs.record`). Once a version changes which members a container holds, or
their order, the moves made before it stay in the log but no longer place their
members: that version's author writes each container's members in the `order` the
active version showed, and those moves can no longer be undone.

A recorded verb names no `unit`, since its record decides what its state is about:
the moved element for a position record, and the whole widget for any other. A verb
with no record declares its own `detail` JSON Schema. It keeps one state for the whole
widget, as a playground's `choose` keeps its submitted settings, unless its `unit` names
a required string detail field that says what each action is about, by element id or by
data key; the verb then keeps a state for each. That schema holds only `properties`, which names its fields, and
`required`, so a rule across fields, such as `if`/`then`, is refused; each property
takes any schema. Leaf writes the schema's `type` and `additionalProperties`
(`packages.md`, "A widget"), so an action's detail holds only the fields `properties`
names.

For an optional command the agent should act on, such as Archive, declare
`attention: true` on its user verb (`$verbs.attention` in the registry). Changes to
that verb's state reach the agent without putting a question on the user's On Me list.
Use `awaits` below when the widget instead asks the user for an answer. A verb
that
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
those two fields. Leaf reads that text as inline Markdown the user typed, so the parent
draws it in that reading (`module-reading.md`, "Markdown"). Each
added child is its own key, so undoing the add removes it. The child's tag lists the
widget in `owners`, requires only an `id`, and has `content: markup`.

The added child belongs to its parent. Its entry may have a module and a shadow root for
presentation, but `package check` refuses one that declares state, obligations,
history, data or visual parts of its own; the parent records and draws
it. Removing the child doesn't withdraw the parent's actions, so a parent selection
still in force selects the same id if it returns. A widget that needs its own actions
or services belongs in authored markup.

A verb the agent writes, such as the task `status` on the Atlas example page, declares
`"writer": "agent"` and an `attribute` or `value` record. A worker sets
it with `leaf page report`; the page shows it at once, and it stays until a new version
answers it. `text: true` requires each report to carry short news for a person in
`detail.text`. Each verb has one writer, so no key holds both a user's action and an
agent's report. A widget with such a verb takes a boolean `overruled` attribute, which a
version sets to keep its authored state over the report. A widget with a user verb
that keeps one state for the whole widget takes a boolean `restated` the same way,
which a version sets to take the user's decision back. Leaf writes both into the composed declaration, so the
package's own lists neither. An element that another widget's verb names by id, as
`lf-board`'s `move` names an `lf-card`, lists `restated` itself.

`awaits` puts a widget's obligation on the user's list, On Me. Its `value` names
the verb whose state is the answer: the recorded value, or a recordless verb's latest
`detail`. A playground's unrecorded `choose` gives its submitted settings.
Whether the obligation is answered is the widget's own word, its `answered` fact,
which the declaration lists under `facts` as `{"type": "boolean"}`: its class's
`static answered(state, element)`, or, without one, whether that verb holds a state
([module-state.md, "Declared widget
state"](module-state.md#declared-widget-state)), counting only the user's acts in
force: a starting value the page's markup writes answers nothing. So a queue whose
question is answered once its marked column is empty says so from the positions its
`state` holds, and a checklist decided step by step says so once its last step is.
The widget says it on each gesture and as a version or another tab's act moves it,
so a version adding a step to a checklist asks again, keeping the other steps'
decisions, once a tab shows it. Marking an element `restated` asks again too: it
withdraws every decision resting on that element, and the question stays open
until the user's next gesture says otherwise. If the widget's `when` stops
holding, a complete obligation stays answered and an incomplete one is withdrawn.

`awaits.retired` names the attribute an author sets to close an obligation but
keep its widget on the page, such as a decided question collapsed with its options;
`when` must require it to be absent. The group the author names round a widget is its
obligation's question, its region and its words (`authoring-on-me.md`, "On the page"),
so a widget needs no prompt of its own.

The module reads this state as `this.state` and records it with `record()`
([module-state.md, "Reading and recording state"](module-state.md#reading-and-recording-state)),
words answers with `static answerWords` ([module-state.md, "Declared widget
state"](module-state.md#declared-widget-state)), and reads obligations with `readObligations()`
([module-reading.md, "Reading obligations and the
On lists"](module-reading.md#reading-obligations-and-the-on-lists)).

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
authored revision, or from the message holding a thread widget, and resolves
it using the command’s revision registry. Changing only the selected contract keeps
any earlier action whose value fits the new schema. The log keeps the original action
and its schema.

## References between widgets

When an attribute names another element, declare it in `refers`, mapping the
attribute to `{}`, which accepts any element id. The attribute an input names as its
`reference` ("Widget outputs") needs no entry, as the registry's `$keys.inputs`
defines. `page check` refuses an id that names no element.

Rules about content, such as a value within its range, belong to the widget and `page
check --render`.

## Work roles

Leaf owns four work roles and reads a hierarchy of work from them
([module-reading.md, "Work hierarchies"](module-reading.md#work-hierarchies)). A
package maps its tags onto them in `$work.widgets`:

- `scope` bounds a hierarchy; a reading stops at a nested scope.
- `goal` is a piece of work. `state` names the attribute holding its state, which
  exactly one verb's value record names, and `done` and `stopped` list the
  values that mean finished and stopped. `stoppedAt` may name an attribute saying
  when it stopped.
- `worker` is an agent doing the work, with `state`, the values that mean `running`
  and `retired`, and optionally `on`, a `refers` attribute naming the goal it works
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

A widget declares the inputs it can show under `inputs`, each naming its contract,
the attribute that carries the page's source id, and the element `property` Leaf sets to
the value. Naming the attribute there declares it, as the registry's `$keys.inputs`
defines; list it in `required` when the widget can't work without the input. A widget
with `content: data` takes its `<pre>` as its `value`, as a `<textarea>`'s text is:
where the markup binds the input whose `property` is `value` to nothing, Leaf sets
`value` to the `<pre>`'s text, a string, so the widget reads one property either way, as
`lf-text-document` and `lf-diff` do. Give that input a contract that admits a string.
Leaf leaves the property of any other unbound input to the widget. Tell page authors
how to bind it in `instructions`, and whoever produces the data in the contract's
`instructions` (`packages.md`, "Package contract").

`page check` requires one `<pre>` on a widget with `content: data`. Where the markup
binds the `value` input, it refuses the `<pre>`. Where the widget has a `value` input
and the markup binds only its other inputs, it takes the element with or without a
`<pre>`, since those inputs may supply the data in its place, as `lf-diff`'s two
compared texts do. Say in the widget's `instructions` which the widget wants, and
report a `<pre>` it won't read as an `error` (`module-plain-elements.md`, "`error`").

```json
{
  "lf-builds": {
    "description": "The current build result of each branch.",
    "attributes": {
      "required": ["id", "source"]
    },
    "content": "empty",
    "inputs": {
      "builds": {
        "contract": "build-status",
        "source": "source",
        "property": "value"
      }
    },
    "instructions": "Bind `source` to the build feed this page should show."
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
`"outputs": {"files": {"contract": "file-list"}}`; the contract is an ordinary
`$data.contracts` entry, and the output's name is the element property that holds it.
The module sets that property to the complete value, or `null` while it has none, and
then dispatches `change` on the element, as a form control does for `value`:

```js
this.files = { files: entries };
this.dispatchEvent(new Event("change"));
```

A consumer reads an external source or another widget's output through the same kind
of input, declaring `source`, `reference` or both:

```json
"inputs": {
  "files": {
    "contract": "file-list",
    "source": "source",
    "reference": "for",
    "property": "value"
  }
}
```

A page binds either `source="project-files"` or `for="review"`, where `review` is a
widget holding a `file-list`. The input binds by contract: it reads the one output of
its contract the named widget declares, whatever that widget calls it, so a consumer
never names a producer's tag or its output and works beside any producer of the
contract. `page check` refuses a `for` naming a widget with no output of the contract,
or with more than one.

Leaf reads the property when the consumer first draws, again each time the producer
says `change`, and from the new element when a revision replaces the producer, so a
consumer draws the current value whichever module loaded first. The consumer gets its
own copy and redraws only when the value differs. Assign a new value rather than
editing the held one, and say `change` after each assignment: Leaf takes the object
the widget already held as unchanged without reading into it, so a large value costs
its readers nothing while another output changes. Hold what changes often, such as a
selection, as a small output of its own beside the large one. Dispatch it on the
element itself: a control inside the element says a bubbling `change` of its own,
which Leaf doesn't count, and which a module listening on its own element tells apart
by `event.target`. Where a verb also records the property (`module-plain-elements.md`,
"`record.property`"), its `record` names the event that reports a change, so Leaf
also reads the property again at that event, even from a control inside the element,
and after Leaf sets the recorded value.

Leaf sets the consumer's property before the producer's `dispatchEvent` returns. A
consumer that draws in its setter has drawn by then; a consumer that extends
`LeafElement` draws after the dispatch returns, in the same frame.

On a page without Leaf the same module needs no import for this, and the host does
the binding itself: `review.addEventListener("change", () => (tree.value = review.files))`.

`page check --render` and `package check --render` validate the value an output
holds each time its element says `change` during their render, including values later
withdrawn or replaced and values from contained samples whose frames are later
disposed. They listen at the window, so they check a producer inside another widget's
shadow tree only where its `change` is composed, which `new Event("change")` is not. A
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
the source's file under `data/` in one step, or leaves it untouched. Open tabs pick up the new
value at once. `leaf data clear` removes the value, and each bound widget receives
`null`. A value that stops fitting a later contract shows users an error for that
source, and `page check` and `page state` report it. A stamped version keeps the
contract it was stamped with, so a value written for a changed contract shows there as
a source error. `leaf page state PAGE` lists each bound source under `data_bindings`, so
a producer needn't parse markup. Every value goes to every user of the page, so never put
credentials or private host state in one.

A file the page binds with `leaf file bind` is a source too, under its binding's id:
a `text-document` value `{key, name, text, revision}`, the binding, the file's name,
its text and its revision, which Leaf reads again each time anyone writes the file.
`leaf data set` and `leaf data clear` refuse that id, since writing the file is what
changes it, and `page check` refuses an input of another contract that binds it.

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
missing, empty or not a string. `lf-diff`'s contract, whose value
has a `files` array of `{path, patch}` objects, declares `{ "records": { "items":
"files", "key": "path" } }`.
