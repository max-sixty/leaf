# Threads and annotations in a module

Read with [module-authoring.md](module-authoring.md).

## Margin contributions

A widget puts its actions and statuses in the page's margin with
`registerContribution({key, target, source, read, activate})`. Leaf draws them beside
`target`, in its margin cluster and in Page Map, where the margin's keyboard routes and
`t` reach them, and inserts nothing into the page's content. `target` is an element, or
a function returning the one the actions currently sit beside. Set `source` to the
widget that owns them when the controls have to sit beside an ancestor that outlives
it. A component registers from a Mount, which holds the registration while its node
stands. For example, in `lf-notes`, whose `save(element)` does the work and whose view
gives the Mount whether Save is disabled:

```js
import { registerContribution } from "/runtime/widget-api.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";

const OfferSave = Mount.make(
  "OfferSave",
  { args: { disabled: Schema.Boolean } },
  (node, args, changes) =>
    Effect.gen(function* () {
      const element = closestAcross(node, "lf-notes");
      let { disabled } = args;
      const actions = yield* Effect.acquireRelease(
        Effect.sync(() =>
          registerContribution({
            key: element.id,
            target: element,
            read: () => ({
              kind: "action",
              subject: element.getAttribute("aria-label"),
              entries: [{ key: "save", glyph: "✓", label: "Save", disabled }],
            }),
            activate: () => save(element),
          }),
        ),
        (actions) => Effect.sync(() => actions.unregister()),
      );
      yield* Stream.runForEach(changes, (next) =>
        Effect.sync(() => {
          disabled = next.disabled;
          actions.update();
        }),
      );
      return Component.noop;
    }),
);
```

`read()` returns data, never controls: the actions available in the widget's current
state, each a plain object. Call the registration's `update()` whenever that state
changes, and every surface redraws from the new entries. Each entry needs a `key`, a `label`, and one
of a `glyph` (text), an `action` (one of Leaf's actions, whose symbol it shows;
`module-reading.md`, "Icons") or an `icon` (a Leaf icon, for an entry that shows what it
holds rather than what it does). `behavior`, `tone`, `rank` and
`state` default to an ordinary primary action.

Pressing an entry calls `activate(activation, context)`, where an entry's `activation`
defaults to its key. An entry for one of the widget's declared commands instead sets
`scope` to the object that declares the command, the one the widget holds as
`lfCommands` (`module-input.md`, "Commands and keyboard routes"), and `activation` to
the command's id, and Leaf disables it with the command and runs the command's own
`run`, so the command's `run` is that entry's one route to the effect. A key the widget
adds for an entry with no `scope`, such as Save above, is a command whose `run` calls
`actions.activate(key)` on the registration, so the key and a press take that entry's
one route.

`kind` says what the whole contribution is: `action` by default, or `change`, `comment`,
`on-me`, `activity` and the margin's other kinds. `read()` may also return `readings`,
items each with an `id` unique within the contribution, the `text` the margin shows
for it, an optional `kind` from the same list, and an optional `activate`, which the
registration's `activateReading(id)` calls. A reading sets `represents: true` when the
widget's own entries answer its question, as a pending suggestion's Accept and Reject
do. Leaf then leaves out the "Waiting on me" it would draw at the same target.

A widget that shows margin entries inside its own content, as the feature gallery does,
draws its own control as an entry with
`presentContributionEntry(control, entry, {selected, unread, receipt, awaitsUser})`,
where `unread` draws the dot for agent words the user hasn't read beside the entry's
count, `receipt` shows whether the agent is working on it, and `awaitsUser` whether it
waits on the user. `receipt` is `null` or a workflow's
`{id, subject, state, reason, seen, detail}`. The control shows the agent at work while
`state` is `"running"`, and an update a turn has taken in while `state` is `"waiting"`
and `seen` is true.

