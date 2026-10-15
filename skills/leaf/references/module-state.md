# Widget state and data

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers the widget controller that records durable user state, declared widget state, bound data and its projections, and editing a bound file.

## The widget controller

A registry-declared widget is a `LeafElement` (module-authoring.md, "Drawing what a
widget reads") and draws its state in `render()` from `this.state` and
`this.reading`, which Leaf draws again whenever they change. It records state through
`this.controller`, the widget's `widgetController(owner)`, whose methods are `read`,
`dispatch`, `defer` and `present`. Leaf records the widget's id and declaration before
upgrade; if the element's `id` changes afterwards, `read()` reports every action
unavailable and `dispatch()` returns `null`. Only a widget written in page or message
markup has a controller. A member the user adds through a `creates` verb, such as a new
option, has none: its parent reads and draws it from its own state, and passes the
member's asynchronous drawing to `controller.present(promise)`. Leaf itself draws what
the declaration alone decides, such as hiding a suggestion's `lf-old` once it is
accepted (`x-retired-when`).

`read()` returns an immutable `{authored, state, memberships, thread, provenance,
actions}`. `authored` is the state the page's markup sets, and `state` that with every
recorded action applied, including the user's latest gestures before the server admits
them. `memberships` maps each attribute an `attribute` record marks to the ids of the
members the widget currently owns, so a reading changes when a member moves even if the
marked ids don't.
`thread.heldBy` is the id of the open Thread whose opening message holds this widget, or
`null`. Each entry in `actions` says whether the action is available and what Undo can
take back; check it before changing anything for the action. Before the document has
loaded, `authored` and `state` may be missing, and a `LeafElement` draws nothing until
`state` holds every declared verb.

Record a gesture with `dispatch({kind: "action", verb, detail, attempt?})`, and undo one
with `dispatch({kind: "undo", target})`, naming an `id` or `attempt` from the action's
Undo candidates. `dispatch` returns `null` when the action isn't available, throws for a
verb the widget doesn't declare, and otherwise returns `{reading, delivery}`. The reading
already shows the result; `delivery` resolves to the event the server admitted, or
`null`, and a refusal restores the server's state.

During a live edit, or while the user rearranges the widget by pointer or keyboard, call
`const resume = this.controller.defer()` before your first change to the DOM, so Leaf
doesn't redraw under the user. Call `resume()` once `dispatch` has returned, or after
cancelling has put the DOM back; it draws the newest reading. A dragged widget
(`dragging`, `module-input.md`, "Pointer presses") defers for the whole drag.

Pass asynchronous preparation the page should wait for, such as a renderer loading, to
`present(promise)`. Drawing that finishes a draw, such as highlighting what `render()`
placed, goes to `this.drawing(promise)` from `updated()` instead: that draw counts as
shown, and a data delivery it draws as presented, only once the promise settles.

### Tab-local working state

State the user arranges but doesn't record, such as which groups they collapsed, stays
out of the log. `tabStore.get(key)` and `tabStore.set(key, value)` keep a string of it
for this page in this tab; set `null` to remove it. An `x-initial` drawing reads the same
store, so the first paint can show it (`module-authoring.md`, "First paint").

## Declared widget state

`render()` draws the whole state each time it runs, and draws the same result if run
twice; the render check draws it again to hold it to that. `this.state` holds every
declared verb, keyed by name, including the initial values an Undo returns to. Keep nested widgets in place rather than rebuilding
the widget, and remove an optional recorded attribute when its value returns to `null`.
Each verb's state takes the shape of its `unit`:

- With `unit: "widget"`, it is `{action, value, detail}`. `action` is `null` for the
  authored state. `value` is the recorded value, or, for a verb with no record, the
  verb's name while it is in force; `null` means undecided. `detail` carries the event's
  other declared fields.
- With a per-part unit, it holds `units`, each part's `{action, value, detail}` by id.
- A position verb's `value` maps each container id to its ordered member ids, and
  `ranks` gives each member's rank.

`detail` follows the payload [package-data.md, "User state"](package-data.md#user-state)
gives each record kind. A recorded body, attribute or value sends `detail: {value}`. A
move sends `detail: {unit, value, rank}`: the moved element's id, the destination
container's id, and `rankAt(state.<verb>, container, index, unit)`, which places the
unit at `index` among the container's others and keeps it there however other units
move. A verb with no record sends what its `detail` schema declares.

A widget that poses an ask can give its class `static answerWords(value, element)`,
returning short words for the answer in the On panel. `value` is the ask's
`answer.value`, and `element` gives the authored markup, such as option labels; read
only that, not what the module draws. Without it, the On panel shows no words for the
answer (`module-reading.md`, "Reading asks and obligation queues").

## Bound data and projections

A widget reads a bound data source in `render()` through an input its entry declares
([package-data.md, "External or derived data"](package-data.md#external-or-derived-data)):

```js
render() {
  const snapshot = this.data("builds");
  return snapshot ? html`…` : html`<p>Waiting for builds.</p>`;
}
```

Leaf draws the widget again whenever the source's value, contract or validity changes.
`this.data(input)` returns `null` while there is no readable value, including when the
value doesn't fit the contract, which clears the old drawing until a readable value
returns. Otherwise it returns a copy of `{source, contract, revision, run, updated,
value, origin}`, the same copy until the next delivery, so a widget can tell a new
delivery by identity: `revision` identifies the value and `run` the write, so a rerun
with the same value gets a new `run`. A widget whose drawing of the data finishes later
starts it from `updated()` and passes it to `this.drawing(promise)`, so Leaf counts the
source as shown only once it settles.

`this.data` throws for an undeclared input and reads the element's binding once.

Rows whose contract declares a `deferred` field arrive without it. Fetch one row's field
with `loadDeferred(snapshot, key)`, which throws if the source changed in the meantime.

### Projecting data

Once the widget has placed its nodes (`module-authoring.md`, "Retained nodes"), mark
which of them show data with `projectData(root, datums, {snapshot})`, in the same
synchronous turn that puts the words on screen, so comments on them anchor to the data
rather than to prose:

```js
setChildren(this, rows.map(row => row.node));
projectData(this, rows.map(row => ({
  node: row.node,
  key: row.key,
  label: row.label,
  identity: row.id,
  origin: {...snapshot.origin, path: ["rows", row.index]},
})), {snapshot});
```

`root` is an element with an id, and each datum's `node` must already be under it.
`key` is a unique string Leaf doesn't interpret, and `label` an optional name shown in
thread chrome. Give `identity` where the same subject survives new values of the source:
a comment then follows the subject and keeps the quote the user saw. Without one, a new
value marks comments on that key as outdated. A node left out of the next call loses
its marking.

A widget declaring `x-data` passes the delivered `snapshot`, even `null`, and Leaf
records each datum's source and revision. A datum that knows its place in the JSON gives
`origin: {...snapshot.origin, path: [...]}`; one computed from other widgets gives
`origin: {derived: [{widget: id}]}`. A projection not drawn from a source omits
`snapshot`.

### Time readings

Reading the time synchronously in a `LeafElement`'s `render()`, a `watchProjection`
paint or a `readingPaint` draw makes Leaf repaint it when the time's reading changes. `ago(ts)` words a server timestamp as the page does everywhere: "just
now", then "2m ago", "2h ago", "2d ago". `shortAgo(ts)` is the short form ("now", "2h").
`quietSince(ts)` says whether work last heard at `ts` has been quiet longer than the
server's grace period. For any other reading, use `clockValue((now) => reading)`, with
`now` the server's time in milliseconds.

For a paint outside those, wrap it as `const draw = clocked(element, paint)` and call
`draw()` when state changes; `draw.stop()` takes it off the clock. Where something else
schedules the paint, pass `invalidate` as a third argument: Leaf calls it when the time
changes, and your scheduled pass calls `draw()`. Time read after an `await` isn't
watched.

## Editing a bound file

`boundFile(binding)` reads and writes a file the agent granted this page with
`leaf file bind`. `read()` returns `{label, text, revision, newline, bytes}`, with `text`
in LF line endings. `save({revision, text})` writes only if the file is still at
`revision`; otherwise it throws an error whose `current` holds the newer file.
`watch(callback)` calls back whenever the file may have changed on disk, including after
the widget's own save, so read it again then. `writable` is false in captured documents
and exports. Editing the file records nothing in the page's log and takes no part in its
Undo. The `file-editor` package's `lf-file-editor` provides this; use `lf-code` for a
snapshot that should travel with the page.
