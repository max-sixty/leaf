# Threads and annotations in a module

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers margin contributions, the visual parts a comment can target, and reading, starting, and rendering Threads from a widget.

## Margin contributions

`registerContribution({key, target, source, read, activate})` adds a widget's actions and
statuses to the page's shared margin. `read()` returns the contribution's complete current
reading, including immutable `contributionEntry({...})` records, and never controls. Leaf
renders those records independently in the target's margin cluster and in Page Map.
`target` is an element, or a function returning the element that currently anchors the
action. `source` defaults to the target and may separately name the semantic owner where
the presentation has to move to a surviving ancestor.

The `kind` in what `read()` returns names what the contribution is, as one of the margin's
reading kinds (`action`, `change`, `comment`, `ask`, `activity`, …; `action` where it
declares none): where a pin with a primary and one more control finds no room for both, it
folds to one control wearing that kind's face and name, which opens to them. Items in its
`readings` have
nonempty `id` strings, unique within that contribution; other contributions may reuse an
id. Leaf keeps each projected control by the contribution key and entry key while its
native kind stays compatible. Actions and disclosures are buttons and statuses are spans,
so crossing between them replaces the control.

An entry needs `key`, `label`, and exactly one of `glyph` (text) or `icon` (a Leaf icon
name). `kind` belongs to the whole reading, never an entry. Entries default to
`behavior: "action"`, `tone: "neutral"`, `rank: "primary"` and `state: "idle"`, and
`activation` defaults to their key; `CONTRIBUTION_ENTRY_SCHEMA` gives the accepted values of
those four fields. An entry that presents a declared command sets `scope` to its
`commandScope` capability and `activation` to that command's id: Leaf derives the entry's
disabled state from the command's availability and invokes the same `run(binding,
context)` as its keyboard route, so keep its semantic action in `run`. Other actions use
`activate(token, context)`, which a contribution with any such entry must supply. The
context carries the projected origin, surface, input kind, current entry, and a `focus`
capability, which moves to the current surface only where activation owned keyboard focus
and otherwise returns false.

The returned registration exposes `entry`, `control`, `contains`, `activate`,
`activateReading`, `focus`, `update` and `unregister`. `update()` replaces the whole reading
and may synchronously present it or focus a surviving key. Auxiliary reading activation
callbacks stay with the live registration; projected readings contain data, and
`activateReading(id)` invokes the current one. Keep text fields, history and other
mechanical editing state in the widget, and publish only action and status records, with
explicit `element` or `entries` relations where a disclosure owns another surface or entry.
For example, inside a widget whose own `save()` method owns the effect:

```js
import {
  contributionEntry,
  once,
  registerContribution,
  whileConnected,
} from "/runtime/widget-api.js";

connectedCallback() {
  if (!once(this)) return;
  whileConnected(this, () => {
    this.actions = registerContribution({
      key: this.id,
      target: this,
      read: () => ({
        kind: "action",
        subject: this.getAttribute("aria-label"),
        entries: [contributionEntry({
          key: "save", glyph: "✓", label: "Save", disabled: this.disabled,
        })],
      }),
      activate: () => this.save(),
    });
    return () => this.actions.unregister();
  });
}

