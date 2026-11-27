# The widget protocol

Read with [module-authoring.md](module-authoring.md).

On an element whose tag declares `verbs` or `inputs`, Leaf sets the widget's state and
bound data as properties and hears what it records as events. This widget needs no
base class and none of Leaf's functions, and draws with Lit:

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
      const action = { verb: "decide", detail: { value }, says: `Chose “${label}”` };
      this.dispatchEvent(new CustomEvent("lf-action", { detail: action }));
    }
  },
);
```

Lit's `render` calls an `@event` handler with the node it listens on as `this`, so
where a handler is a method of the element, pass `{ host: this }` as `render`'s third
argument. Its declaration ([packages.md, "A widget"](packages.md#a-widget)) puts the
question on On Me and admits the ids its buttons mark:

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

`leaf package init --widget` writes a smaller widget of this kind to start from
([packages.md, "Package reach"](packages.md#package-reach)). It draws from `state` and
records with `lf-action` as this one does, under names of its own, and puts no question
on On Me and marks no comment target.

`lf-action` and `lf-undo` record the widget's own actions and take them back, so Leaf
listens for them on the widget's element: dispatch them on it; they need no option but
`detail`. Every other `lf-` event below that is dispatched on an element, and
`pending-task` and `error`, tells the page something about that element. Leaf listens
for it at the document, and an ancestor element may listen too, so dispatch it on the
element with `bubbles: true` and `composed: true`, in addition to any option its entry
names. `lf-announce` and `lf-error` are about no element, and are dispatched on the
window, where they need neither option.

Leaf notices one of these `lf-` events that its listeners will not hear: one that does
not bubble, or, inside a shadow root, one that is not composed. It reports that as a
failure of the element that dispatched the event, as it reports an `error` (below),
and the event has no other effect. It does not notice a `pending-task` or an `error`
dispatched without `bubbles` and `composed`. Nor does it notice anything inside a
shadow root other than one `shadowStage` builds or the open root of an element that
dispatches `lf-connect` (`module-authoring.md`, "Shadow stages and styles"): there, an
event that is not composed goes unheard and unreported.

Where an entry says an event carries a promise, the promise is the event's `complete`
property:

```js
const hold = new Event("lf-hold", { bubbles: true, composed: true });
hold.complete = finished;
this.dispatchEvent(hold);
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
  arrives with those first sets, so the element leaves its `<pre>` in place until then.
- **`lf-action`.** The element records a gesture by dispatching a `CustomEvent` on
  itself. Its `detail` is `{verb, detail, says?, attempt?}`, where `verb` names the
  verb it records and `says` names the gesture in the widget's words
  (`module-state.md`, "Reading and recording state"). The inner `detail` is the
  action's own, in the shape the verb declares: `{value}` for a verb with a `record`,
  and for any other the fields its `detail` schema names.
  Those fields are the package's to name, so they stay under `detail`, where none can
  take the name of Leaf's `verb`, `says` or `attempt`.
  `attempt` is the id a draft's `send` hands its `deliver` (`module-input.md`, "Text
  entry and drafts"), so a refusal returns the words to their draft. An event that
  bubbles to the element from a node inside it is recorded the same way. Leaf has
  set the resulting `state` by the time `dispatchEvent` returns. On an event it sends,
  Leaf sets the event's `delivery` property, a promise of the event the server
  admitted, or of `null` where the server refuses it and Leaf sets the server's state
  again. An event with no `delivery` recorded nothing, because the verb is unavailable
  or the page runs without Leaf.
- **`lf-undo`.** The same kind of event, with `detail` `{verb}`, or `{verb, unit}`
  for a verb with a per-part unit, where `unit` is the part's id, takes back the action
  in force there while `undoable` says it may.
- **`record.property`.** An element that keeps a value in a property and dispatches an
  event when the user changes it, as a form control does, records with no
  `lf-action`, so a component written without Leaf can be a widget. The verb's
  `record` names the property, as
  `{ "attr": "value", "property": "value" }` does, and the `event`
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
  own. The `state` Leaf sets is how the element learns the user may not act: Leaf
  neither disables it nor makes it inert, so an element that doesn't read the verb's
  `available` shows the user's change until Leaf sets the property back. Undo names
  the action in Leaf's own words (`module-state.md`, "Reading and recording state"). The
  tag may also declare the property an output for other widgets to read, and the
  element needs no code for that either (`package-data.md`, "Widget outputs").
