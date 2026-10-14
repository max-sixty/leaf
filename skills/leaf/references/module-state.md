# Widget state and data

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers the widget controller that records durable user state, declared widget state, data subscriptions and projections, and editing a bound file.

## The widget controller

`widgetController` belongs to a widget authored in page or message markup. A
user-added `creates` member has no independent controller; its parent reads and
renders that member through its own declared state. A member's asynchronous drawing
joins the parent's presentation with `controller.present(promise)`.

`widgetController(owner)` is the one semantic interface of a registry-declared widget;
callers supply no options. Leaf captures the owner's identity and revision-bound
declaration before upgrade, so an author change to those facts fails closed. Its
methods are `read`, `subscribe`, `dispatch`, `defer`, and `present`.

`read()` returns an immutable `{authored, state, memberships, thread, provenance, actions}` snapshot.
`authored` is the typed baseline decoded from validated source markup; `state` is that
baseline with admitted and unresolved records folded over it. `memberships` maps each
recorded descendant attribute to its current owned member ids, so moving a member
updates the reading even when the selected ids do not change. `thread.heldBy` is the
`id` of the open, admitted Thread whose root holds this widget, or `null`. Each `actions`
entry carries its availability and exact history or Undo candidates. Guard every
optimistic mutation with its entry's availability; `dispatch()` repeats the same check.
Before document adoption the snapshot can lack authored and state values, and while
`defer()` holds presentation it can be newer than the rendered view.

`subscribe(callback)` calls the callback with the complete reading while the widget is
connected, and returns a function that retires that callback. Call it once, during
initialization; no unsubscribe or resubscribe belongs in the connection callbacks. The
controller runs the module's `renderState(state)` only while the widget has a
subscriber, so every semantic widget subscribes, a report-only or quoted one included,
with `() => {}` where it has nothing more to draw. For each reading the controller calls
`renderState` first and the subscribers after, and only once the reading holds every
declared verb. Draw auxiliary semantic UI from the reading passed to `subscribe`,
keeping it across local control repaints. What the declaration alone determines, such
as a holder's settlement (`x-retired-when`), Leaf paints whether or not the module
subscribes. Native listeners, timers, reading regions, margin contributions and thread
surfaces keep their own lifetimes.

`dispatch({kind: "action", verb, detail, attempt?})` and
`dispatch({kind: "undo", target})` return `null` when the newest reading refuses the
command, otherwise `{reading, delivery}`; an action whose verb is not one of the
reading's `actions` throws. The returned reading already holds the
optimistic result; `delivery` later yields the admitted event or `null`, and a refusal
restores authoritative state. Undo targets only a stable `id` or `attempt` from the
current entry's candidates. The server remains final admission for every command.
"Declared widget state" gives each verb's `detail`.

`defer()` holds the widget's presentation during a live edit or a pointer or keyboard
rearrangement. Call it before the first local DOM mutation; it returns a one-shot
`resume`. Invoke `resume` only after `dispatch` has synchronously staged the semantic
result, or after cancellation has restored the prior local DOM; it renders the newest
reading. While a drag is held (`dragging`, `module-input.md`, "Pointer presses"), Leaf holds new readings
back without a `defer`.

`present(promise)` registers asynchronous visible preparation, such as a renderer
loading; the page does not read as ready until it settles.

### Tab-local working state

State the user arranges but does not record, such as which group they collapsed, stays
out of the log. `tabStore.get(key)` and `tabStore.set(key, value)` keep a string of it
for this page in this browser tab, and setting `null` removes it. An `x-initial`
producer reads the same store, so the first paint can draw that state (`module-authoring.md`, "First paint").

## Declared widget state

A registry-declared widget implements a total, idempotent `renderState(state)`. It
receives the state of every declared verb, keyed by verb name, including the initial
values an Undo returns to. Render the final composition and keep independent nested
widgets mounted; never recreate the owner to restore an initial state. The controller
ignores the renderer's return value. An optional recorded scalar attribute has a null
initial value and must be removed when that value returns.

- A widget-unit verb's state is `{action, value, detail}`. `action` is null for authored
  state; `value` is the typed record value, or the verb's name for a recordless verb
  that stands, and null means undecided; `detail` keeps generated-child labels and other
  declared event data.
- A per-part verb's state holds `units`, each unit's `{action, value, detail}` keyed by
  unit id. A recordless unit missing from `units` is undecided.
- A position verb's state also holds `value`, mapping each container id to the complete
  ordered ids it holds, and `ranks`, each listed unit's rank.

Record user state with `dispatch` ("The widget controller"), with `detail` matching the
effect's payload contract in [package-data.md, "User state"](package-data.md#user-state). For a
recorded body, attribute or scalar value, send `detail: {value}`. For a position, send
`detail: {unit, value, rank}`: the moved element's id, the destination container's id,
and `rankAt(state.<verb>, container, index, unit)`, the rank of a unit dropped at
`index` among the container's other units. A rank keeps a unit's placement whichever
other moves stand, until a version authors the container's units differently. A verb
with no record sends what its declared `detail` schema asks for.

A widget's `x-awaits.value` selects its typed answer from the state (`module-reading.md`, "Reading asks and
obligation queues"). Its class may declare `static answerWords(value, element)`, which
returns concise words for that answer in the On panel. `value` is the ask's typed
`answer.value`; `element` supplies authored markup such as option labels. Read nothing
the module renders; Leaf collapses the words' whitespace. A widget without this
formatter supplies no answer wording, and its typed answer stays available through
`readAsks()`.

## Data subscriptions and projections

