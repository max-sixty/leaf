# Widget state and data

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Where a widget keeps its state

Leaf keeps every kind of state a widget has; the module writes no storage or server
code of its own. Choose by what the state is:

| State                                                                                      | Kept through                                                                                                     | Who sees it                                                                                             | How the widget hears of a change                                                                           |
| ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| What the user makes: a choice, a move, an edit, a playground's settings before they submit | a verb under `x-state` ([package-data.md, "User state"](package-data.md#user-state)), recorded by the controller | every tab and device, and the agent; the verb's `attention` says whether a change asks the agent to act | `render()` runs with the new `this.state`, whether this tab, another one, Undo or a new version changed it |
| Words the user writes to send                                                              | a draft ([module-input.md, "Text entry and drafts"](module-input.md#text-entry-and-drafts))                      | every tab in this browser, until sent                                                                   | `watchDraft`                                                                                               |
| How the user looks at the widget in this tab: an open panel, a step, a collapsed group     | `tabStore` ("State only this tab keeps")                                                                         | this tab                                                                                                | only this tab writes it; read it during setup                                                              |
| Data the agent or a source publishes                                                       | a bound property ("Bound data and projections")                                                                  | everyone                                                                                                | Leaf sets the property, and `render()` runs                                                                |
| A text file on disk                                                                        | `boundFile()` ("Editing a bound file")                                                                           | whoever reads the file                                                                                  | `watch(callback)`                                                                                          |

Undo tells the first row from the third. Record a change the user would expect Undo to
take back, and that a comment on the page may be about. Keep in the tab what Undo should
leave alone, such as which panel they opened. State a module keeps in `localStorage`,
IndexedDB or memory never reaches another device or the agent, and Undo can't take it
back.

## The widget controller

A registry-declared widget draws its state in `render()` from `this.state` and
`this.reading` (`module-authoring.md`, "Drawing what a widget reads"), and records it
through `this.controller`, the widget's `widgetController(owner)`, whose methods are
`read`, `dispatch`, `defer` and `present`. Only a widget written in page or message
markup has a controller, and only under the `id` it had at upgrade: if the id changes,
`read()` reports every action unavailable and `dispatch()` returns `null`. A member the
user adds through a `creates` verb, such as a new option, has none; its parent draws it
from its own state and passes the member's asynchronous drawing to
`controller.present(promise)`. Leaf itself draws what the declaration alone decides,
such as hiding a suggestion's `lf-old` once it is accepted (`x-retired-when`).

`read()` returns an immutable `{authored, state, memberships, thread, provenance,
actions}`. `authored` is the state the page's markup sets, and `state` that with every
recorded action applied, including the user's latest gestures before the server admits
them. `memberships` maps each attribute an `attribute` record marks to the ids of the
members the widget currently owns. `thread.heldBy` is the id of the open Thread whose
opening message holds this widget, or `null`. Each entry in `actions` says whether the
action is available and what Undo can take back; check it before changing anything for
the action. Before the document has loaded, `authored` and `state` may be missing, and a
`LeafElement` draws nothing until `state` holds every declared verb.

Record a gesture with `dispatch({kind: "action", verb, detail, attempt?, says?})`, and
undo one with `dispatch({kind: "undo", target})`, naming an `id` or `attempt` from the
action's Undo candidates. `says` names the gesture in the widget's words, such as
`Chose “Fast”`, and Leaf's acknowledgement and Undo show it, so post no notice of your
own for it. `dispatch` returns `null` when the action isn't available, throws for a verb
the widget doesn't declare, and otherwise returns `{reading, delivery}`. The reading
already shows the result; `delivery` resolves to the event the server admitted, or
`null`, and a refusal restores the server's state.

During a live edit, or while the user rearranges the widget by pointer or keyboard, call
`const resume = this.controller.defer()` before your first change to the DOM, so Leaf
doesn't redraw under the user. Call `resume()` once `dispatch` has returned, or after
cancelling has put the DOM back; it draws the newest reading. A dragged widget
(`dragging`, `module-input.md`, "Pointer presses") defers for the whole drag.

Pass asynchronous preparation the page should wait for, such as a renderer loading, to
`present(promise)`, or, from a widget that also runs off Leaf, dispatch it as a
`PendingTaskEvent` (`module-authoring.md`, "A widget that also runs off Leaf"), which
Leaf passes to the same place. Drawing that finishes a draw, such as highlighting what `render()`
placed, starts in `updated()` and extends the element's `updateComplete`, as any Lit
element's completion waits for work its update starts:

```js
updated(changed) {
  super.updated(changed);
  this.highlighting = highlightBlocks(this);
}
async getUpdateComplete() {
  const result = await super.getUpdateComplete();
  await this.highlighting;
  return result;
}
```

The draw counts as shown only once `updateComplete` settles, and a rejection is the
draw's failure. Set the promise on every update, `undefined` when it starts none, so a
finished failure doesn't fail every later draw.

### State only this tab keeps

`tabStore.get(key)` and `tabStore.set(key, value)` keep a string for this page in this
tab, such as which groups the user collapsed; set `null` to remove it. Read it during
setup so the first visible state reflects it (`module-authoring.md`, "First paint").

## Declared widget state

`render()` draws the whole state each time it runs, and draws the same result if run
twice; the render check draws it again to hold it to that. Keep nested widgets in place
rather than rebuilding the widget, and remove an optional recorded attribute when its
value returns to `null`. `this.state` holds every declared verb by name, each in the
shape of its `unit`:

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

A widget that puts an obligation on On me can give its class
`static answerWords(value, element)`, returning short words for the answer in the On
lists, which otherwise show none. `value` is the obligation's `answer.value`, and
`element` gives the authored markup, such as option labels; read only that, not what
the module draws.

## Bound data and projections

A widget reads a bound data source through the property its `x-data` input names
([package-data.md, "External or derived data"](package-data.md#external-or-derived-data)),
`"property": "value"` for most widgets. Before each update the delivery moves, Leaf
sets that property to the source's value, or `null` while there is no readable value,
including when the value doesn't fit the contract. Declare it as a Lit property and
read it in `render()`, as a widget would read a value any host sets:

```js
static properties = { value: { attribute: false } };

constructor() {
  super();
  this.value = null;
}

render() {
  return this.value ? html`…` : html`<p>No builds.</p>`;
}
```

A widget bound to a source first draws once the page has read its data, or has gone
offline without it, so until then it shows its first-paint box. Each delivery is a new
copy, so a widget tells a new delivery by identity. A rerun with
the same value delivers a new copy too. An input the markup leaves unbound, such as an
`lf-diff` showing its inline patch, is left to the widget: Leaf doesn't set its
property.

A widget output reads through the same property, as the value its producer published
with `publishOutput(element, name, value)` (package-data.md, "Widget outputs"). The
producer publishes in the turn that commits the matching rendering, and publishes
`null` rather than keep stale records after a failed replacement. Leaf doesn't check a
published value against its contract, so publish only values that fit it.

Rows whose contract declares a `deferred` field arrive without it. Fetch one row's field
with `loadDeferred(value, key)`, passing the value Leaf delivered that the row came
from; it throws if the source changed in the meantime.

### Marking drawn data

Mark which nodes show data with plain attributes, so comments on them anchor to the
data rather than to prose. After setting the drawing's marks, dispatch `drawn` with
the value you drew, in the same synchronous turn:

```js
setChildren(
  this,
  rows.map((row, index) => {
    row.node.dataset.lfDatum = row.key;
    row.node.dataset.lfIdentity = row.id;
    row.node.dataset.lfDatumLabel = row.label;
    row.node.dataset.lfOriginPath = JSON.stringify(["rows", index]);
    return row.node;
  }),
);
this.dispatchEvent(new CustomEvent("drawn", { detail: { value: this.value } }));
```

`data-lf-datum` is a key unique within the widget that Leaf doesn't interpret, and
`data-lf-datum-label` an optional name shown in thread chrome. Give `data-lf-identity`
where the same subject survives new values of the source, so a comment follows the
subject and keeps the quote the user saw; without one, a new value marks comments on
that key as outdated. `data-lf-origin-path` is an optional JSON array naming the
datum's place in the value. Take a mark off a node you keep once it no longer shows
data; a node you remove takes its marks with it.

The detail names the property and the value drawn from it, and Leaf stamps the marks
with that value's source and revision, so a draw that finishes after a newer value
arrived keeps the revision it drew. Name the value Leaf set, not a copy, or `null` for
words no bound value supplied, such as records the widget composed itself. A string or
number value can be one you still hold or one Leaf set after the value you last
reported; after reporting a newer one, don't go back to an older one. A widget
with several bound inputs marks the items of one of them and names that one, since a
widget's marks carry one source. Marks on nodes inside a nested widget belong to that
widget. On a page without Leaf, nothing listens and the marks mean nothing.

### Time readings

`ago(ts)` words a server timestamp as the page does everywhere: "just now", then "2m
ago", "2h ago", "2d ago". `shortAgo(ts)` is the short form ("now", "2h").
`quietSince(ts)` says whether work last heard at `ts` has been quiet longer than the
server's grace period. For any other reading, use `clockValue((now) => reading)`, with
`now` the server's time in milliseconds. Read them synchronously in `render()`, which
then redraws as the time's reading changes.

## Editing a bound file

`boundFile(binding)` reads and writes a file the agent granted this page with
`leaf file bind`. `read()` returns `{label, text, revision}`, with `text` in LF line
endings. `save({revision, text})` writes only if the file is still at `revision`, and
otherwise throws a `RequestError` whose `current` holds the newer file.
`RequestError` also carries the HTTP `status` and response `body`; distinguish it
with `instanceof` when handling a server refusal. `watch(callback)` calls
back whenever the file may have changed on disk, the widget's own save included, so read
it again then. `writable` is false in captured documents and exports. Editing the file
records nothing in the page's log and takes no part in its Undo. The `file-editor`
package's `lf-file-editor` provides this; use `lf-code` for a snapshot that should
travel with the page.

## Authenticated HTTP connections

An agent can write an integration as page-owned JavaScript, using a named host
connection for credentials. The trusted CLI grants a single HTTPS origin:

```sh
leaf connection bind PAGE source https://api.example.com --credential-env EXAMPLE_TOKEN
```

The variable must be in the binding command's environment. Leaf captures its value
in private host storage, outside page files and exports, so restarting a page
server keeps the grant usable. The default credential header is
`Authorization: Bearer <value>`; `--header` and `--prefix` configure other
header-based APIs. Binding grants the entire origin, so choose a credential with
only the access this page should have. A connection is available to all scripts
on that page, not isolated to one widget.

```js
import { connection } from "/runtime/widget-api.js";

const response = await connection("source").fetch("/items?page=2");
if (response.status !== 200) throw new Error(`Source returned ${response.status}`);
const items = JSON.parse(response.body);
```

`fetch(path)` returns `{status, headers, body}` with a text body. Only relative
paths beginning with one `/` are accepted. Leaf sends GET with the configured
header, refuses redirects, limits responses to 1 MiB and uses a 15-second socket
inactivity timeout.
Transport and grant refusals reject the promise; upstream HTTP errors return their
status and body. No request is retried automatically. The response exposes content
type, pagination/cache and rate-limit headers, not credentials or cookies.

Each grant allows 200 requests by default (`--max-requests` sets its budget).
Leaf reserves a request before sending it, including failed requests; rebinding
explicitly resets the budget. `leaf connection unbind PAGE source` revokes access.
Connections work only on live pages, not captures, exports or live samples.

Keep endpoint paths, pagination, parsing and application policy in the page or a
package. Fetching changes neither page state nor stored data. Publish browser
derivations through widget outputs; use the typed data source workflow when the
result needs to be stored for the page's other readers.

## LLM generation

`generate({input, schema, instructions?})` asks the host's model for a structured
response. `input` and optional `instructions` are strings; `schema` is the required
JSON Schema for the response, within the selected model's structured-output subset.
For portable requests, use an object root, mark every property required,
and set `additionalProperties: false` on each object. Represent optional values with
nullable types. Leaf checks schema validity locally; the harness reports unsupported
schema features as generation errors. Import it from `/runtime/widget-api.js`:

```js
import { generate } from "/runtime/widget-api.js";

const result = await generate({
  instructions: "Write a concise headline for this story.",
  input: story,
  schema: {
    type: "object",
    properties: { headline: { type: "string" } },
    required: ["headline"],
    additionalProperties: false,
  },
});
```

The result is `{value, model, usage, durationMs}`: `value` is parsed JSON matching
the schema, `model` identifies the host-selected model, `usage` is
`{inputTokens, outputTokens}` (counts may be `null` when unavailable), and
`durationMs` measures the generation's elapsed time. Failures reject the promise.
Leaf sends once; the underlying harness may retry network failures. Requests are
limited to 64 KiB of input, instructions and schema combined.

Generation is available only on live pages, not captured documents, exports or live
samples. It collects no external data and writes no page data or events: the caller
supplies the context and decides how to use the returned value.

To render generated Leaf source as an isolated working preview, use
`mountSample(frame, {source})` from the same module. The [generated sample
workflow](live-samples.md#generated-samples) covers readiness, sizing and disposal.

The page must have an active Codex, Claude Code or Pi claim. The host reuses that harness's
existing login and selects its model: Luna for Codex, Haiku for Claude, and the model
the user configured for Pi. Pi has no structured-output mode, so it is given the schema
and its answer is validated against it; an answer that doesn't match rejects the promise.
Credentials stay on the host; a widget cannot choose the model or supply tools. Leaf does not yet enforce a
spending allowance: repeated calls can continue to incur charges. Usage is returned
per call, not retained as a billing ledger. Independent generation calls run
concurrently, while ordinary page interactions remain available.
