# Plain custom elements

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

A widget needs no base class. On an element whose tag declares `verbs` or `inputs`,
and whose class is no `LeafElement`, Leaf sets the widget's state and bound data as
properties and hears what it records as events, so its module needs none of Leaf's
helpers. This one draws with Lit:

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
  whether the user may act on it now, which a quoted widget's never is, and
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
  a bubbling, composed `CustomEvent`. Its `detail` holds the `verb`, `detail` and
  `says` that `dispatch` takes (`module-state.md`, "The widget controller"). Leaf has
  set the resulting `state` by the time `dispatchEvent` returns. On an event it sends,
  Leaf sets the event's `delivery` property, a promise of the event the server
  admitted, or of `null` where the server refuses it and Leaf sets the server's state
  again. An event with no `delivery` recorded nothing, because the verb is unavailable
  or the page runs without Leaf.
- **`lf-undo`.** The same kind of event, with `detail` `{verb}`, or `{verb, unit}`
  for a verb with a per-part unit, takes back the action in force there while
  `undoable` says it may.
- **Drawing.** The page counts the widget as drawn once its setters return. A setter
  whose drawing finishes later dispatches a bubbling, composed `pending-task` event
  whose `complete` property is a promise of that drawing. A setter that throws is the
  widget's failure: Leaf reports it as `failSoft` does (`module-authoring.md`,
  "Upgrade"), stands the box after the element's content, and sets the property again
  with the next change.
- **Building.** `connectedCallback` runs again each time a revision or a thread puts
  the element back, so the element guards what it builds once, as `once()` does for a
  module that imports it.
- **On Me and comment targets.** The class's `static answerWords` words its answer
  (`module-state.md`, "Declared widget state"), and `data-lf-part` marks each comment
  target (`module-annotations.md`, "Visual parts").

Extend `LeafElement` instead (`module-authoring.md`, "Drawing what a widget reads")
where the widget draws from a page reading, such as obligations, history or the time,
which only a `LeafElement`'s `render()` follows, or holds its drawing through a
gesture (`defer`). Leaf sets no `state` on a `LeafElement`.
