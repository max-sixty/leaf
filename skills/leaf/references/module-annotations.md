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
`state` default to an ordinary primary action.

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
`latest` activity. The summary also holds what a mark standing for the thread says, as
Leaf's margin says it. `line` is `{text, voice}` or `null`: whose turn it is ("Your
turn"), what it holds unread ("2 unread"), or where the agent's work on it stands
("Queued for Claude", "On it"). `voice` is who says the word, `agent` or `leaf`; a
`span` carrying it as `data-lf-voice` wears that speaker's face. `progress` is
`"picked_up"` once the user's update has been delivered into the agent's turn,
`"working"` while the agent is at work on it, and otherwise `null`. `unread` counts the
agent's messages the user hasn't read, which a mark shows whatever its line says.

Address a Thread by its `key`, which stays the same after the server admits it; its `id`
is the name obligations and workflows use. `root` is its opening message, and
`attention.kind` is `"needs_user"` when it waits on the user and `"waiting"` when it is
with the agent. `resolved` is set while it stands resolved.

`anchor` says what the thread is about, and is `null` for a comment on the whole page.
It names a `section`, an element's id, and within it a `datum`, a row of projected data,
a `visual`, a part of a picture, or a `quote`, a passage of its words, with the words
before and after it as `prefix` and `suffix` where they tell two copies of the passage
apart. `detached: true` marks a quote the page can no longer place.
[events.md](../../../src/leaf/events.md), "Anchors", owns these fields. Don't search the
page for a quote: Leaf resolves every anchor by one rule, and hands the result to
whoever places threads, as `placement` ("Page annotation presentation"). A message's `reactions` lists the reactions it takes and those in
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
`parts.message(thread.key, message.key, outlet)` for each of its `threadTurns` and
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
  box's words agree with Resolve and the notice. `attention` is what the thread waits
  on, with the `word` Threads says it in, or null where it waits on nothing, as once
  it is resolved.
- `quote: true` quotes the words the thread is about over its messages.
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

`parts.reply` takes `{hint, accessibleName, sent}`, where
`sent()` runs after a send instead of moving the user to the thread. The reply box
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
`false` leaves the thread unopened. `request` also carries `part`, `message`, `focus`,
`signal` and `current()`; Leaf handles focus, scrolling and arrival. The feature
gallery's `lf-conversation-workspace` is the worked example.

### Widget-local Thread placement

A widget whose element has a `threadOutlets` method shows threads inside itself: beside
its own projected data, as `lf-diff` does beside lines, or about the widget as a whole,
as a task in `examples/command-hub.page/` does at its foot. The method is the
declaration, and the registry says nothing. Leaf calls
`threadOutlets(targets, {signal, collection, onCommit})` whenever placement changes,
with the threads anchored exactly to the widget or to its data, and the open comment
box. Return, in the same order, an outlet for each target or `null`, or a promise of
that array; an asynchronous `threadOutlets` checks `signal` before changing the DOM. A
target is `{anchor, placement, thread}`, with `thread` `null` for the comment box. A
target on a datum names it in `anchor.datum`, with its element at
`placement.datumElement`. A target with no `anchor.datum` is the widget itself: a
thread anchored to its element and nothing inside it. A thread on a passage or a visual
part of the widget is never a target, and stays in the margin. Here `this.outletFor` is
the widget's own method that finds or makes the outlet beside a datum (`lf-diff`'s
`threadOutletFor`):

```js
threadOutlets(targets, { onCommit }) {
  this.beginThreadSurface();
  const outlets = targets.map((target) => this.outletFor(target));
  onCommit(() => this.retireUnusedOutlets());
  return outlets;
}
```

Return `null` for data that is filtered out, collapsed or not loaded, and its thread
stays in the margin; a widget that seats only its data returns `null` for itself too.
Call `threadSurface(this).update()` after a change that only shows or hides data.