- **Members.** An `attribute` record keeps a set of the widget's members, by id. A
  member is an element that has an `id` and stands inside the widget, with no other
  widget recording the same attribute between them. Any Leaf element can be a member,
  and so can a native element HTML marks with the attribute, which for `checked` is a
  checkbox or a radio. Leaf refuses an action that names any other id, so an answer
  names only members the widget holds.
- **A form of native inputs.** An `attribute` record may name a property and an event
  as a value record does. The property is then each member's, and reads true while
  the member is in the set, as a checkbox's or a radio's `checked` does. With
  `{ "kind": "attribute", "attr": "checked", "property": "checked" }` the page writes
  an ordinary form inside the element, each input with an `id`, as in
  `<label><input type="checkbox" id="plan-team" checked /> Team</label>`, and the
  element needs no property and no code to record it. When Leaf hears the event on
  the element, where an input's `change` reaches it by bubbling, it records the ids
  of the members whose property reads true, in page order, with `detail` `{value}`.
  It sets each member's property from the recorded set, and only on a member that
  reads otherwise, so radios that share a `name` record a set of at most one. An
  input's `checked` attribute writes the starting set. The other rules
  `record.property` gives for a value hold for the set, and two sets are the same
  where they hold the same ids.
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
  whose drawing finishes later dispatches a `pending-task` event that carries a promise
  of that drawing. A setter that throws is the
  widget's failure: Leaf reports it as an `error` (below), stands an error box after
  the element's content, and sets the property again with the next change. Where one
  change moves the state of several widgets, Leaf sets a widget's before the state of
  any widget inside it, so a setter that moves a member runs before that member draws.
- **Drawing again unasked.** An element that redraws by itself, as for a timer or a
  value it holds, dispatches the same `pending-task` on itself, and the page waits for
  that drawing too. Leaf promises it no order among the page's other drawing.
- **`lf-connect`.** Leaf first sets an element's properties once it sees the element
  in the page, which is after `connectedCallback` has returned. An element that builds
  or draws from them as it connects dispatches a cancelable `lf-connect` event from
  `connectedCallback`, and Leaf makes the sets it can before
  `dispatchEvent` returns. Leaf cancels the event where it will set `state`, at once
  or when the state and bound data arrive, so an element whose event was cancelled
  draws nothing until `state` is set. On such an element whose tag declares no verbs,
  `state` is empty and says its inputs are set. Leaf also gives the open shadow root of
  an element that says `lf-connect` the page's styles and comment support.
- **`lf-hold`.** An element in which the user holds something, as through a drag, a
  keyboard grab or a scrub, dispatches an `lf-hold` event as the hold starts. It
  carries a promise the element settles as the hold ends, is cancelled, or the element
  leaves the page. Until the promise
  settles, Leaf applies no revision and takes nothing back with Undo, so nothing
  replaces the nodes under the user's hand. A promise the element never settles
  keeps both waiting until the page is loaded again. Leaf goes on setting `state`
  meanwhile, and reads the element's keys again as the hold starts and as it ends.
- **`lf-defer`.** An element may rewrite its own nodes for a while and leave what
  Leaf sets undrawn until it is done, as a drag that moves the nodes does, or an
  editor that stands in place of the element's words. It dispatches an `lf-defer`
  event before its first change to the DOM, carrying a promise, and until the promise
  settles its `state` setter keeps what Leaf sets and draws none of it, so no redraw
  puts the nodes back under the user. It settles the promise once the gesture's
  `lf-action` is dispatched, or once cancelling has put the nodes back, and draws the
  newest state then. An element that shows a gesture's progress by drawing its state,
  as a slider previewing its value does, says no `lf-defer`. Leaf counts a `state` it
  set meanwhile as drawn only once the promise has settled. It reads the page again then, since the nodes changed
  outside any drawing it waited for. `lf-defer` keeps no revision or undo waiting;
  a gesture that needs that says `lf-hold` too.
