# A widget's module

Read with [module-authoring.md](module-authoring.md).

A widget is its declaration ([packages.md, "A widget"](packages.md#a-widget)), plus an
Effect UI component defined with `defineWidget` if it draws anything. A widget that
draws nothing, such as a frame around what the author wrote in it, has no module: its
declaration states its facts, and its package's stylesheet its look.

`defineWidget(tag, component, options)` defines the tag as a custom element that mounts
the component; the header of
[`/runtime/effect-widget.js`](../../../browser/runtime/effect-widget.js) is its whole
contract. Leaf drives that element from outside: on an element whose tag declares
`verbs` or `inputs`, it sets the widget's state and bound data, hears what the widget
records and reads what it declares. The component receives Leaf's state as props,
issues a Command of Leaf's services
([`/runtime/widget-services.js`](../../../browser/runtime/widget-services.js)) for what
it asks of Leaf, and declares what Leaf reads off the element. The header of
`widget-services.js` says what each Command does, which can be less than the function
or event a reference describes, as `Announce` carries no `rows`. Where no Command of
Leaf's does what a widget needs, it calls the function or dispatches the event itself,
from a Command of its own (`Command.make`) or a Mount. The component's
Model holds only what the user is doing in the widget, such as a drag under way; a
native disclosure's `open` is the browser's, which the view writes once, as an attribute
that doesn't change, and which a Mount reads off the live `<details>`, and folds there,
where the widget folds, as for Expand all.
`/vendor/effect-ui.js` exports only the modules
[`build/entries/effect-ui/entry.mjs`](../../../build/entries/effect-ui/entry.mjs) names,
and the bundled widgets' modules show their API in use. This widget records a
ship-or-hold decision:

```js
import { Command, Html, Schema, UiSchema } from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { RecordAction } from "/runtime/widget-services.js";
import { pressAttributes } from "/runtime/lib/controls.js";

const CHOICES = [
  ["ship", "Ship"],
  ["hold", "Hold"],
];
const Message = UiSchema.TaggedEnum({
  Chose: { value: Schema.String, label: Schema.String },
});

const Verdict = Html.component({
  name: "Verdict",
  props: Schema.Struct(widgetProps),
  model: Schema.Struct({}),
  message: Message,
}).make({
  init: () => ({}),
  update: {
    Chose: ($, { value, label }) =>
      $.run(
        RecordAction.make({
          verb: "decide",
          detail: { value },
          says: `Chose “${label}”`,
        }).pipe(Command.asNoop),
      ),
  },
  view: (h) => {
    const decide = h.props.state?.decide;
    return h.div.children(
      ...CHOICES.map(([value, label]) =>
        h.button
          .attrs(pressAttributes("answer"))
          .attr("data-lf-part", `choice:${value}`)
          .attr("aria-pressed", String(decide?.value === value))
          .attr("aria-disabled", String(!decide?.available))
          .on("click", Message.Chose({ value, label }))
          .children(label),
      ),
    );
  },
});

defineWidget("lf-verdict", Verdict);
```

The view draws in a box of its own after the element's authored children, which stay
where the author put them, and `pressAttributes` marks each button as a control of
Leaf's answer role (`module-controls.md`). Its declaration puts the question on On Me
and admits the ids its buttons mark:

```json
"lf-verdict": {
  "description": "A ship-or-hold decision. Put it in an `lf-group` whose label asks the question.",
  "attributes": {
    "properties": { "verdict": { "enum": ["ship", "hold"] } },
    "required": ["id"]
  },
  "content": "empty",
  "verbs": {
    "decide": { "record": { "attr": "verdict" } }
  },
  "awaits": { "value": "decide" },
  "visual": { "prefixes": ["choice:"] },
  "example": "<lf-group id=\"release\" label=\"Ship 4.2 today?\"><lf-verdict id=\"verdict\"></lf-verdict></lf-group>"
}
```

Its package's stylesheet gives the element the box its row of buttons takes before the
module draws (`packages.md`, "Seeing it"):

```css
lf-verdict {
  display: block;
  min-block-size: var(--lf-line);
}
```

`leaf package init --widget` writes a smaller widget of this kind to start from
([packages.md, "Package reach"](packages.md#package-reach)). It draws from `state` and
records with `RecordAction` as this one does, under names of its own, and puts no
question on On Me and marks no comment target. Among the bundled widgets, `lf-tally`
in the default package is a short one that reads a page reading through
`options.inputs`, and `lf-options` decorates its authored children from a shadow root.

Each method or property Leaf reads off the widget's element, such as its keys
(`lfCommands`) or its thread outlets (`threadOutlets`), the component sets with
`declare(node, {…})` from a Mount, Effect UI's hook on a node its view drew, where
`node` is that node. The `DECLARED` list in `effect-widget.js` names those members, and
`declare` refuses any other key. Each stands on the element until the root closes, and
each call says `lf-commands` for keys and `lf-layout` for the rest, so Leaf reads it
again; a preview already on screen reads again only on `lf-preview`
(`module-previews.md`). A member Leaf reads off a node the view draws, such as
`lfPreview` on a row or a child outlet's `lfHold`, the view sets on that node with
`.prop()`.

The component's own events, which its `events` schema declares and its `update` emits,
are for the page around it: each reaches the page as a bubbling, composed `CustomEvent`
named by its lowercased tag. Some of what Leaf hears or reads off the element has no
prop, Command or declaration, such as `drawn`, an output's `change` or `lf-hold`. The
component sets or dispatches it on the element from a Mount.
From that node, `closestAcross(node, tag)`, from the library's
[`shadow-tree.js`](../../../browser/runtime/lib/shadow-tree.js), finds the element,
whether the view draws in its shadow root or beside its authored children, unless the
node is itself an element of the widget's tag. Dispatch an
`lf-` event that is about the element on the element, with `bubbles: true` and
`composed: true`, in addition to any option its entry names, since Leaf listens for it
at the document and an ancestor element may listen too; `lf-announce` and `lf-error` are
about no element and go on the window, where they need neither option.

Leaf notices one of these `lf-` events that its listeners will not hear: one that does
not bubble, or, inside a shadow root, one that is not composed. It reports that as a
failure of the element that dispatched the event, as it reports an `error` (below),
and the event has no other effect. It does not notice a `pending-task` or an `error`
dispatched without `bubbles` and `composed`. Nor does it notice anything inside a
shadow root other than the element's own or one `shadowStage` builds
(`module-authoring.md`, "Shadow stages and styles"): there, an event that is not
composed goes unheard and unreported.

Where an entry says an event carries a promise, the promise is the event's `complete`
property:

```js
const hold = new Event("lf-hold", { bubbles: true, composed: true });
hold.complete = finished;
element.dispatchEvent(hold);
```

- **`state`.** Leaf sets it once the tag is defined, and again each time the state
  changes, whether this tab, another one, Undo or a new version changed it, and the
  component receives it as its `state` prop, which `widgetProps` declares. It is
  immutable, and holds each declared verb by name, in the shape `module-state.md`,
  "Declared widget state", gives. Beside that shape each verb holds `available`,
  whether the user may act on it now, which a quoted widget's never is;
  `unavailable`, why they may not, as a phrase the widget can show, such as
  `no agent or server is available`, or `null` where Leaf gives no reason; and
  `undoable`, whether `TakeBack` would take back the action in force. A verb with a
  per-part unit holds `undoable` on each of its `units` instead. The view draws the
  whole state, and Leaf may set an equal state twice. Off Leaf, `state` stays
  undefined.
- **Bound inputs.** The component names each input's property in `properties`, and
  Leaf's set of it arrives as a prop of that name, as `module-state.md`, "Bound data and
  projections", describes, where a Mount says what the view drew with `drawn`. Leaf
  sets no property, `state` included, until the widget's state and the data a bound
  source names have both arrived. A data body the markup binds to nothing arrives with
  those first sets, and its `<pre>` stays in place among the authored children.
- **`lf-action`.** The component records a gesture by issuing `RecordAction`, which
  dispatches `lf-action` on the element, with `{verb, detail, says?, attempt?}`, where
  `verb` names the verb it records and `says` names the gesture in the widget's words
  (`module-state.md`, "Reading and recording state"). `detail` is the action's own, in
  the shape the verb declares: for a verb with a `record`, the payload its record kind
  sends (`package-data.md`, "User state"), and for any other the fields its `detail`
  schema names. Those fields are the package's to name, so they
  stay under `detail`, where none can take the name of Leaf's `verb`, `says` or
  `attempt`. `attempt` is the id a draft's `send` hands its `deliver`
  (`module-input.md`, "Text entry and drafts"), so a refusal returns the words to their
  draft. Leaf has set the resulting `state` before the Command ends, so the gesture's
  result draws before the browser's next frame. The Command succeeds with `admitted`
  once the server admits the event, with `refused` where the server refuses it and Leaf
  sets the server's state again, and with `unrecorded` where nothing recorded it,
  because the verb is unavailable or the page runs without Leaf. A component that draws
  from `state` maps each to nothing (`Command.asNoop`).
- **`lf-undo`.** `TakeBack`, with `{verb}`, or `{verb, unit}` for a verb with a
  per-part unit, where `unit` is the part's id, dispatches `lf-undo` and takes back the
  action in force there while `undoable` says it may. It succeeds as `RecordAction`
  does.
- **`record.property`.** A widget that keeps a value in a property, as a form control
  does, records with no `RecordAction`. The verb's `record` names the property, as
  `{ "attr": "value", "property": "value" }` does, and the `event` that reports the
  user's change, where that event is not `change`. The property is one of the
  component's `members`: its `get` reads the value off the Model, and its `set` returns
  the message that puts Leaf's value there. Leaf sets the property to the recorded
  value, which is a string, or to the empty string while there is none, so the
  property must take both. The component emits the event as the user changes the
  value, and Leaf records the property's value, as a string, as the verb's action, with
  `detail` `{value}`. An event Leaf hears from inside its own set, or while the property
  holds the recorded value, records nothing, so a component may announce Leaf's set as
  it announces the user's change. Where the action can't be recorded, as on a quoted
  widget, or the server refuses it, Leaf sets the property back to the recorded value.
  `attr` names the attribute in which a page's markup writes the starting value, as for
  any value record. Leaf neither disables the widget nor makes it inert, so a component
  that doesn't read the verb's `available` from `state` shows the user's change until
  Leaf sets the property back. Undo names the action in Leaf's own words
  (`module-state.md`, "Reading and recording state"). The tag may also declare the
  property an output for other widgets to read (`package-data.md`, "Widget outputs").
- **A third-party component.** A component from a third-party library keeps its own
  tag, since the library's styles and the component's own children find it by that
  tag. The widget's view draws it, from a binding Effect UI's `Html.customElement`
  makes of the tag, its properties and its events, so the view sets the library
  component's properties from `state` and the Model, and maps its events to messages
  that record as any gesture does. The module imports the library, which defines the
  tag. The page writes only the declared element, as `<lf-picker id="plan">`, with the
  attributes its declaration names.
- **Drawing.** The root mounts once Leaf has made the sets it makes as the element
  connects, so the first props hold `state` and each bound property, and `init` may
  start the Model from them. It mounts as `connectedCallback` returns, or at the end of
  the pass in which Leaf sets `state`; a widget whose bound data Leaf has yet to read
  draws nothing until the data arrives. A later set draws in Effect UI's flush, a
  microtask later and before the next frame, and the element says each such draw with a
  `pending-task` event the page waits for. Drawing that finishes later still, such as a
  renderer a Mount loads, is said by the Mount with a `pending-task` event of its own on
  the element, carrying a promise of that drawing. Where one change moves the state of
  several widgets, Leaf sets a widget's before the state of any widget inside it.
- **Drawing again unasked.** A draw the component's own messages start, as from a
  click, a timer or a subscription, lands in Effect UI's flush too, and the element says
  none of it: no `pending-task`, no `lf-commands` and no `lf-layout`. Leaf promises it
  no order among the page's other drawing. Where Leaf must read something again after
  such a draw, the Mount that states it says so on each change of what it reads, as
  `lf-commands` and `lf-layout` below and `drawn` (`module-state.md`, "Marking drawn
  data") describe.
- **`lf-connect`.** The element dispatches it as it connects, and Leaf makes the sets
  it can before `dispatchEvent` returns; the element mounts once Leaf has made its sets
  ("Drawing"). Leaf cancels the event where it will set `state`, at once or when the
  state and bound data arrive. On an element whose tag declares no verbs, `state` is
  empty and says its inputs are set. Leaf also gives the open shadow root of a widget
  drawn with `shadow: true` the page's styles and comment support.
- **`lf-hold`.** A widget in which the user holds something, as through a drag, a
  keyboard grab or a scrub, dispatches an `lf-hold` event as the hold starts, from the
  Mount that follows the gesture, since no Command says one. It carries a promise the
  Mount settles as the hold ends, is cancelled, or the element leaves the page. Until
  the promise settles, Leaf applies no revision and takes nothing back with Undo, so
  nothing replaces the nodes under the user's hand. A promise never settled keeps both
  waiting until the page is loaded again. Leaf goes on setting `state` meanwhile, and
  reads the element's keys again as the hold starts and as it ends.
- **`lf-defer`.** An element whose own code rewrites its nodes for a while, as a drag
  that moves them does, dispatches `lf-defer` with a promise: Leaf counts a `state` it
  set meanwhile as drawn only once the promise settles, and reads the page again then.
  The element `defineWidget` defines draws every set as it arrives, so a component draws
  a gesture's progress from its Model, as a slider previewing its value does, and says
  no `lf-defer`. Where a Mount builds an editor in place of drawn words, the view draws
  nothing in the editor's box, so no set redraws over it.
- **`lf-commands`.** An element's keys are its `lfCommands` property
  (`module-input.md`, "Commands and keyboard routes"). A component states them with
  `declare(node, {lfCommands})` from a Mount, where `node` is a node its view drew:
  the scope stands on the element while the root does, and each call says
  `lf-commands`, so Leaf reads them again. The Mount takes as its args what the rows
  read, such as the step a row's `when` reads, and declares on each change of them
  (the Mount's `changes`), the one hook Effect UI gives on a draw the component's own
  messages start. After each draw a set of `state`, an input or a member starts, the
  element says `lf-commands` with a `detail` of `{ within: true }`, so Leaf reads again
  the rows of every scope declared on the element or inside it. One of those can be a
  drawn node's own scope, such as a control's, which a Mount sets as that node's
  `lfCommands` and says `lf-commands` on. `page check --render`
  reports an element whose `lfCommands` Leaf never read (`unread-commands`). Leaf
  reports a declaration it refuses as the element's failure.
- **`lf-walk`.** A widget whose keys step the user through something of its own, as a
  diff's do through its hunks, says where each step landed with an `lf-walk` event from
  the step's `run` (`module-input.md`, "Walks").
- **`lf-layout`.** When the element says it, Leaf reads again whatever it measured or
  read inside the element, such as which parts are comment targets and which outlets the
  element offers its threads (`module-annotations.md`, "Widget-local Thread placement").
  `declare` says it for each member but keys, such as `lfParts`, and the element says
  it after each draw a set starts where the component declares parts. After a draw of
  its own messages that rearranges what it holds without changing its size, as a view
  swap does, the component says it from the Mount that hears the draw.
- **`error`.** A root that fails, or an `options.inputs` that throws, reports the
  failure as the
  element's `error`, an `ErrorEvent` named `error` whose `error` property is the
  failure. Leaf reports it to the agent as a page error naming the widget, which fails
  `page check`. Leaf's failure box stands beside the authored children, which stay
  visible. A later successful reading of the inputs removes the box; a root that failed
  stands failed until the element connects again. For a failure nothing throws, such
  as a data body the widget won't read, `options.inputs` throws, or a Mount dispatches
  an `error` on the element.
- **`lf-error`.** Words that tell the user something they did has not taken
  (`module-scroll-and-motion.md`, "Notices and spoken words").
- **Building.** The element mounts the component as it connects, keeps its root when
  it moves, and closes the root, with its Model, a microtask after it leaves the page,
  so the component needs no first-connection guard. A quoted widget's rules are in
  `module-authoring.md`, "Upgrade".
- **Startup.** `lf-presentation` and `lf-page-interface` on `document`
  (`module-authoring.md`, "Startup and presentation").
- **A stroke drawn on it.** `lf-inspect` (`module-input.md`, "Pointer presses").
- **On Me and comment targets.** `options.statics` sets the class's static members:
  `static answered` says whether its question is answered and `static answerWords`
  words the answer (`module-state.md`, "Declared widget state"). `data-lf-part` marks
  each comment target a light view draws; a widget drawn with `shadow: true` gives
  them as the element's `lfParts`, which `declare(node, {lfParts})` states, since Leaf
  reads no mark inside a shadow root (`module-annotations.md`, "Visual parts").
- **A box it scrolls.** `data-lf-scroll` marks a box the element makes scroll, and
  with a name makes it a reading region (`module-scroll-and-motion.md`, "Reading
  regions").
- **The page's views.** An element whose members (`views`) are the page's own views,
  as the first tab set in `main` is, wears `data-lf-page-views` for as long as it is.
  Leaf then names the member it shows in the address, by the member's id. A member
  the element shows itself (`keepView`, `module-state.md`, "State only this tab
  keeps") is the user's step, as a followed link is: Leaf adds a history entry for it,
  and the entry the user leaves keeps where they were. A member something reveals
  renames the entry the user is on, unless that entry's fragment already names a place
  inside the member, and arriving at an address with no fragment renames its entry too.
  Back or Forward to an entry whose fragment names a place inside another member
  reveals that member, and returns the user to where they were on the entry.
- **Previews, spoken words and a Copy control.** `lfPreview()`, `lf-preview` and
  `lf-preview-ended` (`module-previews.md`), `lf-announce` and `data-lf-quiet`
  (`module-scroll-and-motion.md`, "Notices and spoken words"), and `data-lf-copy`,
  `lfCopy()` and `lfBar` (`module-reading.md`, "Code").
- **Its name, the parts a link reaches, its threads and its revisions.** `lfWord()` and
  `lfSays()` (`module-reading.md`, "Naming"), `lfRevealDatum()`, `lfElementsFor()`,
  `lfDataDatum()` and `lfDatumLabel()` (`module-reading.md`, "Following a reference"),
  `threadOutlets()` and an outlet's `lfHold` (`module-annotations.md`, "Widget-local
  Thread placement"), and `static lfPatch`
  (`module-authoring.md`, "Revisions"), which `options.statics` sets.
- **Words it writes.** Words the widget writes into the page are the page's: the user
  can comment on them, and a version comparison, which reads each version's source,
  never shows them as a change. The box the view draws in by default is marked
  `data-lf-gen="1"`, which sets its words apart from the author's: `named()` leaves
  them out, and a comment's quote doesn't run across them into the author's words. A
  widget drawn with `shadow: true` marks the element holding such words
  `data-lf-gen="1"` itself, such as a count after an authored sentence. Words in a
  generated control, such as its label, or in a generated box of controls
  (`module-controls.md`) are apparatus: they take no comment, and a printed page drops
  the control or box. Marked `data-lf-said`, an element keeps words that are the page
  speaking, as a pick mark reading "selected" does: they take comments and print.
  Marked `data-lf-echo`, it keeps words that copy what the page says elsewhere, such as
  a worker's name: they print and take no comment, which the user leaves where the page
  says them.