The returned registration's `hasCurrentLocation()` says whether the user's focus is
inside any control presenting that contribution, across shadow roots and presentation
surfaces. Its `contains(node)` answers the same ownership question for an arbitrary
node. Use the focus query when retaining a focused entry while updating its reading.

## Visual parts

A visual whose drawn parts carry ids, such as `commit:3f2a`, lets users comment on each
part. It declares the ids' prefixes in `visual.prefixes` (here `commit:`) and marks
each part: each node in the visual's light DOM that carries `data-lf-part="<id>"` is the
part of that id, named by its `aria-label` or else by its words; a node inside another
visual standing in it is that visual's. Each id marks one node, each marked node needs
a name, and the `visual` declaration admits the id, a nonempty string with no
whitespace. A mark inside a shadow root is not read.

Where marks can't say it, the element states its parts as its `lfParts` property, an
object Leaf reads each time it needs the parts, which a component states with
`declare(node, {lfParts})` from a Mount (`module-widgets.md`, "`lf-layout`"), as
`lf-timeline` does. Its `read()` returns the parts drawn
now as `{id, element, label}`, in place of the marks, and may name an element in the
visual's shadow root. A part may also name `surface`, the descendant of its element
whose paint Leaf's marks follow, so a part that holds others, as a board's column
holds its cards, wears its marks on its own frame rather than around each card. An
SVG part, or the `surface` it names, wears its marks on its frame where it has one: the
first shape among its children, where that shape shows, isn't a line, and holds the whole
part. `reveal(id)` shows a part when someone follows its thread, even if it is
visible already, so cancel work that would hide it. `label(id)` names a part in
Threads, in its margin entry and in Page Map without changing the visual, or returns
`null`. Each member is optional.

Leaf reads the parts again each time it sets the widget's properties
(`module-widgets.md`). A visual whose parts or their positions change at another time
says `lf-layout` on its element (`module-widgets.md`, "`lf-layout`"): a
part's margin entry stands level with the part, and Leaf learns that a part moved
inside the visual only from it.

The user picks a part as they pick any element that isn't words, with Alt-click or in
Select mode (`page-authoring.md`, "Stable anchors"). Leaf finds the part under the
pointer by hit-testing, so paint each part across the area a user aims at: an SVG shape
with `fill: none` takes a press only along its stroke.

A visual with too many parts to list, such as a chart's points, also gives `find` and
`at`, and its `read()` may return none, since `read()` is what the target picker and a
screen reader's list offer. `find(id)` returns the part an id names in the current
state, drawing an element for it if it must, or `null` where the state holds none; Leaf
asks it for a comment's part rather than searching `read()`, and a part it doesn't find
stands on the whole visual, since the visual may draw it once it can. `at(node)` returns
the part a node of the visual stands for where no element `read()` returns holds it, or
`null`: Leaf asks it for a hit inside the visual, such as the pointer over a line
through the data, and asks it for the visual itself when focus on the visual names a
target, such as the point its arrow keys reached.

Leaf puts the user on a part's `element` when they travel to it or leave a comment box
on it. A visual whose parts are no places to stand, such as the marks round a chart's
points, also gives `focus` and takes focus for its parts itself. Leaf calls `focus(id)`
as it places focus on the visual for a part, and at no other time, and the visual
settles on the part, as a chart moves its reading to the point even where it holds
focus already. So leaving a comment box, or travel the user cancels, changes nothing
the visual shows.

## Threads

### Reading and opening Threads from a widget

`readThreads()` returns the `{phase, threads}` Leaf's Threads list reads, and a render
that calls it redraws when it changes. A thread the user just started is there at once;
only `phase === "ready"` means every saved thread is. A Thread's `turns` are the
messages a drawing of it shows, in order: its opening message and each later message
but the user's reactions, which a message's `reactions` holds. `nameOf(thread)` returns its name in words
(`module-reading.md`, "Naming").