- **`lf-commands`.** An element's keys are its `lfCommands` property
  (`module-input.md`, "Commands and keyboard routes"). Leaf reads the property each
  time the element dispatches an `lf-commands` event on itself, so
  the element dispatches one after it sets or replaces `lfCommands`, and after anything
  its rows read changes. Like every event an element dispatches on itself, it is heard
  only while the element stands in the page, so an element built before it is placed
  dispatches once it is placed; `page check --render` reports an element whose
  `lfCommands` Leaf never read (`unread-commands`). A `detail` of `{ within: true }`
  has Leaf read again the rows of every scope already declared on the element or
  inside it, as after a redraw of the nodes those rows read; it declares no scope.
  Leaf reports a declaration it refuses as the element's failure.
- **`lf-walk`.** An element whose keys step the user through something of its own, as
  a diff's do through its hunks, says where each step landed with an `lf-walk` event
  (`module-input.md`, "Walks").
- **`lf-layout`.** An element that rearranges what it holds without changing its own
  size, as a view swap does, dispatches an `lf-layout` event on itself. Leaf then reads again whatever it measured or read inside the element, such
  as where a margin entry stands, which parts are comment targets and which outlets
  the element offers its threads (`module-annotations.md`, "Widget-local Thread
  placement").
- **`error`.** An element reports a failure by dispatching an `ErrorEvent` named
  `error` on itself, whose `error` property is the failure. Leaf
  reports it to the agent as a page error naming the widget, which fails `page check`.
- **`lf-error`.** To tell the user that something they did has not taken, such as a
  value the server refused, dispatch an `lf-error` event on the window whose `detail`
  is the words, as `lf-announce` is dispatched (`module-scroll-and-motion.md`,
  "Notices and spoken words"). The Leaf panel shows them until the user has dealt with
  them. A failure in the widget itself is an `error`, never an `lf-error`.
- **`redraw()`.** `page check --render` calls this method on an element that has one,
  to draw the same state again, and reports a draw that changes the page.
- **Building.** The element builds once, behind a first-connection guard
  (`module-authoring.md`, "Upgrade").
- **Startup.** `lf-presentation` and `lf-page-interface` on `document`
  (`module-authoring.md`, "Startup and presentation").
- **A stroke drawn on it.** `lf-inspect` (`module-input.md`, "Pointer presses").
- **On Me, facts and comment targets.** The class's statics its `facts` lists work
  out what the page keeps of its state, `static answered` whether its question is
  answered, and `static answerWords` words the answer (`module-state.md`, "Declared
  widget state"), and `data-lf-part` marks each comment
  target, or the element's `lfParts` states them (`module-annotations.md`, "Visual
  parts").
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
  Thread placement") and `static lfPatch` (`module-authoring.md`, "Revisions").
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

## `LeafElement`

A widget that draws with Lit usually extends `LeafElement`, the Lit element on this
protocol in the library's
[`leaf-element.js`](../../../browser/runtime/lib/leaf-element.js). Its `render()` draws `this.state`, its Lit properties and the page readings it reads
synchronously (`module-reading.md`, "Page readings"), and runs again when one of them
changes, with handlers bound to the widget as in any Lit element. It says `lf-connect`,
announces each update with `pending-task`, says `lf-commands` after each draw, defines
`redraw()`, and wraps the events as `record()`, `takeBack()` and `defer()`. Its
`setup()` is the build behind its first-connection guard. It draws into the element
itself, so a widget that holds authored children returns from `createRenderRoot()` a
part it generated beside them, or says `static shadow = true` and slots them. The
module's header is the class's whole contract.

Only the class follows a page reading, so a widget that draws from one extends it or
is an Effect UI component that `defineWidget` defines (`module-authoring.md`).
A plain element can still draw its own reports in its `state` setter, since Leaf sets
`state` again as they turn ready (`module-reading.md`, "Page history and reports").
A widget that draws with Lit's standalone `render`, as the opening example does, that
imports nothing, or that wraps a component written without Leaf extends `HTMLElement`.