The source declarations and producer workflow are in [package-data.md, "External or derived
data"](package-data.md#external-or-derived-data). A module subscribes through its own input
declaration:

```js
if (once(this)) watchData(this, "builds", (snapshot) => render(snapshot));
```

`watchData(element, input, callback)` throws for an input the element's entry does not
declare. It reads the source binding from the element's markup once, as it subscribes.
The callback receives `null` while the source has no readable value, otherwise a clone of
`{source, contract, revision, run, updated, value, origin}`. `revision` identifies the
value itself; `run` identifies its publication, including a rerun with the same value or
timestamp. `origin` is `{input, source, contract, revision}`, the declared input and the
source reading it came from, so an unchanged source keeps its origin when another source
changes. The callback runs at once and again whenever the source's contract,
publication or validity changes; it states the whole rendering and stays idempotent. An
incompatible contract or unreadable value delivers `null`, clearing the previous
rendering; the subscription stays and recovers when a readable value returns. `page
state` and `page check` report invalid values, and an incompatible subscriber reports
the contract it requires. Register once for the element; returns follow `module-authoring.md`,
"Connection lifetimes". The returned function ends the subscription for good. Its `refresh()`
repaints the last delivered snapshot, on the return when asked while the owner is away;
it neither delivers a pending source reading nor revives a retired subscription.

If the callback renders asynchronously, it returns that promise, so Leaf publishes the
source revision as ready only after the projection settles. A rejection is that
subscriber's page error, reported once, and does not hold the revision back.

A source whose contract declares `deferred` sends its rows without that field.
`loadDeferred(snapshot, key)` fetches one row's field for the `snapshot` the callback
received, and throws when the source's revision changed before or during the load.

### Projecting data

The renderer owns its nodes and their placement (`module-authoring.md`, "Retained nodes"). After placing them,
annotate their words with `projectData(root, datums, {snapshot})`. Commit visible words
and their snapshot labels in the same synchronous turn, before awaiting later resource
settlement; until replacement words are mounted, the previous words keep their previous
snapshot's provenance. The root is an id-bearing seat. Each datum is
`{node, key, label?, identity?, origin?}`, and its node must already stand under that
root, including inside a declared shadow stage. Leaf validates the coordinates and marks
readable data rather than authored prose; it never builds, moves or removes nodes. A
node kept as ordinary furniture but omitted from the next datum list loses its former
projection labels and provenance.

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

`key` is a non-empty string unique in the projection and opaque to Leaf. `label` is an
optional human coordinate for thread chrome. `identity`, when supplied, is a non-empty
string unique in the projection, naming the same subject across source replacements
independently of its rendering key. A comment follows that subject and keeps the quote
from the value the user saw. A reused identifier for a new subject needs a new
identity. Without one, source-backed keys stay exact only within the captured revision;
replacing the value marks their placement outdated. Derived projections omit `snapshot`
and keep their section and key identity.

A widget declaring `x-data` passes the delivery's `snapshot`, including `null` when no
current value exists. Leaf stamps the seat and every datum with that snapshot's source
and revision and uses `snapshot.origin` as their default provenance. A datum that knows
its exact JSON coordinate supplies `origin: {...snapshot.origin, path: [...]}`; path
segments are object keys or array indices. A formatted or parsed datum may name its
whole input. Derived records can name contributing widget seats as
`origin: {derived: [{widget: id}]}`. Explicit `origin: null` removes provenance. These
are construction inputs, not an inverse edit mapping; Leaf never infers them from
displayed words or datum keys.

### Time readings

A time reading made synchronously in a subscription callback (the controller's,
`watchData`'s, or a `watchProjection` paint's) or in a `readingPaint` draw subscribes
that paint to Leaf's shared clock, which repaints it only when a reading's result
changes; the clock
never redelivers unchanged data to keep a timestamp current. `ago(ts)` says how long ago
a server timestamp was, as the page words it everywhere: "just now" under 45 seconds,
then "2m ago", "2h ago" or "2d ago". `shortAgo(ts)` is the same reading for a tight seat
("now", "2h"). `quietSince(ts)` says whether working last heard at `ts` has gone
unheard past the server's working grace, the bound the page's own activity reads. For
another rounded reading, use `clockValue((now) => reading)`, whose `now` is the
calibrated server time in milliseconds.

For a paint outside these subscriptions, wrap it with `clocked(element, paint)` and call
the returned function where state changes. Its readings pause while the element is away
and tick again when it returns; the returned function's `stop()` takes it off the clock.
If a presenter schedules the painting, pass its synchronous claim as the third argument,
`clocked(element, paint, invalidate)`: a clock change calls `invalidate`, and the
scheduled pass calls the function `clocked` returned, capturing fresh readings. Until
that paint runs, the previous readings stay subscribed. Time read after an `await`
belongs in a separate synchronous `clocked` paint.

## Editing a bound file

`boundFile(binding)` returns the transport for a file explicitly granted to this page
with `leaf file bind`. Its `read()` returns `{label, text, revision, newline, bytes}`;
`save({revision, text})` checks that exact revision before writing and returns the
submitted snapshot. A stale save throws an error whose `current` holds the newer file.
Other errors carry a message and leave the caller's buffer alone. `text` uses LF line
endings; the host keeps the file's LF or CRLF form. `watch(callback)` calls back whenever
the page hears that the bound file may have changed on disk, including through the
widget's own save, and returns a function that stops it; read the file again then, and
its revision says whether it changed.

The `writable` property is false in captured documents and exports. The transport owns
page-relative routing; a widget never names a host path. The file stays external
filesystem state: editing it appends no Leaf action and takes no part in page Undo,
and CodeMirror owns editing history. Use the `file-editor` package's `lf-file-editor`
for this interface, and `lf-code` for a snapshot that should travel with the page.
