# Widget state and data

Read with [module-authoring.md](module-authoring.md).

## Where a widget keeps its state

Leaf keeps every kind of state a widget has; the module writes no storage or server
code of its own. Choose by what the state is:

| State                                                                                      | Kept through                                                                                                  | Who sees it                                                                                                         | How the widget hears of a change                                                         |
| ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| What the user makes: a choice, a move, an edit, a playground's settings before they submit | a verb under `verbs` ([package-data.md, "User state"](package-data.md#user-state)), recorded with `lf-action` | every tab and device, and the agent; the verb's `attention` or `unsent` says whether a change asks the agent to act | Leaf sets `state` again, whether this tab, another one, Undo or a new version changed it |
| Words the user writes to send                                                              | a draft ([module-input.md, "Text entry and drafts"](module-input.md#text-entry-and-drafts))                   | every tab and device showing the page, until sent                                                                   | the draft's `watch`                                                                      |
| How the user looks at the widget in this tab: an open panel, a step, a collapsed group     | `tabStore` ("State only this tab keeps")                                                                      | this tab                                                                                                            | only this tab writes it; read it as the widget builds                                    |
| Data the agent or a source publishes                                                       | a bound property ("Bound data and projections")                                                               | everyone                                                                                                            | Leaf sets the property                                                                   |
| What the widget shows or derives now, for another widget to follow: a step, a selection    | an output ([package-data.md, "Widget outputs"](package-data.md#widget-outputs))                               | the widgets on this page that name it, in this tab                                                                  | the widget sets it, and Leaf sets a reader's bound property                              |
| A text file on disk                                                                        | `boundFile()` ("Editing a bound file")                                                                        | whoever reads the file                                                                                              | `watch(callback)`                                                                        |

Undo tells the first row from the third. Record a change the user would expect Undo to
take back, and that a comment on the page may be about. Keep in the tab what Undo should
leave alone, such as which panel they opened. State a module keeps in `localStorage`,
IndexedDB or memory never reaches another device or the agent, and Undo can't take it
back.

## Reading and recording state

A registry-declared widget draws its state from `state`, the property Leaf sets,
records a gesture with an `lf-action` event and takes one back with `lf-undo`
(`module-plain-elements.md`). Check a verb's `available` before changing anything for
it, and its `undoable` before offering to take it back.

Only a widget written in page or message markup has a state, and only under the `id`
it had at upgrade. Elsewhere, as off Leaf (`module-authoring.md`, "A widget that also
runs off Leaf") or on an element with no `id`, Leaf sets no `state` and an `lf-action`
records nothing, so a widget that also runs there draws its markup. A member the user adds through a `creates` verb, such as a new option, has
none either; its parent draws it from its own state. Leaf itself draws what the
declaration alone decides, such as hiding a suggestion's `lf-old` once it is accepted
(`retired-when`).

A widget reads and records only its own state. Nothing tells it when Leaf sets
another element's `state` again, so a widget that follows another reads that widget's
output and asks it for a change with an invoker command
([package-data.md, "Widgets working together"](package-data.md#widgets-working-together)).

`says`, in an `lf-action` event's `detail`, names the gesture in the widget's words,
such as `Chose “Fast”`. Leaf's acknowledgement shows it, and so does Undo in the tab
that made the gesture, so post no notice of your own for it; another tab, or this one
after a reload, names the gesture in Leaf's own words.

The user takes their latest gesture back with ⌘Z, Ctrl+Z off a Mac, or with the Undo
row in the leaf's menu.

A widget says its own drawing under way, such as a renderer loading, with a
`pending-task` event (`module-plain-elements.md`, "Drawing").

### State only this tab keeps

`tabStore.get(key)` and `tabStore.set(key, value)` keep a string for this page in this
tab, such as which groups the user collapsed; set `null` to remove it. Read it as the
widget builds, so the first visible state reflects it (`module-authoring.md`, "First
paint"). `tabStore.keys()` lists the keys set, and `tabStore.read(key)` answers
`{available, value}`, which tells a key never set from a store the browser has switched
off; `tabStore.where(key)` names the browser's storage entry behind a key.

A widget that shows one member at a time (`views`, `module-authoring.md`, "First
paint") keeps the open member in the tab too, through these helpers. A member's native
`hidden` attribute is view state. Read `viewMembers(holder)` for the canonical member
list, including holders a module creates. Reading members or the opening choice changes
no DOM. As the widget builds, open the member `openingView(holder)` returns, and show each
later member with `keepView(holder, member)`, which applies native visibility and
remembers it for reload. Passing null shows none without forgetting the last member.
During an exit animation, `keepView(holder, member, leaving)` keeps one outgoing member
visible too; call it again without that member when the animation ends. Only the
selected member is saved. Pass `null` as a second argument to get null where neither
the address nor the tab names a member, and choose then.

Show each member with `keepView` rather than by writing `hidden`, so that Leaf hears of
a switch before the member the user leaves is hidden, while the page can still say
where they were in it. Leaf shows a member too, as the browser's find, a fragment or
travel reveals it and as Back or Forward returns to it. The member gets a `beforematch`
event then (`module-scroll-and-motion.md`, "Travel and history"). In its listener the
widget shows the member with `keepView`, as it does for a press, and redraws what marks
its open member: where Leaf has already shown the member, as it has for one the page's
own tree holds, the call changes nothing. From `keepView` and those reveals Leaf keeps
two things for the widget:

- **The address**, where the widget says its members are the page's views
  (`data-lf-page-views`, `module-plain-elements.md`).
- **The user's place in each member**, where the members stand in the page's flow,
  because the widget declares `flow` or is the page's parts, and each member has an
  id. A member the widget shows opens where the user last read it in this tab. One
  they never read past its start leaves the page where it stands, unless the page is
  scrolled past that start, and then it opens at its start, under the headers stuck
  over it (`module-scroll-and-motion.md`, "Sticky headers"). A member something
  reveals is placed by whatever revealed it. A member of any other widget is a box in
  the page, and showing it scrolls nothing.

## Declared widget state

The `state` setter draws the whole state each time Leaf sets it, and draws the same
result if set twice; the render check draws it again to hold it to that. Keep nested
widgets in place rather than rebuilding the widget, and remove an optional recorded
attribute when its value returns to `null`. `state` holds every declared verb by name,
each in the shape of its `unit`:

- For a verb that keeps one state for the whole widget, it is
  `{action, value, detail}`. `action` is `null` for the
  authored state. `value` is the recorded value, or, for a verb with no record, the
  verb's name while it is in force; `null` means undecided. `detail` carries the event's
  other declared fields.
- With a per-part unit, it holds `units`, each part's `{action, value, detail}` by id.
- A position verb's `value` maps each container id to its ordered member ids, and
  `ranks` gives each member's rank. Leaf moves no member: the widget places each
  container's members in that order as it draws (`module-authoring.md`, "Retained
  nodes").

For a verb with a record, `detail` is the payload
[package-data.md, "User state"](package-data.md#user-state) gives for its record kind. A
move's `rank` comes from `rankAt` in the library's
[`rank.js`](../../../browser/runtime/lib/rank.js), which gives the key for the index
the unit was dropped at among the container's other units. That key keeps the unit's
place whichever other moves are in force. A verb with no record sends what its
`detail` schema declares.

A widget that puts an obligation on On Me can give its class
`static answerWords(value, element)`, returning short words for the answer in the On
lists, which otherwise show none. `value` is the obligation's `answer.value`, and
`element` gives the authored markup, such as option labels; read only that, not what
the module draws.

Such a widget says whether its question is answered with
`static answered(state, element)`, returning `true` or `false`. Leaf calls it after
each of the widget's actions and each undo of one, with the `state` it then sets on the
element and the authored markup, wherever the widget stands, and sends the answer with
the gesture: the obligation leaves On Me, or returns to it, as the user acts, and the
log keeps the widget's word. `lf-options` answers once a pick is made, or Done is
pressed where it takes several:

```js
static answered(state, group) {
  return group.hasAttribute("multiple")
    ? Boolean(state.answer?.action)
    : Boolean(state.choose?.action) && state.choose.value.length > 0;
}
```

A class without it is answered while the user's acts in force hold a state at the
verb `awaits.value` names: an action there that records a non-empty value, or, for a
verb with no record, any action there. Either way, `answered` reads only the user's
acts, never a value the markup holds, as lf-options' reads `action` beside its
`value`. Only the user's gestures carry the word, so a version that writes an answer into the markup
answers nothing: one that settles a question retires it (`awaits.retired`), and one
that asks a decided question again marks it `restated` (`authoring-revisions.md`).

## Bound data and projections

A widget reads a bound data source through the property its input (`inputs`) names
([package-data.md, "External or derived data"](package-data.md#external-or-derived-data)),
`"property": "value"` for most widgets. Before each update the delivery moves, Leaf
sets that property to the source's value, or `null` while there is no readable value,
including when the value doesn't fit the contract. On a `LeafElement`, declare it as a
Lit property and read it in `render()`, as a widget would read a value any host sets; a
plain element defines a setter that draws:

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
the same value delivers a new copy too. Where the markup binds the input of a widget
whose body is data (`content: data`) to nothing, as with an `lf-diff` showing its
inline patch, Leaf sets the input's property once, with its first sets, to the text of its
`<pre>`. Any other unbound input is left to the widget (`package-data.md`, "External
or derived data").

An input bound to another widget's output reads through the same property, as the
value that widget holds (package-data.md, "Widget outputs"). The producer sets its
output property and says `change` in the turn that commits the matching rendering,
and holds `null` rather than keep stale records after a failed replacement. The
running page doesn't check a held value against its contract, so hold only values
that fit it.

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

The detail holds one key, the property its input names (`value` above), with the value
drawn from it. Leaf stamps the marks with that value's source and revision, so a draw
that finishes after a newer value arrived keeps the revision it drew. Name the value
Leaf set, not a copy, or `null` for words no bound value supplied, such as records the
widget composed itself. A string or number value can be one you still hold or one Leaf
set after the value you last reported; after reporting a newer one, don't go back to an
older one. A widget with several bound inputs marks the items of one of them and names
that one, since a widget's marks carry one source. Marks on nodes inside a nested
widget belong to that widget. On a page without Leaf, nothing listens and the marks
mean nothing.

### Time readings

To say how long ago a server timestamp was, a template draws Leaf's `lf-age` element,
as a page's markup does: `<lf-age datetime=${ts}></lf-age>`. It needs no import, in a
shadow tree too. It words the age as the page does everywhere, "just now", then "2m
ago", "2h ago", "2d ago", and keeps it current. Pointing at it says when, in the
reader's zone and as their browser writes a date: "Sat, Aug 15, 2026, 2:02 PM PT".

`clockValue((now) => …)` states any other condition on the time, such as whether a
timestamp is older than a limit or which day a date falls in. It is a page reading
(`module-reading.md`, "Page readings"). `now` is the server's time in milliseconds,
the clock an age reads, so the answer never disagrees with an age beside it; keep no
clock of your own. Return the answer rather than the time, as in
`clockValue((now) => now - Date.parse(collected) > STALE_MS)`: the render that read it
runs again only when that answer changes.

## Editing a bound file

`boundFile(binding)` reads and writes a file the agent granted this page with
`leaf file bind`. `label` is the file's path below the deepest folder holding every
file the page binds, or `null` until the page's state names it. `read()` returns
`{label, text, revision}`, with `text` in LF line endings. `save({revision, text})` writes only if the
file is still at `revision`, and resolves the saved `{label, text, revision}`. Where the server refuses the save, which then wrote nothing,
it resolves `{refused, current}` instead: `refused` is the server's reason, and
`current` the newer file where the file was no longer at `revision`, else `null`. It
rejects where the page isn't `writable`, and where the server gave no refusal, as when
the request went unanswered, a proxy answered in the server's place or the server
failed after writing; then the save may have reached the file. `watch(callback)` calls
back whenever the file may have changed on disk or its label changed, the widget's own
save included, so read it again then. `beside(path)` gives the address the page's own
server answers a file at by its path from the bound file's folder, such as a picture
a README names, `../` included, or `null` where the page isn't `writable`. The path
can name any file the user can read outside Leaf's state, so on a page that binds a
file, any code the page runs, its packages' and any it loads from another server
included, can read the user's files and send them anywhere. `writable` is false in captured documents and exports. Editing the file
records nothing in the page's log and takes no part in its Undo. The `file-editor`
package's `lf-file-editor` provides this; use `lf-code` for a snapshot that should
travel with the page. A widget that only shows the file binds it as a source by its
binding's id instead ([package-data.md, "External or derived
data"](package-data.md#external-or-derived-data)).

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

The page must have an active Codex, Claude Code or Pi claim, and a Claude Code claimant's
session must be running, since Leaf's plugin in it makes the call. The host reuses that
harness's existing login and selects its model: Luna for Codex, Haiku for Claude, and the
model the user configured for Pi. Neither Claude Code's call nor Pi has a
structured-output mode, so each is given the schema and its answer is validated against
it; an answer that doesn't match rejects the promise.
Credentials stay on the host; a widget cannot choose the model or supply tools. Leaf does not yet enforce a
spending allowance: repeated calls can continue to incur charges. Usage is returned
per call, not retained as a billing ledger. Independent generation calls run
concurrently, while ordinary page interactions remain available.