A thread names its widget by `id`, so a widget that shows threads needs an `id` on
each instance and should require it in its schema: Leaf reports an instance without
one as a failure of that widget and registers no surface for it.

The widget creates, lays out and removes its outlets, and Leaf fills them. An outlet you
stop returning may still hold the comment box the user is typing in, so remove outlets
only in `onCommit`, which runs once this pass's placement takes effect, and keep
returned ones in the document while redrawing around them. A widget that must remove a
node holding outlets at another time, such as when its data goes, first calls
`releaseOutlets(node)`, before any `holdFocus`. If `threadOutlets` throws, Leaf returns
the widget's threads to the margin until the next pass.

`threadSurface(this).open` is the reactive opener for the comment box on the widget or
one of its data items, or `null` while no surface is registered, as in an export, which
holds no thread and can send none. Read it while rendering and offer comment controls
only when it exists; call it with the datum, or with the widget itself, to open the box
in the outlet `threadOutlets` returns for it. Leaf keeps the draft and the sending.
Registration can follow the widget's first drawing, and departure retires the opener
until the widget returns.

The comment box standing in an outlet the widget returns for itself can offer a second
send. Set the outlet's `lfHold` to its words, such as `"Send & pause"`, and the box
shows a button under those words beside Send, which Tab reaches after Send. Its comment
carries `holds`, naming the widget, so the widget is held while that thread is open:
its reading's `thread.heldBy` names the thread (`module-state.md`), and resolving the
thread releases it.

`threadSurface` and `releaseOutlets` also load through `portable-api.js`. Without a
registered Leaf surface, there is nothing to update or release, and `open` is `null`.

### Page annotation presentation

On a page whose `body` has `data-annotations="page"`, Leaf draws no margin, marks or
thread cards, and one element may draw them in the page's own layout. The feature
gallery's `lf-x-margin` is the worked example: a margin of marks and cards built from
what this section describes.

`placePageThreads(owner, render, {reveal})` supplies the outlets for the page's threads.
`render(targets, {signal, collection, onCommit})` returns an array as `threadOutlets`
does ("Widget-local Thread placement"), an outlet or `null` for each target; a widget's
own outlet still wins. Outlets stay inside `owner`, and if `render` fails, presentation
fails. The targets are every thread whose anchor has a place on the page, resolved ones
included, and the open comment box, whose `thread` is `null`. Each target's `placement`
says where it stands:

- `place` is the element it stands by: the block holding a passage, or the element or
  datum commented on.
- `ranges` holds, for a passage, a live `Range` over each run of its words. Measure
  them for the lines the words stand on, and paint them with the CSS Custom Highlight
  API. They stay the same ranges while they cover the passage: the browser moves a live
  range with words written ahead of it, and Leaf hands over new ones only once the
  words they cover change. A highlight's rule names the elements holding its words,
  since a rule naming none restyles every element on the page and Firefox paints a
  highlight only from a rule matching the words' own element: set
  `data-lf-marked-words`, the mark Leaf's own passage highlights use, on the parent
  element of each range's start and end, and write the rule as
  `[data-lf-marked-words]::highlight(name)`.
- `status` is `exact`, or `fallback` or `outdated` where Leaf can't place the anchor's
  own subject, such as a named control or data since replaced, and `place` is the
  nearest element still standing. A comment on a widget's datum also reads `fallback`
  until the widget has drawn its data, so a target can turn from `fallback` to `exact`
  as the page starts.

Leaf reads no pointing or pressing on a passage's words on such a page, where its own
margin previews and opens a thread from them. A thread is reached by what the element
draws for it.

A presentation may draw every thread at once, as a rail of conversations does, or only
the one the user asked for, as a margin draws a card. A thread it returns `null` for is
drawn nowhere on the page, and a route to it, such as `t`, Show on page in Leaf's panel
or `threadActions.open`, calls `reveal(key)`. Record the thread as open and return; Leaf
runs `render` again, fills the outlet it now returns, and lands the user in it. Return
`false` to leave the thread to Leaf's panel. `reveal` is asked only for a thread among
the targets. One that takes a thread and then returns no outlet for it has failed: Leaf
reports it as it reports a failed `render`, shows the thread in its panel, and doesn't
ask for that thread again until the element calls `update()`.