Address a Thread by its `key`, which stays the same after the server admits it; its `id`
is the name obligations and workflows use. `root` is its opening message, and
`attention` is the obligation record that speaks for it, or `null` when nobody owes a
move there: its `next_actor` is `"user"` when the thread waits on the user and
`"agent"` when it is with the agent, and its `state` says where that stands. `resolved`
is set while it stands resolved. A message's `reactions` lists the reactions it takes
and those in force, and is `null` on a message that takes none. An agent's message
carries `agent`, the name it shows under.

A Thread's `anchor` says what it is about, and is `null` for a comment on the whole
page. It names a `section`, an element's id, and may say where inside that element with
a `datum`, a `visual` part or a `quote`, the words of a passage; a quote may stand
inside a datum. `prefix` and `suffix`, where the anchor has them, are the text before
and after the quote, which tell two copies of the same words apart.
[events.md](../../../src/leaf/events.md), "Anchors", defines every field.

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
threadActions.setReaction(thread.key, agentMessage.key, emoji, true);
```

`open(key, {part, focus, travel, message})` takes the user to the Thread wherever a
margin mark would: the page's primary reader ("Owning the primary conversation
presentation"), which is the Leaf panel unless a package registers one. `part` is
`"thread"` for the card, `"reply"` for the reply editor, or `"message"` with
`message: message.key` for one message; with none it lands as opening a thread does, in
the reply after a press and on the thread after a key. `travel: false` keeps the page where it is, and
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

### Owning the primary conversation presentation

A package that provides the page's main conversation reader, such as a shelf of
conversations or a feed of turns, registers
`registerThreadPresentation(owner, {render, reveal})` in `whileConnected`; a page has at
most one. Leaf then opens threads there instead of in its floating panel, and widgets
inside the messages it draws live there.

`render(shownCollection, parts)` names outlets inside the widget: a whole conversation
with `parts.thread(thread.key, outlet)`, or its parts with
`parts.message(thread.key, message.key, outlet)` for each of its `turns` and
`parts.reply(thread.key, outlet)`. Leaf fills the outlets and keeps the rendering,
reactions, read tracking and reply draft; the package keeps layout, order, selection,
scroll and disclosure. The user's message editor opens in place of the message,
with its frame extending slightly beyond the message's edges, so a scroller holding message
parts keeps about 12px of padding beside them (the worked example's `.reader`).

A widget that draws the conversation's head itself, as Leaf's floating panel does,
passes `parts.thread` a third argument, `{head, reply, quote, scroller, landing,
drawn}`, each part optional:

- `head: {news, controls, unread}` names places on the widget's head line. The notice
  of news the thread holds back stands in `news`, and Resolve, or Reopen, in `controls`;
  without them, both stand beside the first message's head. Next unread, offered where
  the thread's opening leaves a reply unread, stands in `unread`, and without that place
  nowhere.
- `reply: {outlet, options}` names where the reply box stands, at the thread's end
  without `outlet`, with the options `parts.reply` takes, except that `hint` is called
  with `{resolved, attention}`: the thread as it is drawn, held news included, so the
  box's words agree with Resolve and the notice. `attention` is whose `turn` the thread
  is (`"user"` or `"agent"`) and its `state`, with the `word` Threads says it in, or
  null where it waits on nothing, as once it is resolved.
- `quote: true` quotes the words the thread is about over its messages, for a widget
  that stands apart from them. Without it, the thread quotes them only once the page
  no longer shows them as quoted, as after a revision rewrote them.
- `scroller: (transcript) => box` names the box that scrolls the thread's messages,
  which may be the thread's own `transcript`. An answer the user waits for that arrives
  past its foot then says New reply there.
- `landing(resolved)` is called as the user presses Resolve or Reopen, with whether
  the thread stood resolved before the press. It returns a step Leaf runs once the
  settlement shows, which returns whether it moved the user, or `null` to leave the
  user to the thread: Reopen then puts the caret in the reply box, wherever it stands.
  With a landing, taking the settlement back opens the thread in this widget again.
- `drawn()` runs once the thread's DOM is placed, before asynchronous widget
  preparation finishes, so layout and scroll can follow the words before the next
  frame. A render abandoned before drawing calls nothing. The handle's `update()` still
  waits for the widgets' preparation.

Each place, as an outlet, stands inside the widget, and may stand in its shadow tree.
A whole thread, as a reply part does, takes the reply being written in it that no
other view holds, so the user goes on writing there.

`parts.reply` takes `{hint, accessibleName, sent}`. A send leaves the user on the
thread, and `sent()` then runs in place of Leaf's landing of the new turn. The reply box
stands in a resolved thread too, and a reply there reopens it. The collection
holds back changes that would move what the user sees behind a notice, which a whole
conversation stands as a card does, or where its `head` names, and message parts at
the end of the first part's head, while `readThreads()` stays current for counts. A
feed of single turns supplies Resolve and Reopen through `threadActions`.

Await the handle's `update()` after a local layout change, or `update({release: true})`
to show held news for a deliberate change of view. If `render` throws or names an outlet
or a place outside the widget, that update rejects, the threads go back to Leaf's floating panel,
and `primary` reads false until the next `update()` takes them back.

`reveal(key, request)` shows the requested part in the package's layout, or returns
`false` to leave the part to the thread's place on the page, such as its margin card.
Where nothing there shows it, Leaf asks again with `request.last` set, and a second
`false` leaves the thread unopened. Where the user asked for the thread's place on the
page, as Leaf's Show on page does, and the page now shows the thread, Leaf asks with
`request.page` set, and a reader that draws the thread elsewhere returns `false` to
put its view away. `request` also carries `part`, `message`, `focus`, `signal` and
`current()`; Leaf handles focus, scrolling and arrival.

### Widget-local Thread placement

A widget whose element has a `threadOutlets` method, which a component declares
(`module-widgets.md`), shows threads inside itself: beside
its own projected data, as `lf-diff` does beside lines, or about the widget as a whole,
as a task in `examples/command-hub.page/` does at its foot. The method is the
declaration, and the registry says nothing. Leaf calls
`threadOutlets(targets, {signal, collection, onCommit})` whenever placement changes,
with the threads anchored exactly to the widget or to its data, and the open comment
box. Return, in the same order, an outlet for each target or `null`, or a promise of
that array; an asynchronous `threadOutlets` checks `signal` before changing the DOM. A
target is `{anchor, placement, thread}`, where `thread` is the Thread, or `null` for the
comment box. A target on a datum names it in `anchor.datum`, with its element at
`placement.datumElement`; a passage running across several data names the last there and
the first in `anchor.from`. A target with no `anchor.datum` is the widget itself: a
thread anchored to its element and nothing inside it. A thread on a passage or a visual
part of the widget is never a target, and stays in the margin. Here `outletFor` is
the widget's own function that finds or makes the outlet beside a datum (`lf-diff`'s
`threadOutletFor`):

```js
declare(node, {
  threadOutlets: (targets, { onCommit }) => {
    beginThreadSurface();
    const outlets = targets.map((target) => outletFor(target));
    onCommit(() => retireUnusedOutlets());
    return outlets;
  },
});
```

Return `null` for data that is filtered out, collapsed or not loaded, and its thread
stays in the margin; a widget that seats only its data returns `null` for itself too.
After a change that only shows or hides data, as a fold or a filter does, say an
`lf-layout` event on the widget (`module-widgets.md`, "`lf-layout`"), and Leaf
calls `threadOutlets` again. A change that also resizes the
widget still needs the event: after a resize alone, Leaf measures the widget again and
does not call `threadOutlets`.

Leaf asks for the method on each placement pass, and registers or retires the widget
when `declare` says `lf-layout`, so outlets that arrive with a later draw are used.

A thread names its widget by `id`, so a widget that shows threads needs an `id` on
each instance and should require it in its schema: Leaf reports an instance without
one as a failure of that widget and registers no surface for it.

The widget creates, lays out and removes its outlets, and Leaf fills them, drawing each
thread as a card with its own frame that fills the outlet and stands on the ground the
widget declares where it paints one (`--lf-ground`). So an outlet's box is the cards'
shape, and the outlet draws no frame of its own. A card fills its outlet at any width.
`--lf-thread-card-min` is the narrowest a card stands beside the page, and an outlet
that insets its cards reads it to leave them that room. Leaf folds an outlet's resolved
threads into a disclosure of class `lf-resolved-threads`, and the widget may size the
disclosure's summary, of class `lf-resolved-summary`, as it sizes its own rows. An
outlet you stop returning may still hold the comment box the user is typing in, so
remove outlets only in `onCommit`, which runs once this pass's placement takes effect,
and keep returned ones in the document while redrawing around them. A widget that must
remove a node holding outlets at another time, such as when its data goes, first calls
`threadSurface(element).release(node)`, before any `holdFocus`, and the comment box
leaves the widget's outlets under `node` with the user still writing in it. If
`threadOutlets` throws, Leaf returns the widget's threads to the margin until the next
pass.

`threadSurface(element).open` is the reactive opener for the comment box on the widget
or one of its data items, or `null` while no surface is registered, as in an export,
which holds no thread and can send none. A component reads it in `options.inputs`, which
follows its registration, and offers comment controls only while it exists; call it with
the datum, or with the widget itself, to open the box in the outlet `threadOutlets`
returns for it. Leaf keeps the draft and the sending. Registration can follow the
widget's first drawing, and departure retires the opener until the widget returns.

The comment box standing in an outlet the widget returns for itself can offer a second
send. Set the outlet's `lfHold` to its words, such as `"Send & pause"` (`declare` sets
it where the widget's own element is the outlet, and the view's `.prop("lfHold", …)` on
an outlet it draws), and the box
shows a button under those words beside Send, which Tab reaches after Send. Its comment
carries `holds`, naming the widget, so the widget is held while that thread is open,
and resolving the thread releases it.

`threadSurface` also loads through `portable-api.js`. Without a registered Leaf
surface, there is nothing to release, and `open` is `null`.

### Page annotation presentation

On a page whose `body` has `data-annotations="page"`, one element may supply the outlets
for the page's threads with `placePageThreads(owner, render)`. Its `render` takes the
same arguments and returns the same array as `threadOutlets`, for passages and visual
parts as well as data; a widget's own outlet still wins. Outlets stay inside the
element, and if `render` fails, presentation fails.

The targets are the open comment box and the threads whose subject Leaf finds on the
page, resolved ones among them. A thread Leaf has nowhere to place, such as a comment on
the whole page, is not a target, and neither is one whose subject Leaf can't find on
the page. A target's `anchor` says what it is about, as a Thread's does ("Reading and
opening Threads from a widget"), and its `placement` says where it stands.
`placement.place` is the element it stands by, such as the block that holds a passage.
Only a target on a passage has `placement.ranges`, an array of live `Range`s in reading
order, one over its words in each text node they run through, to measure where the
words are drawn.

The registration throws on other pages, and returns a handle with `read()`, `update()`,
`unregister()`, `open(node)` and `reveal(key)`; register it in `whileConnected`.
`read()` returns what `readThreads()` returns. `update()` asks for `render` again and
returns nothing to await, so do what must follow a placement in the `onCommit` its
`render` is handed, which runs once Leaf has filled the outlets. `open(node)` opens the
comment box on the visual part or datum that holds `node`, or else on the nearest
element with an `id`, `node` itself included, and throws where there is none.
`reveal(key)` takes the user to that Thread, in the outlet that holds it or else in
Leaf's panel.

Keep outlets keyed by thread, and hold size changes back with `HeldReading`
(`module-scroll-and-motion.md`, "Holding the reader's place"). An owner that scrolls
inside its own box registers it as a reading region. Whatever the owner doesn't show
stays in Threads and the On lists of Leaf's panel.
