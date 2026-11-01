# Threads and annotations in a module

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Margin contributions

A widget puts its actions and statuses in the page's margin with
`registerContribution({key, target, source, read, activate})`. Leaf draws them beside
`target`, in its margin cluster and in Page Map, where the margin's keyboard routes and
`t` reach them, and inserts nothing into the page's content. `target` is an element, or
a function returning the one the actions currently sit beside. Set `source` to the
widget that owns them when the controls have to sit beside an ancestor that outlives
it. For example, inside a widget whose `save()` method does the work:

```js
import {
  contributionEntry,
  registerContribution,
  whileConnected,
} from "/runtime/widget-api.js";

setup() {
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

`read()` returns data, never controls: the actions available in the widget's current
state, built with `contributionEntry`. Call `update()` whenever that state changes, and
every surface redraws from the new entries. Each entry needs a `key`, a `label`, and one
of a `glyph` (text), an `action` (one of Leaf's actions, whose symbol it shows;
`module-reading.md`, "Icons") or an `icon` (a Leaf icon, for an entry that shows what it
holds rather than what it does). `behavior`, `tone`, `rank` and
`state` default to an ordinary primary action; `CONTRIBUTION_ENTRY_SCHEMA` lists their
values.

Pressing an entry calls `activate(activation, context)`, where an entry's `activation`
defaults to its key. An entry for one of the widget's declared commands instead sets
`scope` to its `commandScope` and `activation` to the command's id, and Leaf disables it
with the command and runs the command's own `run`. A command the widget adds for one of
these entries calls `this.actions.activate(key)`, so a key and a press do the same
thing.

`kind` says what the whole contribution is: `action` by default, or `change`, `comment`,
`on-me`, `activity` and the margin's other kinds. `read()` may also return `readings`,
items each with an `id` unique within the contribution and an optional `activate`,
which the registration's `activateReading(id)` calls.

A widget that shows margin entries inside its own content, as the feature gallery does,
draws its own control as an entry with
`presentContributionEntry(control, entry, {selected})`, and shows whether the agent is
working on it with `presentContributionReceipts(control, receipt, awaitsUser)`, where
`receipt` is a workflow's `{id, subject, stage, detail}` or `null`.

The returned registration's `hasCurrentLocation()` says whether the user's focus is
inside any control presenting that contribution, across shadow roots and presentation
surfaces. Its `contains(node)` answers the same ownership question for an arbitrary
node. Use the focus query when retaining a focused entry while updating its reading.

## Visual parts

A visual whose drawn parts carry ids, such as `commit:3f2a`, lets users comment on each
part. It declares the ids' prefixes in `x-visual.prefixes` (here `commit:`) and calls
`registerVisualParts(source, read, {reveal, label})` once. `read()` returns the parts
drawn now as `{id, element, label}`, each id a nonempty string with no whitespace.
`reveal(id)` shows a part when someone follows its thread, even if it is visible
already, so cancel work that would hide it. `label(id)` names a part in Threads without
changing the visual, or returns `null`. Call the returned `update()` after the parts or
their positions change.

## Threads

### Reading and opening Threads from a widget

`readThreads()` returns the `{phase, threads}` Leaf's Threads list reads, and a render
that calls it redraws when it changes. A thread the user just started is there at once;
only `phase === "ready"` means every saved thread is. `threadTurns(thread)` returns a
Thread's turns, and `threadSummary(thread)` its `topic`, its name in words, and its
`latest` activity.

Address a Thread by its `key`, which stays the same after the server admits it; its `id`
is the name obligations and workflows use. `root` is its opening message, `anchor` names
the `section` and `datum` it is attached to, and `attention.kind` is `"needs_user"` when
it waits on the user and `"waiting"` when it is with the agent. `resolved` is set while
it stands resolved. A message's `reactions` lists the reactions it takes and those in
force, and is `null` on a message that takes none. An agent's message carries `agent`,
the name it shows under.

`agentName()` returns the page's current agent name, or "the agent" when none is
supplied. Use it when a package attributes agent activity.

`threadInput(element)` returns the reply editor of the Thread containing that element,
or `null` outside one. `landInThread(editor, {target, line})` enters an existing reply
editor and records where Escape returns when the Thread has no own focus destination:
`target` is the package's return element and `line` is its accessible return label.
It returns whether it could land. Use `threadActions.open` below when starting from a
Thread key rather than an editor already present.

`threadActions` acts on Threads through Leaf's own path, showing the result at once:

```js
threadActions.create({ text, anchor, attempt });
threadActions.open(thread.key, { part: "thread" });
threadActions.reply(thread.key, text);
threadActions.resolve(thread.key);
threadActions.reopen(thread.key);
threadActions.setReaction(thread.key, agentMessage.key, token, true);
```

`open(key, {part, focus, travel, message})` takes the user to the Thread wherever a
margin mark would: the page's primary reader ("Owning the primary conversation
presentation"), which is the Leaf panel unless a package registers one. `part` is
`"thread"` for the card, `"reply"` for the reply editor, or `"message"` with
`message: message.key` for one message. `travel: false` keeps the page where it is, and
`focus: false` leaves focus alone. It resolves to the element it landed on, or `null` if
the Thread is gone or the user has done something else. To act on that element
afterwards, such as selecting the reply text, check it still has focus:

```js
const editor = await threadActions.open(thread.key, { part: "reply" });
if (editor?.matches(":focus") && editor.setSelectionRange) {
  editor.setSelectionRange(0, editor.value.length);
}
```

Don't test a `retainUserIntent` predicate taken before the call (`module-input.md`,
"Delayed work"): the route's own move to the editor turns it false.

`reply`, `resolve`, `reopen` and `setReaction` return `null` when the Thread doesn't
offer the action, and otherwise a promise of the admitted event, or of `null` if the
server refused. A reply needs text, and reopens a resolved Thread. `setReaction` takes
the state you want, not a toggle, so a stale control can't undo another change. `create`
takes `text`, optionally with `anchor`, `attempt`, `holds`, `about`, `drawing` and
`suggestion`; empty text needs a drawing. It returns `{key, delivery}` at once. A
package's own input keeps its draft as `module-input.md`, "Text entry and drafts",
describes.

### Starting a thread from a widget

A widget whose entry declares `x-thread-seat` appends the box where the user starts a
thread about it, built with `threadBox(this, hint)`. It returns `null` in Leaf's
interface or in quoted markup.

### Owning the primary conversation presentation

A package that provides the page's main conversation reader, such as a shelf of
conversations or a feed of turns, registers
`registerThreadPresentation(owner, {render, reveal})` in `whileConnected`; a page has at
most one. Leaf then opens threads there instead of in its floating panel, and widgets
inside the messages it draws live there.

`render(shownCollection, parts)` names outlets inside the widget: a whole conversation
with `parts.thread(thread.key, outlet)`, or its parts with
`parts.message(thread.key, message.key, outlet)` for each of its `threadTurns` and
`parts.reply(thread.key, outlet)`. `parts.transcript(thread.key, outlet)` draws all of
its turns as a whole conversation does, for a widget that draws the conversation's head
itself, in place of message parts. Leaf fills the outlets and keeps the rendering,
reactions, read tracking and reply draft; the package keeps layout, order, selection,
scroll and disclosure. The user's message editor opens in place of the message,
with its frame extending slightly beyond the message's edges, so a scroller holding message
parts keeps about 12px of padding beside them (the worked example's `.reader`).
`parts.transcript` also takes `{drawn}`. `drawn(answer)` runs once its transcript DOM
is placed, before asynchronous widget preparation finishes, so layout and scroll can
follow the words before the next frame. `answer` is null except when this draw answers
the user's last turn; then it is the read-only `{turn, reply}` message keys, with
`reply: null` while only work under way has arrived. A render abandoned before drawing
calls nothing. The handle's `update()` still waits for the widgets' preparation.

`parts.reply` takes `{hint, accessibleName, sent}`, where
`sent()` runs after a send instead of moving the user to the thread. The reply box
stands in a resolved thread too, and a reply there reopens it. The collection
holds back changes that would move what the user sees behind a notice, placed where
`parts.news(thread.key, outlet)` names or else at the end of the first part's head,
while `readThreads()` stays current for counts. A feed of single turns supplies Resolve
and Reopen through `threadActions`.

Await the handle's `update()` after a local layout change, or `update({release: true})`
to show held news for a deliberate change of view. If `render` throws or names an outlet
outside the widget, that update rejects, the threads go back to Leaf's floating panel,
and `primary` reads false until the next `update()` takes them back.

`reveal(key, request)` shows the requested part in the package's layout, or returns
`false` to leave the part to the thread's place on the page, such as its margin card.
Where nothing there shows it, Leaf asks again with `request.last` set, and a second
`false` leaves the thread unopened. `request` also carries `part`, `message`, `focus`,
`signal` and `current()`; Leaf handles focus, scrolling and arrival. The feature
gallery's `lf-conversation-workspace` is the worked example.

### Widget-local Thread placement

A widget that declares `"x-thread-surface": true` shows threads beside its own projected
data, as `lf-diff` does beside lines. Leaf calls its
`threadOutlets(targets, {signal, collection, onCommit})` whenever placement changes,
with the threads anchored exactly to its data and the open comment box. Return, in the
same order, an outlet for each target or `null`, or a promise of that array; an
asynchronous `threadOutlets` checks `signal` before changing the DOM. A target is
`{anchor, placement, thread}`, with the datum's element at `placement.datumElement` and
`thread` `null` for the comment box. Here `this.outletFor` is the widget's own method
that finds or makes the outlet beside a datum (`lf-diff`'s `threadOutletFor`):

```js
threadOutlets(targets, { onCommit }) {
  this.beginThreadSurface();
  const outlets = targets.map((target) => this.outletFor(target));
  onCommit(() => this.retireUnusedOutlets());
  return outlets;
}
```

Return `null` for data that is filtered out, collapsed or not loaded, and its thread
stays in the margin. A thread the agent starts on a visible datum also waits in the
margin until the user opens it. Call `threadSurface(this).update()` after a change that
only shows or hides data.

The widget creates, lays out and removes its outlets, and Leaf fills them. An outlet you
stop returning may still hold the comment box the user is typing in, so remove outlets
only in `onCommit`, which runs once this pass's placement takes effect, and keep
returned ones in the document while redrawing around them. A widget that must remove a
node holding outlets at another time, such as when its data goes, first calls
`releaseOutlets(node)`, before any `holdFocus`. If `threadOutlets` throws, Leaf returns
the widget's threads to the margin until the next pass.

`threadSurface(this).open(datum)` opens the comment box on one of the widget's data
items, in its outlet; Leaf keeps the draft and the sending.

`threadSurface` and `releaseOutlets` also load through `portable-api.js`. Without a
registered Leaf surface, there is nothing to update or release, and `open` returns
`false`.

### Page annotation presentation

On a page whose `body` has `data-annotations="page"`, one element may supply the outlets
for all of the page's threads with `placePageThreads(owner, render)`. Its `render` takes
the same targets and returns the same array as `threadOutlets`, for passages and visual
parts as well as data; a widget's own outlet still wins. Outlets stay inside the
element, and if `render` fails, presentation fails.

The same element can show obligations, updates, status and margin actions by registering
`consumeAnnotations(owner, render)`. `render` runs synchronously after the conversations
are placed, with the current inventory and a view:

- `view.items(entry)` returns the items the owner's visible controls don't already
  show, and `view.activate(item)` runs one. Key items by `contributionItemKey(item)`.
- `view.controls(entry)` returns the contribution's real controls. Place those nodes,
  not copies of their markup, so they keep their behavior. `view.controlKey(control)`
  and `view.controlRecord(control)` name and describe one.
- `view.arriving` is true while focus is on its way to an entry here; release held
  layout so its control can be reached.
- `view.place(entry, row)` ties a row to its source for commenting and Escape.

Both registrations throw on other pages, and return handles with `read()`, `update()`
and `unregister()`; register them in `whileConnected`. Keep rows keyed, and hold size
changes back with `HeldReading` (`module-scroll-and-motion.md`, "Holding the reader's
place") while updating surviving controls at once. An owner that scrolls inside its own
box registers it as a reading region. Whatever the owner doesn't show stays in Threads
and the On lists of Leaf's panel.