Leaf seats the comment box in its outlet unless Leaf's panel covers where the outlet
stands, where the user couldn't see what they type; the box then stays in the panel's
field and the outlet stays empty. An outlet with no box of its own, as one hidden until
it is filled, is judged by the nearest box around it. So stand an outlet in the part
of the window clear of the panel, which `shownWindow` gives
(`module-scroll-and-motion.md`), and show nothing for an outlet that is empty.

The returned handle has `read()`, the collection `readThreads()` returns; `update()`,
which asks for `render` again after a change of the element's own, such as a card
closing, and returns a promise of the pass that places the result, so await it before
measuring or focusing what an outlet holds; `open(node)`, which opens the comment box on
the addressable element holding `node`; and `unregister()`.

The same element can show the page's other annotations by registering
`consumeAnnotations(owner, render)`. `render(entries, view)` runs synchronously after
the threads are placed, with the page's annotations grouped by place, one entry each, in
page order. An entry has a `key`, stable while its place stands, and a `title` naming
the place, and the view reads the rest:

- `view.target(entry)` is the element the entry is about.
- `view.items(entry)` returns its readings, the ones a contributed control doesn't
  already show. Each has a `kind` (`on-me`, `comment`, `draft`, `change`, `activity`
  and the margin's other kinds), a `text`, its name in Leaf's words such as "Waiting on
  me", and for some a `label`, such as the question an obligation asks. A thread no
  outlet holds is among them as a `comment` with its `thread`, so an element that also
  places threads draws those from its targets. `view.activate(item)` runs one, as a
  press on its margin entry would. Key items by `contributionItemKey(item)`.
- `view.controls(entry)` returns the contribution's real controls. Place those nodes,
  not copies of their markup, so they keep their behavior. `view.controlKey(control)`
  and `view.controlRecord(control)` name and describe one.
- `view.arriving` is true while focus is on its way to an entry here; release held
  layout so its control can be reached.
- `view.place(entry, row, item)` ties a row to its entry's place for commenting and
  Escape. The row stands inside `owner` by the time `render` returns. The presses in a
  placed row are the page's margin targets, which Go-to letters (`g m`); pass the
  `item` a row stands for, and a thread's row is among its Thread controls (`g t`).

Both registrations throw on other pages; register them in `whileConnected`. The
annotation view's handle has `read()`, `update()`, which asks for `render` again, and
`unregister()`. Keep rows keyed, and hold size
changes back with `HeldReading` (`module-scroll-and-motion.md`, "Holding the reader's
place") while updating surviving controls at once. An owner that scrolls inside its own
box registers it as a reading region. Whatever the owner doesn't show stays in Threads
and the On lists of Leaf's panel.

A box the element stands over the page follows its place with `anchorTo`
(`module-scroll-and-motion.md`, "A box that follows scrolled content"), and joins the
layer the user hides with `o` ("The annotation layer").

## The annotation layer

The user hides everything drawn over the page's content with `o`, or Hide annotations in
the leaf's menu, to read what lies under it. A widget that draws over the page, as a
page's own margin draws pins and cards, joins that layer with
`watchAnnotationLayer(watch)`. Leaf calls `watch(hidden)` at each change, and at once
where the layer stands hidden as the widget joins, as after a reload; the command takes
a press while anything watches or the layer is hidden. While `hidden` is true, draw
nothing over the page's content, and first return the user from anything of the widget's
that goes to the content it stood by. What takes room of its own, such as a rail beside
the column, covers nothing and stays. Register it in `whileConnected`, and call the
function it returns as the cleanup.