syncActions() { this.actions.update(); }
```

Call `syncActions()` when the widget's state changes, and return the actions available in
that state from `read()`; every surface receives the same current records. Leaf's margin
controls and Page Map provide keyboard routes. A widget adding its own commands calls
`actions.activate(key)` from those rows, so keyboard and pointer input reach the same
effect.

Leaf places a contribution in its target's margin cluster, beside the page or pinned over
it, and inserts nothing into the page's content, so its controls come after the page's
content in the tab order; the margin's keyboard routes, `t` and Page Map reach them from
the target. A package never places or sizes these controls itself.

A widget that shows margin entries inside its own content, as the feature gallery's
gallery of them does, paints a control it owns as one with
`presentContributionEntry(control, entry, {selected})`, where `entry` is a
`contributionEntry` record. `presentContributionReceipts(control, receipt, awaitsUser)`
paints the control's turn: the agent's work on it, from a workflow's
`{id, subject, stage, detail}` or `null`, and whether the user owes it an answer.

## Visual parts

A visual with generated part ids declares the accepted `x-visual.prefixes` and calls
`registerVisualParts(source, read, {reveal, label})` once; a second registration for the
same source throws. `read()` returns the parts currently drawn as `{id, element, label}`
records. `reveal(id)` settles the visual on the requested part when someone follows its
thread, even if the part is already visible, so cancel any pending work that would retire
it before returning. `label(id)` names a part in Threads without changing the visual's
state, and returns `null` for an unknown id. The returned `update()` says the parts or
their geometry changed; call it after any such rendering change.

## Threads

### Reading and opening Threads from a widget

`readThreads()` returns the same immutable `{phase, threads}` collection the Threads panel
reads; a paint that reads it follows it (`module-reading.md`, "Page readings").
`threads` holds conversations, including local sends while `phase` is `waiting` or
`offline`; only `ready` means the saved inventory is complete. A bare reaction without
a spoken turn is not a listed Thread. Each widget keeps its own search, filter and order
state and derives its displayed rows from the collection. `threadTurns(thread)` selects a Thread's displayed turns, and
`threadSummary(thread)` gives its `topic` and `latest` activity. An agent-written message
or closing event carries `agent`, the name it is shown under.

A Thread's `key` survives admission of a pending gesture, so use it, not `id`, to address
the Thread; message keys survive admission too. Its `id` is the name asks and workflows
give it; its `root` is its opening message, which a reply or settlement names as its
`parent`; and its `anchor` names the `section` (the widget's id) and `datum` it rests on.
`attention.kind === "needs_user"` marks a Thread waiting on the user, including recovery
after a failed response, and `"waiting"` one that is with the agent. Every Thread carries
`offers: {open, reply, resolve, reopen}` for current command availability. Reply is
admissible on a resolved Thread and reopens it. Each message's `reactions` is `null` or its
current vocabulary and `choices`, including labels, glyphs and reactions in force.

`threadActions` adds a package's own controls over the current reading and Leaf's
optimistic event path:

```js
threadActions.create({text, anchor, attempt});
threadActions.open(thread.key, {part: "thread"});
threadActions.reply(thread.key, text);
threadActions.resolve(thread.key);
threadActions.reopen(thread.key);
threadActions.setReaction(thread.key, agentMessage.key, token, true);
```

`threadActions.open(key, {part, focus, travel, message})` takes the user to the Thread in
the nearest reader, the same choice a mark and `t` make: the page's primary reader where
one is registered ("Owning the primary conversation presentation"), else the open Threads
panel, else inline where the page shows it, beside its passage or widget, else Threads.
`part: "thread"` lands on the card
or summary; `part: "reply"` reveals its reply editor; `part: "message"` asks for the reader
that renders native authored message content, the registered primary reader and then
Threads; `message: message.key` opens one message. Omitting `part` follows the surface's
ordinary route: a compact passage card starts at the card, and a widget conversation or
Threads at its reply. A focused jump that moves the page records a return place for Back;
`travel: false` keeps the page in place and records none. `focus` defaults to true, and
`focus: false` reveals the part without taking focus. The call resolves to the actual
destination after reveal and placement, or `null` when the Thread is unavailable or newer
input has superseded the move. The widget need not render or own the conversation to offer
this route.

Leaf keeps the original gesture's intent inside this route, and the returned
destination, while it still holds focus, is the capability for a continuation. A
predicate captured on the button before the call would reject the route's own move to
that editor:

```js
const editor = await threadActions.open(thread.key, {part: "reply"});
if (editor?.matches(":focus") && editor.setSelectionRange) {
  editor.setSelectionRange(0, editor.value.length);
}
```

`reply`, `resolve`, `reopen` and `setReaction` return `null` when the current reading does
not offer that action, otherwise a promise resolving to the admitted event, or `null` if
admission refuses it. The action changes `readThreads()` at once; the server stays final. A
reply needs non-empty text. `setReaction` names the desired state, so a stale
control cannot invert a concurrent change: `false` withdraws a reaction in force, and the
token must be in the current layer's vocabulary on an addressable agent message.
`create` accepts `text`, an optional `anchor`, `attempt`, `holds`, `about`, `drawing` and
`suggestion`; empty text needs a drawing. It returns `{key, delivery}` synchronously, where
`key` is its minted or supplied attempt and `delivery` is the admission promise, and in a
reading its pending Thread appears at once, including while saved history is loading.
Creation needs no Thread reading; its key selects the local Thread immediately. Leaf's
reply editors keep one durable draft per Thread, and a package's own input keeps its own (`module-input.md`, "Text entry and drafts").

### Starting a thread from a widget

A widget whose entry declares `x-thread-seat` builds the box where the user starts a thread
about it with `threadBox(this, hint)`, where `hint` labels the box, and appends the element
it returns. It returns `null` for an element in Leaf's interface or in quoted markup, and
throws for one the declaration's `when` does not select or one with no id.

### Rendering Threads in a widget

`mountThreadViews(owner, render)` lets a package supply containers for Leaf's own
conversation view, for a Thread list or dashboard. It returns a handle with `update()` and
`unregister()`, and throws for a second registration on the same element. The callback
receives the `readThreads()` collection on its first presentation and on later
publications, and a second argument, `surfaces`: `surfaces.thread(thread.key, outlet)` shows
that conversation in an element inside the widget. Each widget chooses its own Threads,
outlets, filters and order, and may render each Thread once per callback. Several widgets
may render the same Thread; these views are mirrors and leave the Thread at its page or
margin position. Leaf renders the messages, reply editor, reactions, settlement controls
and receipts, and an authored message's interactive widgets open in the primary reader or
the Threads panel.

```js
this.threads = mountThreadViews(this, (collection, surfaces) => {
  for (const thread of collection.threads) {
    const outlet = this.outletFor(thread.key);
    if (outlet) surfaces.thread(thread.key, outlet);
  }
});
```

The widget owns each outlet's creation and layout, and Leaf owns its children; every
outlet stays inside its owner. A returned promise delays that widget's repaint without
holding up Leaf's own surfaces. `surfaces.signal` aborts when a newer render supersedes this
one or the consumer unregisters, so an asynchronous callback checks it before changing its
UI. The handle's `update()` requests a new render after a local layout change. Register in
`whileConnected` and call `unregister()` from its cleanup.

### Owning the primary conversation presentation

`registerThreadPresentation(owner, {render, reveal})` selects one primary package reader per
page, for a package that supplies the page's conversation reader, such as a shelf of
conversations or a feed of individual turns. Interactive message widgets then have one
native instance, in this reader or in the fallback Threads panel. Leaf's floating panel
draws page threads with its own reader until a package registers one, and then opens them
in the package's. `mountThreadViews` stays useful for optional mirrors of it.

`render(shownCollection, parts)` nominates connected elements inside the owner as outlets.
Its collection holds back updates that would move visible content, and Leaf shows a notice
that releases them; `readThreads()` stays the current reading for counts and action
availability.

```js
parts.thread(thread.key, conversationOutlet);
// Or nominate individual parts of that Thread:
parts.message(thread.key, message.key, messageOutlet);
parts.reply(thread.key, replyOutlet);
```

A pass can nominate a whole conversation or its individual parts, each once, and several
parts can share an outlet. A shadow outlet displays the parts through native slots, while
their nodes stay in the document. Leaf keeps the generated nodes, message rendering,
reactions, read tracking and the shared reply draft; a nominated message of the user's own
offers its rewrite in place, and a nominated reply box opens the latest of those on ↑, as a
whole conversation does. `parts.reply` takes optional `{hint, accessibleName, sent}`: what
the empty box reads and is named, each a string or a function read as it paints, and
`sent()`, called after a send in place of standing the user on the thread, for a box that
stays for the next turn. The package keeps layout, ordering, selection, scroll and
disclosure. A returned promise delays the presentation; check `parts.signal` before
asynchronous layout changes, since a newer pass or `unregister` aborts it.

The handle supplies `update()` and `unregister()`. Await `update()` after local layout
changes; ordinary updates keep held news, and `update({release: true})` shows the current
reading for a deliberate view change. `reveal(key, request)` selects and reveals the part in
the package's layout, returning its asynchronous layout work where needed, or `false` to use
the Threads panel. The request carries `part` (`message`, `thread`, `reply`, or null for the
surface default), `message` (the addressed message key, or null), boolean `focus`,
`signal`, and `current()`; a message can be materialized without taking focus.
Asynchronous work checks cancellation before changing layout. Leaf then owns focus,
scrolling, first-unread navigation and ask arrival. Whole conversations include
settlement controls, and a feed of fragments supplies Resolve and Reopen through
`threadActions`. Register in `whileConnected` and call `unregister()` from its cleanup. The
feature gallery's `lf-conversation-workspace` switches Conversation, Shelf and Feed with
these APIs.

### Widget-local Thread placement

A widget declares `"x-thread-surface": true` to place Thread UI beside its own projected
data. Leaf registers each instance once its module has upgraded it and retires it when it
leaves the page, so the module neither registers nor unregisters. On each reconciliation
pass Leaf calls the element's own `threadOutlets(targets, {signal, collection, onCommit})`
with one ordered batch of the widget's targets; return an array of matching outlet elements
or `null`, in the same order, or a promise of that array. Each target supplies
`{anchor, placement, thread}`: `placement.datumElement` is the exact rendered datum, and
`thread` is its current Thread or `null` for the active composer. Several targets may share
one outlet. Here `this.outletFor` stands for the widget's own method, which finds or creates
the outlet beside the datum (`lf-diff`'s `threadOutletFor` is the worked example):

```js
threadOutlets(targets, { onCommit }) {
  this.beginThreadSurface();
  const outlets = targets.map((target) => this.outletFor(target));
  onCommit(() => this.retireUnusedOutlets());
  return outlets;
}
```

The batch holds only exact datums belonging to the widget, in current Thread order, then
its active composer where that resolves exactly; the composer may precede any Thread at its
datum. It leaves out a thread the agent starts at an on-screen datum where the widget draws
no thread yet, since opening the outlet would move what the user is reading: that thread
waits in the margin until the user presses its marker, adds a turn of their own, or
scrolls the datum out of the window. Return `null` for data that is filtered, collapsed or
not yet hydrated; the thread then falls back to the margin and lazy widgets stay lazy.
Deliberate thread travel may reveal the datum through `lfRevealDatum`, and the next pass
calls `threadOutlets` again. `threadSurface(this).update()` asks for a pass after a
layout-only visibility change.

The second argument's `signal` aborts when a newer pass supersedes the preparation or the
widget leaves; `collection` is the complete immutable Thread collection, for keeping a
layout allocation; and `onCommit(run)` registers work for when this batch's placement
commits, which a cancelled preparation never reaches. Outlets returned after cancellation
claim nothing. The widget owns outlet creation, removal and layout, and Leaf owns the
outlet's children. An outlet the widget stops returning may still hold the composer the
user is typing in until Leaf moves it at commit, so remove such an outlet only from
`onCommit`, and keep every returned outlet in the document while the widget redraws the
data around it; moving one with `move` keeps the user in it. A widget that removes a node
holding outlets outside `onCommit`, because its data went (a file dropped, a source
cleared, a part or the whole widget replaced by `failSoft`'s box), first calls
`releaseOutlets(node)`, ahead of any `holdFocus` around the removal: Leaf's composer leaves
every outlet under `node` at once, and the user stays in it. Outlets must stay inside their
widget; disconnected outlets claim no threads.

Leaf renders the messages, replies, reactions, settlement controls and receipts into each
outlet. A thread the widget places does not also appear in the margin; the Threads panel
stays the complete index. If `threadOutlets` throws, Leaf reports a page error, clears
that widget's views and returns its threads to the margin; the next pass calls it again.

`threadSurface(this).open(datum)` opens the ordinary anchored draft at one projected
element the widget owns, and seats the response bar in the widget's outlet when the datum
still resolves exactly. Before Leaf has registered the widget, or once it has left the page, `update()`
does nothing and `open` returns `false`. Escape from that draft returns focus to the datum
element when it can take focus, and otherwise to the page. Widgets receive no draft,
submission or event APIs.

### Page annotation presentation

With `data-annotations="page"` on `body`, one connected element may register
`placePageThreads(owner, render)` to nominate page-owned conversation outlets; both
registrations in this section throw on a page without that attribute, and a second
registration throws. Its callback receives the same target batch and
`{signal, collection, onCommit}` as `threadOutlets`, and returns the same matching outlet
array. Page targets include exact passages and visual details as well as projected data;
`collection` keeps a row's allocation while its live target is absent. Targets express
candidacy: widget-local outlets that survive take priority, and a held widget arrival
stays with its notice until the user opens it. A target may stand anywhere in the
document, but its outlet stays inside the registered owner. A failure of this callback
fails presentation rather than showing an empty view.

The same owner can register `consumeAnnotations(owner, render)` for asks, updates, status
and contributed actions. It receives the current immutable inventory after the
conversations commit, and a view with these capabilities:

- `view.items(entry)` gives generated items not already shown by an owner's visible native
  contribution controls. `view.activate(item)` uses the current action; a view never sends
  an event itself. Key items by `contributionItemKey(item)`, since each contribution owns
  its reading ids.
- `view.controls(entry)` returns the native contribution controls, in order. Seat those
  actual nodes, whose registration owns activation, command scopes, disabled state and
  focus, and copy no markup. `view.controlKey(control)` names a control by its contribution
  and entry key, and `view.controlRecord(control)` reads its immutable contribution entry,
  including its owner.
- `view.arriving` says a contribution focus is arriving at this view; release held layout
  before seating that reading, so its control is reachable.
- `view.place(entry, row)` ties a row to its current source for commenting, standing and
  Escape, and `view.target(entry)` reads that exact target.

Annotation paint is synchronous and joins the conversation presentation. `controls` and
`place` accept only entries in that paint's current reading; holding layout never
authorizes old actions. Both handles provide `read()`, `update()` and `unregister()`;
register in `whileConnected` and unregister from its cleanup. Keep rows keyed, and hold
visible size changes with `HeldReading` (`module-scroll-and-motion.md`, "Holding the reader's place"): hold only layout
identities and allocations, update surviving records and controls at once, and leave
retired slots their space with no interactive descendants. An owner that scrolls inside a
box of its own is a reading region: a page bounds it with `data-bound`, which registers it,
and a widget whose theme makes it scroll calls `registerReadingRegion`. At narrow widths
the owner stays where touch and the keyboard reach it. Omitting either consumer keeps the
core Threads and On routes.
