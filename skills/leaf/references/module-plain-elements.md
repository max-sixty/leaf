# Plain custom elements

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

A widget needs no base class. On an element whose tag declares `verbs` or `inputs`,
Leaf sets the widget's state and bound data as properties and hears what it records as
events, so its module needs none of Leaf's helpers. This one draws with Lit:

```js
import { html, render } from "/vendor/lit.js";

const CHOICES = [
  ["ship", "Ship"],
  ["hold", "Hold"],
];

customElements.define(
  "lf-verdict",
  class extends HTMLElement {
    set state({ decide }) {
      render(
        CHOICES.map(
          ([value, label]) =>
            html`<button
              type="button"
              data-lf-part="choice:${value}"
              aria-pressed=${decide.value === value}
              aria-disabled=${!decide.available}
              @click=${() => this.choose(value, label)}
            >
              ${label}
            </button>`,
        ),
        this,
      );
    }

    choose(value, label) {
      this.dispatchEvent(
        new CustomEvent("lf-action", {
          bubbles: true,
          composed: true,
          detail: { verb: "decide", detail: { value }, says: `Chose “${label}”` },
        }),
      );
    }
  },
);
```

Its declaration ([packages.md, "A widget"](packages.md#a-widget)) puts the question on
On Me and admits the ids its buttons mark:

```json
"lf-verdict": {
  "description": "A ship-or-hold decision. Put it in an `lf-group` whose label asks the question.",
  "attributes": {
    "type": "object",
    "properties": { "verdict": { "type": "string", "enum": ["ship", "hold"] } },
    "required": ["id"],
    "additionalProperties": false
  },
  "content": "empty",
  "verbs": {
    "decide": { "unit": "widget", "record": { "kind": "value", "attr": "verdict" } }
  },
  "awaits": { "value": "decide", "answered": { "decide": {} } },
  "visual": { "prefixes": ["choice:"] },
  "example": "<lf-group id=\"release\" label=\"Ship 4.2 today?\"><lf-verdict id=\"verdict\"></lf-verdict></lf-group>"
}
```

- **`state`.** Leaf sets it once the class is defined, and again each time the state
  changes, whether this tab, another one, Undo or a new version changed it. It is
  immutable, and holds each declared verb by name, in the shape `module-state.md`,
  "Declared widget state", gives. Beside that shape each verb holds `available`,
  whether the user may act on it now, which a quoted widget's never is;
  `unavailable`, why they may not, as a phrase the widget can show, such as
  `no agent or server is available`, or `null` where Leaf gives no reason; and
  `undoable`, whether `lf-undo` would take back the action in force. A verb with a
  per-part unit holds `undoable` on each of its `units` instead. The setter draws the
  whole state, and Leaf may set an equal state twice.
- **Bound inputs.** Leaf sets each one's property, and the element marks what it drew
  and dispatches `drawn`, as `module-state.md`, "Bound data and projections",
  describes. Leaf sets no property, `state` included, until the widget's state and the
  data a bound source names have both arrived. A data body the markup binds to nothing
  is set as `value` with those first sets, where its `<pre>` still stands, so the
  element leaves the `<pre>` in place until then.
- **`lf-action`.** The element, or a node inside it, records a gesture by dispatching
  a bubbling, composed `CustomEvent`. Its `detail` holds the `verb`, `detail`, `says`
  and `attempt` that `dispatch` takes (`module-state.md`, "The widget controller");
  `attempt` is the id `sendDraft` hands its `send` (`module-input.md`, "Text entry and
  drafts"), so a refusal returns the words to their draft. Leaf has
  set the resulting `state` by the time `dispatchEvent` returns. On an event it sends,
  Leaf sets the event's `delivery` property, a promise of the event the server
  admitted, or of `null` where the server refuses it and Leaf sets the server's state
  again. An event with no `delivery` recorded nothing, because the verb is unavailable
  or the page runs without Leaf.
- **`lf-undo`.** The same kind of event, with `detail` `{verb}`, or `{verb, unit}`
  for a verb with a per-part unit, takes back the action in force there while
  `undoable` says it may.
- **`record.property`.** An element that keeps a value in a property and dispatches an
  event when the user changes it, as a form control does, records with no
  `lf-action`, so a component written without Leaf can be a widget. The verb's
  `record` names the property, as
  `{ "kind": "value", "attr": "value", "property": "value" }` does, and the `event`
  that reports the user's change, where that event is not `change`. Leaf sets the
  property to the recorded value, which is a string, or to the empty string while
  there is none, so the property must take both. When Leaf hears the event on the
  element, it records the property's value, as a string, as the verb's action, with
  `detail` `{value}`. An event it hears from inside its own set, or while the
  property holds the recorded value, records nothing, so an element may announce
  Leaf's set as it announces the user's change. Where the action can't be recorded,
  as on a quoted widget, or the server refuses it, Leaf sets the property back to the
  recorded value. `attr` names the attribute in which a page's markup writes the
  starting value, as for any value record. Leaf sets `state` on the element too, as
  on any widget, so this form doesn't suit an element with a `state` property of its
  own. Undo names the action in Leaf's own words (`module-state.md`, "The widget
  controller").
- **A third-party component.** A component from a third-party library keeps its own
  tag, since the library's styles and the component's own children find it by that
  tag. The page writes it inside the element the registry declares, as in
  `<lf-picker id="plan"><ui-picker>…</ui-picker></lf-picker>` for a library's
  `ui-picker`. Where the declaration's `record` names a property, the `lf-picker`
  module imports the library and defines that property to read and write the
  component's own:
  `get value() { return this.querySelector("ui-picker").value; }`, and the setter
  to match. The component's event reaches `lf-picker` by bubbling, and a module
  whose component's event doesn't bubble dispatches one of the same name on
  `lf-picker`. The page writes the starting value on `lf-picker`, with every other
  attribute the declaration names, and the component's own attributes on the
  component. A component the package's author writes is the declared element itself,
  under its `lf-` tag, and needs none of this.
- **Drawing.** The page counts the widget as drawn once its setters return. A setter
  whose drawing finishes later dispatches a bubbling, composed `pending-task` event
  whose `complete` property is a promise of that drawing. A setter that throws is the
  widget's failure: Leaf reports it as `failSoft` does (`module-authoring.md`,
  "Upgrade"), stands the box after the element's content, and sets the property again
  with the next change. Where one change moves the state of several widgets, Leaf sets
  a widget's before the state of any widget inside it, so a setter that moves a member
  runs before that member draws.
- **Drawing again unasked.** An element that redraws by itself, as for a timer or a
  value it holds, dispatches the same `pending-task` on itself, and the page waits for
  that drawing too. Leaf promises it no order among the page's other drawing.
- **`lf-connect`.** Leaf first sets an element's properties once it sees the element
  in the page, which is after `connectedCallback` has returned. An element that builds
  or draws from them as it connects dispatches a bubbling, composed, cancelable
  `lf-connect` event from `connectedCallback`, and Leaf makes the sets it can before
  `dispatchEvent` returns. Leaf cancels the event where it will set `state`, at once
  or when the state and bound data arrive, so an element whose event was cancelled
  draws nothing until `state` is set. On such an element whose tag declares no verbs,
  `state` is empty and says its inputs are set. Leaf also gives the open shadow root of
  an element that says `lf-connect` the page's styles and comment support.
- **`lf-hold`.** An element in which the user holds something, as through a drag, a
  keyboard grab or a scrub, dispatches a bubbling, composed `lf-hold` event as the
  hold starts. The event's `complete` property is a promise the element settles as
  the hold ends, is cancelled, or the element leaves the page. Until the promise
  settles, Leaf applies no revision and takes nothing back with Undo, so nothing
  replaces the nodes under the user's hand. A promise the element never settles
  keeps both waiting until the page is loaded again. Leaf goes on setting `state`
  meanwhile, and reads the element's keys again as the hold starts and as it ends.
- **`lf-defer`.** An element may rewrite its own nodes for a while and leave what
  Leaf sets undrawn until it is done, as a drag that moves the nodes does, or an
  editor that stands in place of the element's words. It dispatches a bubbling,
  composed `lf-defer` event as it starts, whose `complete` property is a promise it
  settles as it finishes. Leaf counts a `state` it set meanwhile as drawn only once
  the promise has settled. It reads the page again then, since the nodes changed
  outside any drawing it waited for. `lf-defer` keeps no revision or undo waiting;
  a gesture that needs that says `lf-hold` too.
- **`lf-commands`.** An element's keys are its `lfCommands` property
  (`module-input.md`, "Commands and keyboard routes"). Leaf reads the property each
  time the element dispatches a bubbling, composed `lf-commands` event on itself, so
  the element dispatches one after it sets or replaces `lfCommands`, and after anything
  its rows read changes. Like every event an element dispatches on itself, it is heard
  only while the element stands in the page, so an element built before it is placed
  dispatches once it is placed; `page check --render` reports an element whose
  `lfCommands` Leaf never read (`unread-commands`). A `detail` of `{ within: true }`
  has Leaf read again the rows of every scope already declared on the element or
  inside it, as after a redraw of the nodes those rows read; it declares no scope.
  Leaf reports a declaration it refuses as the element's failure.
- **`lf-layout`.** An element that rearranges what it holds without changing its own
  size, as a view swap does, dispatches a bubbling, composed `lf-layout` event on
  itself. Leaf then reads again whatever it measured or read inside the element, such
  as where a margin entry stands and which parts are comment targets.
- **`error`.** An element that shows a failure its own way reports it by dispatching a
  bubbling, composed `ErrorEvent` named `error` on itself, whose `error` property is
  the failure. Leaf reports it to the agent as a page error naming the widget, which
  fails `page check`.
- **`lf-error`.** To tell the user that something they did has not taken, such as a
  value the server refused, dispatch an `lf-error` event on the window whose `detail`
  is the words, as `lf-announce` is dispatched (`module-scroll-and-motion.md`,
  "Notices and spoken words"). The Leaf panel shows them until the user has dealt with
  them. A failure in the widget itself is an `error`, never an `lf-error`.
- **`redraw()`.** `page check --render` calls this method on an element that has one,
  to draw the same state again, and reports a draw that changes the page.
- **Building.** `connectedCallback` runs again each time a revision or a thread puts
  the element back, so the element guards what it builds once (`module-authoring.md`,
  "Upgrade").
- **On Me and comment targets.** The class's `static answerWords` words its answer
  (`module-state.md`, "Declared widget state"), and `data-lf-part` marks each comment
  target, or the element's `lfParts` states them (`module-annotations.md`, "Visual
  parts").
- **Words it writes.** Words the element writes into the page are the page's: the user
  can comment on them, and a version comparison, which reads each version's source,
  never shows them as a change. To set apart words it writes, such as a count after an
  authored sentence, it marks the element holding them `data-lf-gen="1"`. `named()`
  then leaves them out, and a comment's quote doesn't run across them into the
  author's words. Words in a generated control, such as its label, or in a generated
  box of controls (`module-controls.md`) are apparatus: they take no comment, and a
  printed page drops the control or box. Marked `data-lf-said`, it keeps words that
  are the page speaking, as a pick mark reading "selected" does: they take comments
  and print. Marked
  `data-lf-echo`, it keeps words that copy what the page says elsewhere, such as a
  worker's name: they print and take no comment, which the user leaves where the page
  says them.

`LeafElement` (`module-authoring.md`, "Drawing what a widget reads") is a Lit element
on this protocol. It says `lf-connect`, announces each of its updates with
`pending-task`, defines `redraw()`, and wraps the events as `record()`, `takeBack()`
and `defer()` (`module-state.md`, "The widget controller"). Extend it where the widget
draws from a page reading, such as obligations, history or the time, which its
`render()` follows.
