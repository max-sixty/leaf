# Authoring behavior modules

Use this reference for browser behavior in a page script, a page-owned widget, or a
reusable package widget. Read "What a behavior module owes" before writing one, then
the sections its behavior needs. The same helpers serve each form. A semantic
controller needs a registry-declared widget; ordinary elements use the other helpers
alone.

[page-authoring.md, "Page behavior"](page-authoring.md#page-behavior) owns script placement,
imports, and revision lifetime. [packages.md, "A widget"](packages.md#a-widget)
owns element declarations; its ["User state"](packages.md#user-state) and
["External or derived data"](packages.md#external-or-derived-data) sections own
state and source contracts. Add or change those declarations when the module needs
a new capability.

Registry-declared widgets default-export their constructor. Leaf registers it in
the publication’s vocabulary. Create child widgets with
`createWidgetElement(owner, tag, Constructor)` from the public API, importing the
child’s constructor. Each publication retains these constructors and its private
module dependencies. The installed layer’s runtime and vendor libraries have one
instance per running document; changing their bytes requires a fresh document.

## The helper surface

`/runtime/widget-api.js` is the whole Leaf API a behavior module gets. A module imports
only from it: it does not reach into the runtime's other modules, query Leaf's own
chrome, or copy a runtime helper into itself. Each helper is documented once below, in
the section for the task it serves, and the header of its module under `runtime/`
states its full contract. A DOM helper takes the element whose behavior it implements.

Of Lit, the surface exports `render`, `html`, `nothing`, `repeat`, `keyed`, `live`,
`ref`, `createRef`, `classMap`, `styleMap`, `guard`, and `unsafeHTML`.

## What a behavior module owes

Each rule names the section that documents its helpers.

- Upgrade once with `once()`, and hold each connection's listeners, observers and
  registrations in `whileConnected` ("Upgrade", "Connection lifetimes").
- Check `quoted()` before wiring anything that carries input back ("Upgrade").
- Read the page's words with `says()` or `wrote()`, never `textContent`, and a widget's
  `<pre>` body with `bodyText()` or `dataBody()` ("Reading the page").
- Build injected UI with `offer()`, `offered` or `selectableOffer()`, label it with
  `relabel()`, and reserve measured room inside `measure` ("Generated controls").
- After a view swap that keeps the widget's outer box, await `layoutChanged()` before
  restoring scroll ("Generated controls").
- Keep the widget's first-paint box once the page presents ("First paint").
- Schedule paints with `frameFor` and observe size with `sizeObserver`, so checks and
  tests wait for that work too ("Scheduling paints"); write repeated state through
  `keeps` ("Writes that change nothing").
- Record durable user state only through the widget controller, and keep working state
  in `tabStore` ("The widget controller", "Tab-local working state").
- Register commands at upgrade ("Commands and keyboard routes").
- Place focus with `focusDestination`, never `element.focus()` ("Focus and layers").
- Animate through `motion`, never `element.animate` ("Motion").

## Upgrade

A module's `connectedCallback` returns at once unless `once(this)`, which is true only
on the element's first connection, so a reconnection never builds the widget twice.
Keep `disconnectedCallback` for teardown that must happen synchronously, such as
cancelling a grab or removing hoisted UI; everything else a connection holds goes in
`whileConnected` ("Connection lifetimes").

`quoted(element)` is true for a widget inside one the registry marks `x-exhibit`: quoted
material, which never takes the user's edits. Check it before wiring anything that
carries input back, such as a choose path or a drag grip. Presentational upgrades and
view state still run in a quoted widget.

`failSoft(element, error, source)` turns a failed upgrade, or a failed part of one, into
a visible error box naming the widget, with `source` beneath it when given, and reports
the failure as the page's error, which `page check` fails on. In a container a template
renders, the box is a template value, so the next `render` there replaces it. On a
widget with a shadow stage the box stands in the stage, and the next `shadowStage` call
replaces it. `reportFailure(element, error)` sends that report alone, for a part the
widget shows failed its own way while the rest stands, such as a diff file whose patch
it cannot draw.

## Connection lifetimes

A widget can leave the page and return, as a revision or a thread presentation moves
it. Register `whileConnected(element, start)` once, after `once(this)`, for the
listeners, observers and registrations one connection holds. It calls `start(signal)`
at once on a connected element and again on each return. Listeners take `{signal}`, and
`start` may return a cleanup function for other resources. A departure aborts the
signal and runs that cleanup. A `start` that throws has its signal aborted and is never
started again; its error reaches the caller of `whileConnected`, or the page's error
report when it was a return. The function `whileConnected` returns retires the
registration for good and releases what it holds. Call it when the element no longer
needs those resources, as a widget that fails soft from a paint it cannot repeat does,
so a return does not start them again. Register resources a `watchData` callback uses
before `watchData`, so they stand when the callback runs.

```js
schedulePaint = frameFor(this, () => this.paint());

connectedCallback() {
  if (!once(this)) return;
  this.build();
  whileConnected(this, (signal) => {
    window.addEventListener("resize", this.schedulePaint, { signal });
    const sizes = sizeObserver(this.schedulePaint);
    sizes.observe(this);
    return () => sizes.disconnect();
  });
}
```

Leaf decides a departure once a DOM mutation batch is read: an element removed and put
back in the same batch has not left and keeps its resources. A connecting element's
`start` runs only after every element that left before it has released, so a widget a
revision replaces hands its replacement a registration only one element may hold, such
as `registerThreadPresentation` or `registerReadingRegion`.

A `widgetController` subscription, `watchData`, `watchComparison` and the page readings
("Page readings") pause while their owner is away. On a return, a subscription calls
its callback again, and the controller its `renderState`, only when its reading changed
while the owner was away or when a callback's returned promise had not settled before
the owner left. A callback that throws or rejects is reported once, as a page error
naming the element, and its subscription stays: the next changed reading calls it again.
So return the promise of any paint that finishes later, abandon unfinished work on
departure, keep finished nodes where they are, and have `start` restore whatever its
cleanup cleared. A `renderState` or controller subscriber that throws also replaces what
the widget shows with its fail-soft box ("Upgrade"), since the rest of its view may be
half drawn.

`readingPaint(element, draw)` gives a reading of the module's own the same rule. Build it
once, before `whileConnected`. The returned `paint(key, ...args)` calls `draw(...args)`
unless `key` names the reading it last drew, so calling it from `start` on every
connection draws again only a changed reading, or one whose promise a departure cut
short. Authored content that never changes is one reading, keyed by its text. A `draw`
that throws or rejects is reported by the same rule and never fails `start`; `paint`
then returns a rejected promise you may ignore. `paint.owes(key)` says whether a call
would draw, `paint.forget()` makes the next call draw, `paint.refresh()` redraws the last
reading (on the return, when asked while the owner is away), and `paint.stop()` retires
it.

`aborted(signal)` resolves once a signal aborts, for work that races its own
cancellation: `Promise.race([work, aborted(signal)])`.

## Startup and presentation

`body[data-lf-presented]` means the page's first authoritative state, or its deliberate
offline fallback, is safe for recorded interaction. Authored content is visible before
then, and Leaf disables its arrival transitions and durable widget actions until the
stamp. Printed keys pressed earlier are held and reach the page's key handlers after
the stamp, in order, so neither a package's keys nor its styles need an arrival guard.
A package opens a dialog or popover only after the stamp or in response to a user
gesture; Leaf does not defer top-layer UI during startup. A declared `x-shadow` widget
gets the same arrival protection when it builds its shadow root with `shadowStage`
("Shadow stages and styles").

Startup dispatches two events on `document`. `PRESENTATION` fires once, in the turn the
page's complete authoritative layout first stands: UI drawn from element geometry reads
it there synchronously for its first paint, then follows ordinary layout signals.
`PAGE_INTERFACE` fires at startup and at each in-place revision activation; UI derived
from authored structure reconciles there, and its `detail.present(promise)` holds the
page until asynchronous preparation lands.

A widget that keeps part of its own upgrade off the presentation path, such as a heavy
renderer it loads only once the user has the page, runs that work through
`afterPresentation(() => …)`, which both waits for presentation and declares the work.
Until every such arrival lands the page reads as still arriving, so a reader outside it
waits on the page rather than on a widget it would have to know about.

### First paint

Upgrade should add behavior and move nothing: a widget's box at first paint is the box
it keeps once the page presents. `leaf package check --render` names a widget that moves
as `keeps-first-box` ([packages.md, "Seeing it"](packages.md#seeing-it)).

- Size the widget in the package theme under `html[data-lf-interactive]`, as its module
  will draw it. Leaf sets that attribute before first paint wherever its runtime will
  run, in a served page or an export.
- Where the module draws a structure of its own whose shape the log does not change,
  such as a row of count tiles, declare that structure as `x-prepaint` rather than
  summing its line heights in the theme. Delivery writes it into each occurrence for the
  first paint, and the module removes it (`:scope > [data-lf-prepaint]`) in the same
  step that draws its replacement.
- Where the structure depends on the instance's authored members or on values it keeps
  in `tabStore` ("Tab-local working state"), declare `x-initial` instead: the rooted
  path of a classic JavaScript bundle that registers one synchronous producer with
  `document.documentElement.lfInitial.register(tag, render)`. Delivery draws each host
  with it as soon as the host's source has arrived, so the widget first appears whole
  while prose before it can paint; with scripts disabled, the authored host stays as
  written. `render(host, {tabStore, offer, offerElement, keeps})` builds the drawing and
  returns the node references and mechanical state the behavior module needs. It may
  move authored nodes within its host; Leaf keeps their original source for passages,
  anchors and version comparison. The producer does no asynchronous or network work
  and reads no log-derived state. The behavior module calls `initialRender(host)`, which
  adopts the existing drawing or produces it for a later revision or a thread arrival,
  then adds behavior to those nodes without rebuilding them. The theme styles the
  actual initial layout; neither the producer nor the module reserves an estimated
  height. `x-initial` requires `x-upgrade: true` and cannot accompany `x-prepaint`.
  Build its classic bundle during development and commit it; installation, serving and
  export run the committed bundle without a compiler.
- Where the markup cannot say how tall the drawing will be, declare `x-height`, add the
  class `lf-rendered` once the drawing is in, and draw at the stated height where the
  drawing can take any. `page check --render` tells a page's author the height to
  state for a drawing that cannot.
- Where the widget shows one of its members at a time, declare `x-views`, open on the
  member `openingView(holder, members)` returns, and until the module upgrades show only
  the member marked `data-lf-opening`, as `lf-tabs` does. Record each member the widget
  shows with `keepView(holder, member)`, so a reload reopens it.

## Rendering

### Template rendering

Paint templates with `render(template, container)`, which lands in the turn that
caused it, including a forward widget gesture. Package widgets extend `HTMLElement` and
receive semantic state through `widgetController`, without a reactive copy of that
state.

Templates own generated containers or bounded ranges, never authored children. Once
`render` owns a container, update its children only through `render`, so Lit keeps its
markers and disconnects removed directives. `repeat(items, identity, template)` keys
template rows and keeps a row's nodes across reorders, but builds afresh a row that
moves to another `repeat`, detaching any retained node in it; place nodes the module
retains itself as "Retained nodes" describes.

When the application owns a native property the user also changes, bind it with `live`,
such as `.value=${live(value)}` or `.checked=${live(checked)}`: it compares the live DOM
value and restores the authoritative value even when that value equals the previous
template input, as when a gesture is refused. Do not bind initial defaults onto
properties whose current value belongs to the browser.

### Retained nodes

`setChildren(parent, nodes)` makes `parent`'s children `nodes`, in order, moving only
what is out of place. Where nodes move between parents, place every list at once with
`setChildLists([[parent, nodes], …])`, naming outer parents first, so a node moves
straight from the list it leaves to the one it joins. For one placement use
`move(parent, node, before)`, with `null` to append. For a subtree whose contents and
descendant attributes all belong to the renderer, `setRenderedChildren(parent, nodes)`
matches unchanged nodes and edits only changed text, keeping native selections in text
the source kept; keep independently stateful controls outside that subtree.

Every placement of a retained node, by `render`, `repeat`, these helpers or `move`,
keeps the user standing in it. Within one document it uses native `moveBefore` where the
browser has it, which keeps focus, caret, typed text and iframe documents. Elsewhere,
Safari included, it inserts the node and puts the user back on it with a text field's
caret, and an iframe in it reloads. A reorder needs no focus hold of its own. A plain
`append` or `insertBefore` of a node that already stands somewhere takes it out first,
which blurs it. A selection in a moved editable collapses even under `moveBefore`, so a
custom element holding a `LeafEditorView` calls the view's `placeSelection()` from its
`connectedMoveCallback`. Leave native disclosure, editor and scroll state with the
retained nodes.

### Shadow stages and styles

`shadowStage(host, nodes)` builds an `x-shadow` widget's shadow root, gives it the
theme's styles, makes its children `nodes`, and returns the root; never call
`attachShadow` yourself. For a template, stage a concrete container with
`shadowStage(host, [container])`, call `render(template, container)`, and keep that
container in later stage updates.

A module that writes stylesheet text of its own, for a constructed sheet or a `<style>`
in its shadow root, wraps it in `inBaseLayer(css)`. The rules then join the theme's
`lf-base` cascade layer, below Layouts, semantic state and the page's own stylesheet.

### Scheduling paints

Paint an element through `frameFor(element, paint)`, which returns a scheduling
function: calls coalesce into one `nextRender` callback, calls while the element is
detached are ignored, a departure cancels pending work, and the element is checked
again before painting. A return permits fresh scheduling; it does not replay cancelled
work.

`nextRender(callback)` runs a callback in the rendering pass under way, or in the next
frame's when asked from anywhere else, such as an input handler. `nextFrame(callback)`
never runs in the pass that asked for it, for a step that must wait a frame, such as an
animation tick. Both return an id for `cancelRender(id)`. Leaf counts this work: the
page does not read as settled until it is done. Continuous motion that may run until
the user stops it, such as recording playback, uses `nextAnimation(callback)` and
`cancelAnimation(id)` instead, which hold no settlement open; cancel it when the motion
stops or its owner leaves.

`afterScript(callback)` runs a callback once, at the microtask checkpoint that ends the
current script, for a paint two steps of one script would otherwise invalidate twice.
Asked again with the same function before it runs, it still runs once, so pass a function
the module keeps rather than a new arrow at each call.

Observe size with `sizeObserver(callback)` in place of `new ResizeObserver`, so the
page reads as unsettled while sizes change. Pass `{counted: false}` for boxes that move
for as long as the page plays.

### Writes that change nothing

A write that restates what a node already says still reaches everything watching the
page, from screen readers to a full-document repaint. `keeps(node, name, value)` writes
an attribute only when its value would read back differently; pass booleans and counts
directly, and `null` or `undefined` to remove it. `keepsText(node, text)` and
`keepsHidden(node, hidden)` do the same for words and `hidden`. `toggleAttribute` and
`classList.toggle(name, force)` already write nothing for an unchanged flag or class. A
length measured off the page goes into a style property as `layoutPx(length)`, which
rounds to layout's 1/64px so a box that has not moved writes nothing new;
`atLayoutPrecision(length)` returns the rounded number.

## Generated controls

`offer(tag, className, label, inputType, pressable)` makes a control or a box of
controls a widget injects: the native element, so the browser keeps its activation,
disabled state, focus and accessibility, carrying Leaf's markers for generated chrome.
`inputType` is for an `input` only. A custom element whose host has a complete `focus()`
and `click()` contract passes `true` as `pressable`, so its tag marks it as a press
like a native control. In a Lit template, `<button ${offered("lf-btn")}>` gives an
element the same anatomy: `offered` owns its class and markers, and a native button's
type defaults to `button`. A native input's `type` binding goes before `offered`, so its
press marker reads that type. Bind values and handlers normally.

A page word that is also a control, such as a tab's name, has to stay selectable, which
a form control is not. `selectableOffer(role, className, label)` builds it as a focusable
span with that `role`, and the widget supplies the keyboard pattern the native element
would have had. `el(tag, className, text)` makes an element with its class and first
words and no Leaf markers, for structure that is not injected UI.

`relabel(node, label, {says})` writes a generated control's label. `says` is required:
`true` where the label is the page speaking, such as a pick mark reading "chosen",
`false` for an ordinary action word, and `"echo"` for a copy of words the page says
elsewhere, such as a roster row naming a worker. A template label writes the same
markers as static attributes: `data-lf-gen="1"`, plus `data-lf-said` or `data-lf-echo`.

A widget upgrades wherever Leaf connects it, including in a shut panel where every box
measures zero. Take a measurement inside `measure(element, take)`, which runs `take`
now when the element has a box and otherwise the first time it does. `reserve(control,
labels)` reserves a changing label's widest words, measured in the control's own face,
through `measure`, and measures again when the window changes the face.

After a view swap that rearranges descendants without resizing the widget's outer box,
call `layoutChanged(element)` and await its promise before restoring scroll. It
dispatches the bubbling, composed `LAYOUT` event, which a widget that measures what it
holds listens for; a listener joins asynchronous work through the event's
`detail.present(promise)`. A size change needs no call, since a `sizeObserver` hears it.

`searchField(className, {name, label, placeholder = label})` builds a search or filter
field with the shared frame, accessible label, native editor and Clear. The caller owns
its query and results. Put an auxiliary reading such as a match count in its `end` slot
and reserve its longest value with `reserve`.

A widget folds content it may show again by setting its `hidden` to `HIDDEN`. Where the
browser supports `hidden="until-found"`, find-in-page and fragment links still reach the
content and fire `beforematch` on it, and the widget opens it there; elsewhere the
content is plainly hidden. A folded element that is itself a Tab stop stays one, so the
widget withdraws it.

## Reading the page

`says(element)` is what an element says, read the way passages and comments read it.
Use it in place of `textContent`, which also returns lines Leaf writes into the page.
`wrote(element)` reads only the words the author wrote, leaving out what an upgrade
generated, for naming one of the widget's own parts. Read a widget's `<pre>` body with
`bodyText(this)`, which drops leading blank lines and trailing whitespace, or
`dataBody(this)` where whitespace is content, as in a diff; the element's own
`textContent` also holds the formatting around the `<pre>`.

A message's HTML markup is a document of its own, and it may repeat the shapes the page
holds. A module that finds a partner element by reference, as a seat names the widget it
serves, searches `authoredScope(element)`: the page's `main`, or the body of the message
whose markup holds the element. A search of the whole `document` lets quoted markup
answer for the page. `elementById(id, root)` finds an id in the document, or only within
`root` when one is given, such as `authoredScope(this)`, and searches the shadow trees
widgets declare too, where `getElementById` misses. `under(node, root)` says whether
`node` is `root` or inside it, across the shadow boundaries where `contains` stops.
`inChrome(node)` says whether a node stands in Leaf's own interface rather than on the
page, as a widget an agent sent in a Thread reply does.

### Naming elements

A module that names an element away from it, in a feed row or a summary, reads the
page's shared names rather than its own. `addressableLabel(element)` is what Leaf's
chrome calls it: first the name the authoring contract gives it (the attribute its entry
declares with `x-name`, else a leading `<summary>`, heading, or titled member's
`<strong>`, inside a leading `<header>` or `<hgroup>` too), else its caption, its
`aria-label`, its `<label>` or its `alt`. An element whose words are its own, such as a
paragraph or a list item, is otherwise named by those words cut short; any other element
takes the name of the nearest element holding it that has one, so a question's options
are named by the question. Past that, plain markup is named by its words cut short and
a registered widget by nothing: the label is empty, and `addressableWord(element)` is
the word for its kind. A widget whose title is an attribute, as a column's `label` is,
declares `x-name`.

`anchorLabel(anchor, about)` names a comment's anchor the way Threads does.
`excerptWords(text, cap)` cuts words to at most `cap` characters at a word boundary,
ending in an ellipsis.

### Reading declarations

A module reads its registry entries rather than repeating them.
`declarationFor(element, key)` is the value of one key in the entry for the element's
tag, or `undefined`. `elementsDeclaring(root, key, {direct})` lists the elements under
`root`, or only its children with `direct: true`, whose entries declare `key`.
`matchesWhen(element, when)` says whether the element's attributes satisfy a
declaration's `when`, as an `x-thread-seat` declaration's `when` selects its elements.
`layerFact(name)` returns a copy of a layer-wide `$` declaration, such as `$reactions`.

### Following a reference

A module reaches another widget through an attribute its entry declares in `x-refers`
([packages.md, "References between widgets"](packages.md#references-between-widgets))
rather than looking the id up itself. Leaf resolves the attribute in the owner's own
authored document first, so a widget in a reply finds its message's element before a
page element with the same id, as the server does, and then in the page, which a reply's
widget may name. A keyed contract resolves inside the owner's enclosing scope instead.
Both helpers below throw a `TypeError` for an attribute the owner's entry does not
declare.

A key addresses elements under the named widget in one key space: a registered visual
part's id, a projected datum's key, or, where the widget's parts have a private address,
whatever its `lfElementsFor(key)` maps to elements under itself. `lf-code` answers its
`hi` grammar, so `"3-5,8"` addresses those lines.

`navigateToDatum(widget, attribute, key, messages)` travels to the first element a key
addresses. Leaf resolves declared shadow trees, asks the target to hydrate lazy data or
draw a visual part it shows only in another state, opens its containing disclosure,
focuses the addressed element, updates the fragment, and announces the supplied
`success` or `missing` message. Commands at that focus use the datum's identity. A lazy
target may implement `lfRevealDatum(key)` to return its hydration promise,
`lfDataDatum(key)` to map a semantic key to the rendered projected element, and
`lfDatumLabel(key)` to name a datum it has not drawn, as its `projectData` label will
once it is. Where a key is a source location rather than the datum's durable identity,
translate it to the durable key and read `projectedDatum(widget, key)`: the unique
current projected element, or `null` when it is missing or ambiguous, including after a
reveal replaced its node.

#### Indicating (experimental)

The signature and the `lfElementsFor` hook may change. `indicate(widget, attribute, key)`
marks the elements a key addresses, in place of whatever the calling widget last
indicated through the same attribute, and returns whether anything is marked; a `null`
key clears it, which a driver owes in its cleanup. Leaf paints the marked elements with
`data-lf-indicated` and nothing else, leaving the target's own ARIA state alone, and
never scrolls, focuses, reveals, hydrates or announces for them, so a driver may move
its indication every animation frame; the driver's own narration says what the mark
means. An indication is browser state, like hover: the log never records it, and a new
revision does not carry it. A widget whose parts have a face of their own styles
`[data-lf-indicated]` on them; the default is an accent outline. A target that
re-renders what a key addresses calls `layoutChanged(this)`, and every standing
indication resolves again.

## The widget controller

`widgetController(owner)` is the one semantic interface of a registry-declared widget;
callers supply no options. Leaf captures the owner's identity and revision-bound
declaration before upgrade, so an author change to those facts fails closed. Its
methods are `read`, `subscribe`, `dispatch`, `defer`, and `present`.

`read()` returns an immutable `{authored, state, thread, provenance, actions}` snapshot.
`authored` is the typed baseline decoded from validated source markup; `state` is that
baseline with admitted and unresolved records folded over it; `thread.heldBy` is the
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
reading. While a drag is held (`dragging`, "Pointer presses"), Leaf holds new readings
back without a `defer`.

`present(promise)` registers asynchronous visible preparation, such as a renderer
loading; the page does not read as ready until it settles.

### Tab-local working state

State the user arranges but does not record, such as which group they collapsed, stays
out of the log. `tabStore.get(key)` and `tabStore.set(key, value)` keep a string of it
for this page in this browser tab, and setting `null` removes it. An `x-initial`
producer reads the same store, so the first paint can draw that state ("First paint").

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
effect's payload contract in [packages.md, "User state"](packages.md#user-state). For a
recorded body, attribute or scalar value, send `detail: {value}`. For a position, send
`detail: {unit, value, rank}`: the moved element's id, the destination container's id,
and `rankAt(state.<verb>, container, index, unit)`, the rank of a unit dropped at
`index` among the container's other units. A rank keeps a unit's placement whichever
other moves stand, until a version authors the container's units differently. A verb
with no record sends what its declared `detail` schema asks for.

A widget's `x-awaits.value` selects its typed answer from the state ("Reading asks and
obligation queues"). Its class may declare `static answerWords(value, element)`, which
returns concise words for that answer in the Questions panel. `value` is the ask's typed
`answer.value`; `element` supplies authored markup such as option labels. Read nothing
the module renders; Leaf collapses the words' whitespace. A widget without this
formatter supplies no answer wording, and its typed answer stays available through
`readQuestions()`.

## Data subscriptions and projections

The source declarations and producer workflow are in [packages.md, "External or derived
data"](packages.md#external-or-derived-data). A module subscribes through its own input
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
the contract it requires. Register once for the element; returns follow "Connection
lifetimes". The returned function ends the subscription for good. Its `refresh()`
repaints the last delivered snapshot, on the return when asked while the owner is away;
it neither delivers a pending source reading nor revives a retired subscription.

If the callback renders asynchronously, it returns that promise, so Leaf publishes the
source revision as ready only after the projection settles. A rejection is that
subscriber's page error, reported once, and does not hold the revision back.

A source whose contract declares `deferred` sends its rows without that field.
`loadDeferred(snapshot, key)` fetches one row's field for the `snapshot` the callback
received, and throws when the source's revision changed before or during the load.

### Projecting data

The renderer owns its nodes and their placement ("Retained nodes"). After placing them,
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
`watchData`'s, or a page reading's) or in a `readingPaint` draw subscribes that paint to
Leaf's shared clock, which repaints it only when a reading's result changes; the clock
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

## Commands and keyboard routes

A widget contributes each command once with `commands(element, title, rows, options)`,
at upgrade. The dispatcher, shortcut bar, command reference, `aria-keyshortcuts` and
inline hints all read those same declarations. `options` is the scope's own `when`
predicate, alone or as `{when}`.

`commandScope(title, rows, options)` declares the same scope as a capability, for
controls Leaf rather than the widget creates: put it on a margin entry's `scope`
("Margin contributions"), and each projection attaches it to its own visible control.
Where the same command set also applies to retained widget DOM, attach that one
capability with `commands(element, scope)` rather than declaring the rows again, as here:

```javascript
const actions = commandScope("In a classifier", [
  {
    id: "classify.pass",
    title: "Pass",
    keys: ["ArrowLeft"],
    contextKeys: ["1"],
    decision: true,
    control: passButton,
    bindingBadge: passHint,
    when: canClassify,
    run: () => classify("pass"),
  },
]);
commands(classifier, actions);
```

In a template, `commandsOn(title, rows, options)` attaches a scope to its element: once
per connection, taking the current declaration on each render, and withdrawing its
attachment when the directive leaves. When rows read the element they stand on, pass a
function of that element in place of the rows, such as
`commandsOn(title, (summary) => [{ keys: () => DISCLOSE(summary), … }])`; it runs on
each render, so it only builds rows. Declare a template's scope there rather than
looking its element up after rendering.

### Command rows

Leaf checks each row as it enters the register and throws for a malformed one.

| Field | Meaning |
| --- | --- |
| `id` | Stable dotted identity, such as `draft.save`, lowercase. Keep it when the keys or words change; the command reference and repeated widget instances use it. |
| `title` | Required concise name, such as `"Pass"`, or a function where state changes it. |
| `description` | Optional detail the command reference shows. |
| `line` | Shorter wording for the shortcut bar, which defaults to the title; `false` keeps a reference-only row off the bar. |
| `label` | Overrides the keycap, not the action name. |
| `keys` | Bindings in canonical spelling (`"a"`, `"Shift+a"`, `"Mod+Enter"`), or a function returning them. |
| `contextKeys` | Aliases that may also be forwarded to the enclosing ask's opening and its margin controls and threads ("Decisions and forwarded keys"). A row with `routes` declares them on each route instead. |
| `routes` | Subcommands, each with its own `id`, `title`, and `binding` or `contextKeys`, where one row's keys mean different things. |
| `when` | Whether the command is available. A route may declare its own. |
| `run(binding, context)` | Performs the command. A row without `run` presents a native behavior or a shared outer handler and does not shadow it. |
| `control` | The visible element that activates the command. |
| `decision` | `true` where the command starts, advances, answers or revises the ask containing the scope's element; it needs a `control`. |
| `bindingBadge` | Requests an inline shortcut hint ("Inline shortcut hints"). |
| `repeat` | `true` to run on a held key's repeats too; off by default. |
| `native` | `true` to run without preventing the platform's own default for the press. |
| `reach` | The short place phrase the command reference shows while the command is unavailable, such as `in an open draft editor`. |
| `runFromCommandReference` | `false` for a parameterized step the command reference cannot run without a choice it does not have, such as a hint tied to the live viewport. |

A route may also declare its own `when` where its control is available independently of
its siblings. The shortcut bar stays compact, while the command reference lists and runs
each route on its own.

Call `paintKeys()` after private state a `when` or a computed field reads changes, since
closures are not reactive; every projection of the commands then updates together.

### How scopes compose

Command scopes compose by focused ancestry: the exact control's scope is nearest, then
the scopes of the widgets containing it, then Leaf's page scopes. A scope owns only the
bindings whose rows run something, so an undeclared key falls outward. A row keeps its
key while its command is unavailable, so the key never exposes an ancestor's different
meaning. Escape means one step back at every depth, and an unavailable inner Escape
passes the key on to the next live one. Text fields and other native controls keep their
editing keys ahead of every widget scope and context alias, including aliases attached
to an editor itself. Replacing or removing a scope's attachment withdraws its old
routes.

A native button with a row's `control` and `run` has one activation path: Leaf invokes
`run` for both its click and its keyboard command, and paints its disabled state from
`when`. Remove a separate click listener and disabled painter, and run the semantic
action directly in `run`, never the same button's `click()`. Express every condition in
the row's, route's or scope's `when`: Leaf paints `aria-disabled` and guards activation,
so a refused press keeps focus, and the button's own `disabled` attribute is an output. A
disabled fieldset still constrains the button. Native inputs keep their platform
activation and editing behavior; a row that focuses an editor or activates a checkbox
does not replace it. Generated margin controls use the same callback ("Margin
contributions").

Leaf already answers the keys of every folding control, a `details > summary` or a button
with `aria-expanded`: Enter and Space, and the arrow that opens or closes it in its text
direction. A widget row that rewords the same press takes `DISCLOSE(element)` as its
`keys`, so the two name the same set. `rowArrows(node)` returns `[back, ahead]` for a row of
controls, which is `["ArrowRight", "ArrowLeft"]` in right-to-left text. `PRESS` is the
keys a focused button answers, Enter and Space, for a row that presses a control a
button would. `labelOf(row)` is the key text a row shows, for a tooltip that names its
keys, and `saying(rows)` is what a set of rows answers now, in the words a screen reader
speaks, for an announcement.

### Decisions and forwarded keys

`keys` work inside the widget. `contextKeys` work there too, and are the only keys Leaf
forwards to the enclosing ask's opening and its margin controls and threads; a route can
declare its own. Numbers are the widget's own choices, not an allocation across asks:
options own their stable numeric assignments, and a classifier declares Pass as `1` and
Keep as `2`. Never assign numbers from the currently available actions: disabling `1`
must not turn `2` into a different action. The page owns `q` and `Shift+q` for moving
between Questions.

`decision: true` marks the command's role in the ask; it neither assigns a binding nor
makes ordinary keys forwardable, and a numeric command need not be a Decision. A
forwarded key keeps the original scope, row and route, checks their current
availability, and invokes the original callback or native control. Register a command
once, not on every nearby button; evidence nested inside an option is not an answer, and
a margin entry may stand outside the ask's element.

### Inline shortcut hints

Declare `bindingBadge` on a row or route to request an inline hint, whether or not the
command is a Decision. An element names an empty face the widget positions, inside the
control it labels or beside it; `null` requests a badge at the control's corner. Each
face belongs to one action. Leaf gives the face the class `lf-binding-seat`, which keeps
it absolutely positioned even while empty, so filling it moves nothing; position the
seat with its holder and offsets. Leaf writes the key into the face while the face shows
and the key works, and clears it otherwise. The widget owns the face's placement, not its
text or active state, and paints no binding text itself. A command with `contextKeys` and
no `bindingBadge` has a key nothing on the page shows, and `leaf package check --render`
names it (`shows-context-keys`, packages.md, "Seeing it").

### Walks

A list of focusable rows takes its walk from `rowWalk({id, noun, plural, rows})`, whose
two returned rows go into the list's own scope: ArrowUp and ArrowDown step and clamp,
Home and End reach the ends, and each landing shows its position, such as `Option 3 of
7`. `rows()` returns the list as it stands at each press. Optional `landed(row)` runs
after a press that moved to another row, and `scroll: false` keeps the page still for a
list read off what is in view.

A walk the widget moves itself, such as through its tabs or a diff's hunks, calls
`beginWalk(key, noun, read)` at each step and announces the text it returns, such as
`Hunk 3 of 7`. `read()` returns where the walk stands, usually
`listWalkPosition(items, current, {identity})`, which is `null` when `current` is not in
`items`. `key` names the walk, so a step that lands where the last one did shows that the
walk reached its end.

### Go-to targets

Every visible press a widget builds with `offer()` or `selectableOffer()` joins the
targets `g` reaches. A package declares no `g` binding of its own and lists those
controls nowhere else. Buttons, checkboxes, radios and selectable controls are targets;
text and range inputs stay ordinary Tab stops.

## Focus and layers

A module that puts the user somewhere calls `focusDestination(element, cause)` rather
than `element.focus()`. The cause says what moved them, and every reader of where the
user stands acts on it:

- `"move"`: a route taking them somewhere, such as a walk to the next row or a box opened
  to type in;
- `"return"`: putting them back, such as a widget's own Escape step landing them in the
  thing it took them out of, or a re-render handing them to the control that replaced
  the one they stood on;
- `"step"`: a widget's own Tab loop;
- `"press"`: landing on a control to press it on the user's behalf.

A return marked as a move reads as the user arriving, and releases news or opens options
they never went to. An element that is not a control is lent a tab stop for exactly as
long as it holds focus, so the browser's Tab order continues from there and no
`tabindex` is left behind. `{caret: [start, end, direction]}` places a text field's
caret. Focus placement never scrolls; reveal the destination separately with
`scrollIntoView` ("Scrolling to a destination"). In an embedded sample, it places focus
only while that child owns input.

A module that hides or replaces nodes the user may be standing in, as a re-render that
rebuilds a row does, calls `holdFocus(scope)` before the change and the function it
returns after it; moves keep the user's place themselves ("Retained nodes"). `holdFocus`
returns `null` where the user stands outside `scope`. The returned function puts the user
back on the node, with its caret, or on the first drawn stand-in it is passed, such as
the replacement keyed on the same identity, and does nothing once focus was placed
elsewhere in the meantime. A list of keyed items passes `holdFocus(list, { key })`,
naming the attribute each item carries: the restore then lands on the item keyed the
same, or the nearest that survived, and on the control in it like the one the user
stood on.

Generated native controls can carry a stable `data-lf-carry` key inside their nearest
named owner, which must match authored markup by id and tag; another named wrapper starts
its own scope, and keys are unique within it. When a live revision replaces the
document, Leaf carries focus and caret by owner id, key and tag once the generated
control is visible after upgrade. Authored inputs keep focus at once, so typing continues
during startup.

`focused()` is the element where the user stands, across shadow trees.
`standingIn(scope)` says whether the user stands in a scope, across shadow trees, and
`whenLeft(element, leave)` runs `leave` once when they move off an element; a window
losing system focus does not count. A group reached by its own arrows offers one Tab
stop with `rove(items, stop)`; a `null` stop leaves it none.

### Layers

A widget's own layer, such as a list it opens over its contents, records where it was
opened from with `openLayer(layer)` as it opens, which reads where the user stands.
Open a native modal dialog or popover with `showNativeLayer(layer, {source})`;
`modal: false` opens a nonmodal dialog. Inside a sample it suppresses the native
opening's automatic focus, so place the intended arrival with `focusDestination`. A
popover keeps its `source` when Leaf re-seats it, as it does when a panel starts or stops
covering the page. Close a native dialog or popover with `closeNativeLayer(layer)`,
which inside a sample keeps the platform's return from taking focus from the containing
page. `isNativeLayer(node)` asks whether a popover is open or a dialog stands modal; lint
refuses a selector that asks it again.

A layer closes with `closeLayer(close, land)`. `close` hides it, and `land`, a function,
puts a user who stood in it where the close takes them, usually
`() => handBack(openerOf(layer))`. `handBack(...destinations)` lands the user on the first
destination that takes focus, most particular first, and lets go onto the page where
none does. Readers of where the user stands hear only where they end up. The layer's
Escape is a command row like any other key.

### Delayed work

A module implementing its own navigation captures `retainUserIntent()` in the gesture
that starts it, before its first wait, and checks the returned predicate after every
wait before moving focus or scroll. Loading a file, a deferred value or a renderer is a
wait, and the predicate turns false once the user presses, types, scrolls, leaves the
window, or moves focus elsewhere, so a user who went on is not moved back. A predicate
taken after a wait would carry a newer gesture's authority. If the navigation opens or
closes a surface that moves focus, `currentIntent.handoff(() => changeSurface())` keeps
that synchronous focus transfer without renewing the original input generation; check
the predicate before starting it. If the synchronous work already moved focus, the
handoff adopts that destination instead of running the old focus move, and returns
false, so a caller that requires the surface change can decline. Leaf's navigation
helpers keep intent already; `threadActions.open` returns its completed destination
("Reading and opening Threads from a widget").

### Pointer presses

A handler that takes over a press, as a link that travels to a source line does, acts
only on `plainPress(event)`: the primary button with no modifier. A modified press keeps
its platform meaning, such as a new tab or a context menu.

A control whose label is the page's own words checks `reachedForWords(control)` in its
click handler: true means the press ended a text selection on the control, so the user
was taking the words rather than pressing. A container that takes a press anywhere on its
box, as an option card does, first asks `worksInside(event.target, container)`, which
returns the control or widget inside it the press was aimed at, or `null` where the
container is the aim.

A control that shows only part of its word, with the whole in its `title`, carries the
class `HOLDS_WORD`. A finger held on it reads the word, and releasing presses it. While
the press is held the control has `data-lf-held-word`, and the package's CSS shows the
whole word in that state as it does under keyboard focus.

A widget the user drags calls `dragging(this, true)` as the drag starts and
`dragging(this, false)` as it ends, is cancelled, or the widget disconnects. While any
drag is held, Leaf holds new state back from widgets and the page and paints it once the
last drag is released, so nothing moves under the pointer. The image that follows the
pointer is `motionPreview(label)`, an inert box carrying the dragged item's label.

A mechanical surface that must stop its motion before a gesture is handled subscribes
with `onUserInput(callback)`. Leaf calls it synchronously, in capture, for `pointerdown`,
`keydown`, `input`, `wheel`, `touchstart` and the window's `blur`; the callback observes
the event and does not claim it. Filter the events that belong to the surface, and call
the returned function when it disconnects. Keyboard commands still use `commands()`. A
drawing stroke dispatches the bubbling, composed `lf-inspect` event on its semantic
target before reading its coordinate frame; a moving visual handles it to freeze the
evidence being drawn on. Entering Draw mode alone does not inspect a visual.

## Text entry and drafts

A widget-owned composition box is Leaf's text field, `offer(TEXT_FIELD)`: a Markdown
editor that shows the draft the way the sent message will read and answers the textarea
members a box needs (`value`, the selection, `placeholder`, `readOnly`, `name`,
`aria-label`), firing `input` for the user's edits only. `TEXT_FIELD` is its tag, and
`TEXT_BOX` matches it and any native textarea, for code asking whether an element takes
typed paragraphs. A field has `:state(ready)` once its editor view exists. When it replaces a
reading surface, keep that surface in flow until the field is ready, so a connecting
empty field does not shrink the scroller and lose the user's place.

Wire the box with `wireInput(box, options)`. Enter submits on a physical keyboard and
Shift+Enter writes a newline; on a touch screen Enter stays a newline and the visible
control submits; Mod+Enter submits wherever a modifier key exists. The helper also owns
the submit control's state, image attachments and shortcut projections. Its options
include `sendBtn`, the submit control; `sends`, its action in words, such as
`"add and select option"`; `hint`, the placeholder; `save(value)`, called with the whole
draft on each edit; `send(text, raw, owns)`, called on submit with the trimmed and raw
draft and a predicate that is true while the box still holds that draft; `busy()` and
`hasContent(raw)`, which hold the submit back; and `paint()`, the widget's own drawing
from the box. A direct editor that needs more commands, such as Save and Cancel,
registers those rows on its box. Write `.value` only to seed the box before wiring it.

`wireInput` returns the box's one seam onto its draft, `sync`, since a box holds more
than its `.value`: an image pasted into one is kept as Markdown and shown as a thumbnail
beside the words. `sync.value()` reads the whole draft, `sync.load(value)` replaces it
(a stored record, a draft arriving from another tab, the emptiness a send leaves), and
`sync()` says the box's state changed. The send button, placeholder and the widget's
`paint` then repaint once, before the next frame shows.

A box's words are a draft, so they survive a reload, a new version and a closed tab, and
every tab of the page shares them. The widget keeps the draft under a context string
unique on the page, such as `option:` and its id. `loadDraft(ctx)` reads the words to seed
the box, or `null` where none stand. `saveDraft(ctx, text, payload)` records an edit, from
`save`, with an optional `payload` the send needs, such as the choice the words go with.
`watchDraft(ctx, callback, {input: box})` calls `callback(text, payload)` whenever the
draft changes other than by an edit in this box: another tab or view changing it, a send
emptying it (`text` is `null`), or a refusal giving the words back. The callback puts
the words in the box with `sync.load(text ?? "")`. `watchDraft` returns a function that
stops it; register it in `whileConnected`. `input` names the box the draft is written
in, so a live revision gives the user's caret back to the box that replaces it.
`sendDraft(ctx, owns, send)` sends, from `send`: while the stored draft is the one the
box shows and `owns()` returns true, it calls `send(attempt, payload)`, which dispatches
and returns the delivery promise, and it resolves to that delivery's result, or `null`
when it sent nothing. One `attempt` stands for one edit of the words, so a resend after a
reload names the same attempt. The draft empties as the send goes and settles once the
log accepts it, and a refusal gives the words back; the box follows both through
`watchDraft`. `clearDraft(ctx)` drops the draft, as Cancel does. `lf-options`' box
for adding an option (`lf-options-addition.js`) is the worked example.

For a CodeMirror editor, import `LeafEditorView` and use it in place of the dependency's
`EditorView` constructor. It keeps CodeMirror's state and editing API while placing focus
through Leaf and keeping editor reveals within the current document, and its navigation
extension survives retained states and complete `setState` replacements.

## Scrolling

### Reading regions

A pane declares `x-reading-role: pane` and keeps `x-content: markup`: exactly one direct
body element between an optional native `header` first and an optional native `footer`
last. Leaf lays out every package's pane by the same rules from the first paint; its
module registers the pane's body as a reading region, below.

Whether a pane's body scrolls is the workspace Layout's decision (`layouts.css`). Where
the window is large enough, the workspace is full-height: it fills the window and gives
its body a definite height, so a pane that is the body or a direct cell of it may shrink
below its content and scrolls its body. A pane inside a section of the body, or inside
another pane's body, flows with what holds it, and elsewhere every pane takes its
content's height. A module measures no minimum and chooses no posture.

`--lf-full-height: 1` on a box says its children are given a definite height to fill; it
does not inherit. While the workspace is full-height, the Layout sets it on `main` for
the body and on a grid of panes for its cells. A widget given that height keys its rules
on `@container style(--lf-full-height: 1)`, which asks the widget's parent; it fits what
it shows to the height, so the reader moves through the workspace rather than scrolling
it, declares `--lf-holds-height: 1` on each part it scrolls within that height, and sets
`--lf-full-height: inherit` on each box that passes the height on to its parts, as a
playground does down to its panes. A widget deeper in the body, in a section or a tab, is
not told, and takes its content's height.

A module that composes regions out of boxes it generates, such as a playground's controls
beside its preview, gives those boxes the pane rules by marking them
`data-lf-reading-role="pane"` and `data-lf-generated`, with the pane grammar of one header,
one body and one footer. A generated pane scrolls its body where its widget passes the
height on to it, and its widget draws the frame around it: the workspace's hairline grid
joins only panes a page wrote. These attributes are the module's to write, never an
author's (`page check` refuses `data-lf-` markup). Keep the package theme to placement
inside that grammar, such as track sizes and chrome; a package copy of the full-height
rules is a second posture decision that drifts from the Layout's. Generate boxes rather
than `lf-pane` elements: those are authored words the render gate pairs with the file.

`registerReadingRegion({id, host, body})` binds a region's id to its host and to the body
that scrolls whenever the theme makes it scroll. Focus in a pane's header or footer
selects the pane through its host. It throws while another region holds the id, so
register it in `whileConnected` and return its cleanup there; an element that returns
claims the id again. Containment follows rendered slots, so native conversation parts
nominated into a shadow reader belong to the region registered around their outlets. A
compound widget whose parts scroll independently registers each, taking a stable id from
`compoundReadingRegionId(owner, localName)`.

`scrollerFor(element)` is the box that scrolls an element: its reading region's scroller,
or `pageScroller`, the document's. `readingPosture(node)` is `"bounded"` while the
region's body is its own scroller, and `"flow"` otherwise.

Leaf records the user's place in each region as they scroll and restores it when the
region's layout moves under them. A composition that hides or reveals regions, such as a
tab switch, runs the change through `preserveReadingRegions(owner, change)`, which awaits
the promise `change` returns before the visible regions' places are restored. A region
that shows one subject of several in turn, as a trace's saved tree shows one
checkpoint's elements, replaces its body's contents inside
`showReadingSubject(id, subject, render)`, and Leaf returns the reader to their place in
each subject. `watchReadingRegionTransitions(listener)` hears these changes, and returns
a function that stops it: `{phase: "shift", shifted}` whenever a shown region's scroller
or width changes, the window's height changes, or the page's width changes (an entry with
no region); `before` and `after` around `preserveReadingRegions`; and
`leaving` and `showing` around `showReadingSubject`.

### Holding the reader's place

A widget that re-renders or resizes content holds the user's place with
`placeKeeper(scroller, {items, identity})` rather than by restoring a `scrollTop`.
`items` is a selector for the nodes that can mark a place and `identity(node)` the key
each is rendered under, so a keyed re-render hands the place to the replacement. The
keeper's `around(mutate)` brackets one synchronous mutation, which moves no scroller
itself; `take()` and `finish(hold, following)` bracket a mutation that spans tasks,
following it frame by frame while `following()` is true. Use it also for a synchronous
change in the page scroller where native anchoring does not keep the focused control
still. `runtime/user-place.js` describes which node holds the place.

A widget that remembers where the user was reading, in a view it hides and shows again,
keeps a place rather than an offset: `capturePlace()` reads the page's place as a
landmark in its own words, and `restorePlace(place)` returns to it however the page has
moved since.

A region whose rows the log or the clock decides holds them back while their growth
would move what the user sees, with a `HeldReading` built with its widget:
`new HeldReading(this, region, changed)`, where `region()` returns the nodes the reading
draws and `changed()` draws the widget again. `hold(reading)` returns the reading to draw:
the new one where it is the first, equals the one drawn last, or would move nothing seen;
otherwise the one drawn last, until that growth would move nothing seen. `release()` lets
the next reading draw whatever it moves, and `show()` releases and draws now. The wait
continues across a return.

### Scrolling to a destination

`scrollIntoView(target, {block, behavior})` lands on a destination: it reveals the
target in inner overflow, horizontally by the nearest edge, then places it through its
enclosing reading regions. `block` defaults to `start` and accepts `center`, `end` and
`nearest`. For a vertical navigation that keeps sideways reading, use
`scrollIntoReadingBand(target, holder, block, behavior)`, where `target` is an element or
a Range and `holder` is the element whose reading regions contain it; `block` is `start`,
`center`, `end` or `nearest`. It places the target in the innermost region's reading band
and reveals it in enclosing regions, across shadow roots, without changing horizontal
offsets. Both stop at the current document, including inside a live sample, where native
`Element.scrollIntoView` can scroll the containing page; use them for an explicit
arrival, since entering visible controls and ordinary repainting keep the current
position.

`scrollLimit(box)` is the furthest a box scrolls down, and `atScrollEnd(box)` says whether
it stands there. `landingInsets(scroller)` reads the `scroll-padding` a scroller declares
on each edge. `shownWindow({within, gap})` is the `DOMRect` of the window the page shows,
below Leaf's banner and above its bottom bar, narrowed to the rectangle `within` and
inset by `gap`.

### Sticky headers

A sticky header, a sticky box over the top of its scroller, has a stated height, sticks at
`var(--lf-top)`, and adds its height to `--lf-top` for what it stands over. Its holder
passes the value it met on under a second name, since a custom property cannot read
itself:

```css
.file { --lf-top-outer: var(--lf-top); }
.file > .head { position: sticky; top: var(--lf-top); block-size: var(--head-h); }
.file > .rows { --lf-top: calc(var(--lf-top-outer) + var(--head-h)); }
.file .row { scroll-margin-top: var(--head-h); }
.file > .head { --lf-head-inset: var(--head-pad); }
```

The rows' `scroll-margin-top` has a landing on a row arrive below the header. Focus needs
nothing declared: a focused row lands below the headers stacked over it, and a control in
a stuck header counts as shown where it sticks. Leaf also reads what passes under
`--lf-top` as off screen, for read acknowledgement, arrival checks and chrome placement.
A header whose controls stand below where it sticks may say how far (`--lf-head-inset`),
so a control revealed from elsewhere lands exactly there. Put the stacked value on a box
that does not itself scroll.

Leaf starts `--lf-top` again on every box that scrolls and does not itself stick,
`overflow: hidden` included, so a header inside one sticks at that box's top. A box a
package makes scroll also states `--lf-top: 0px` beside its overflow, so the restart holds
from the first paint. A box that scrolls with `scroll-padding` of its own states that room
as `--lf-landing-room-start` beside its `--lf-top-start`. A header sticks below its
scroller's top padding; to have it stand on the scroller's top edge, state
`--lf-top-start` at minus that padding and `--lf-top: var(--lf-top-start)`. A box that only
clips, such as a card rounding its corners, uses `overflow: clip`: a `hidden` box is a
scroller, and a header inside it would scroll off with the page rather than stick below
the banner.

### Sideways scrollers and container queries

A box a package makes scroll text sideways carries the class `lf-text-scroller`. An
overlay scrollbar paints over the box's lower edge and widens under the pointer, so while
the box scrolls, Leaf adds room for that bar below its last line.

A composition allocates a Leaf element's outer box. The package owns how the element's
contents use that allocation, based on its available inline size rather than the page
shell or a reading posture. Prefer intrinsic grid or flex layout. When the contents need a
discrete breakpoint, make the element a query container and apply the conditional rules
to its descendants. A rule for the host inside that block silently fails: an unnamed query
answers from the nearest ancestor container, and `body` is a container, so the rule
follows the page shell instead. Keep the host's own layout intrinsic, or put the
properties that change on a descendant layout box.

## Travel and history

A place on the page is an ordinary fragment link; Leaf follows it the way it travels to a
thread, clearing a panel that covers the page and opening whatever holds the element. A
widget that asks which of its parts a fragment names reads it with `fragmentTarget(hash)`,
as Leaf's own arrival does, so the widget opens the part the landing goes to: an id in
Leaf's chrome, in a message's markup, or on content a revision settled away names
nothing.

When Leaf travels to a target, such as a comment anchor or an ask, it first dispatches
`lf-reveal` on each ancestor of the target and the target itself, outermost first, with
`detail: {target, mayReveal, present, replacedView}`. A widget that folds content listens
for it and opens whatever holds `target`. `mayReveal` is the traveller's kept intent
("Delayed work"): an asynchronous listener checks it after each wait. A widget replacing a
mutually exclusive visible view opens it and calls `replacedView()` synchronously during
dispatch, and travel places that destination at once; expanding content within the
current view reports no replacement. A listener joins later layout through
`present(promise)`, and travel waits for those promises and reads fresh geometry for its
final placement. `lf-tabs` is the worked example.

A widget that adds same-document history entries adds them with `pushEntry(url)` and
`replaceEntry(url)`. It places the page itself at Back or Forward to one of its entries by
claiming that traversal with `claimTraversals(claim, {signal})`: `claim(url)` returns the
function that places the page for an entry of its own, or nothing for any other, and
aborting `signal` withdraws the claim. Every other traversal returns the user to where
they left the entry: its focus, selection and offset where Leaf recorded them, else the
browser's saved offset. Where the element an entry's fragment names is no longer shown,
the traversal reaches the widget holding it shut as `lf-reveal` and lands on it, as a
followed link does.

## Motion

A module that moves something calls `motion(element, keyframes, ms)` rather than
`element.animate`. The stylesheet's reduced-motion guard reaches CSS animation and
transitions but not a Web Animations call, so `motion` is where a user who asked for
stillness is answered: it returns `null` under that preference and before
`body[data-lf-presented]`. A caller treats no animation and a finished one as the same
state. `reducedMotion()`, `scrollBehavior()` and `onMotionPreferenceChange(listener)`
answer the same preference where a module has to branch on it; the last returns a
function that stops listening. Spend a duration only on letting the eye follow a box from
where it was to where it is: a result the module can already draw is drawn in the
gesture rather than after a wait.

`foldDuration()` reads how long a unit takes to leave, from the document-root
`--lf-motion-fold` stylesheet input; a widget retiring one calls it each time rather than
choosing a number or caching a value. The `--lf-motion-*` time inputs accept CSS
calculations and are set on the document root, including when the animated element lives
in a shadow tree.

A temporary yellow cue calls `backgroundFlash(element, ms)`. It supplies only the starting
tint; the browser fades to the element's live CSS background, including any hover or
theme change during the cue, and it shares `motion`'s gates and cleanup.

## Notices and spoken words

`notice(message)` shows a moment's news in Leaf's status line and announces it to screen
readers, such as the acknowledgement of a gesture the widget recorded. News that arrives
without the user's gesture passes `{background: true}` and waits behind what the user just
did; `{announce: false}` shows it without announcing it. `announce(message)` only
announces, for words the screen already shows.

`quietWord(element, word)` gives an element a word screen readers say and the screen does
not show, placed after the element's leading `<strong>` title; an empty word removes it.
Pass the element's whole quiet word each time. Leaf writes the quiet word of an element it
marks as rewritten, changed by the user, or reported, so a module writes quiet words only
on parts it builds.

## Content helpers

### Markdown

Registry `x-text-format: inline-markdown` formats direct authored text nodes; `markdown`
renders a data body's exact source as safe block Markdown. A block body is delivered
already formatted for first paint, and its canonical body record stays source, while
passages and comments read its visible words. A module adopts the prepared
`.lf-markdown-body` and uses `paintMarkdown(body, source)` for changing block prose.
`markdownSourceOffset(body, node, offset)` carries a rendered caret back to its offset in
the source. Inline formatting does not interpret strings a module assigns with
`textContent`.

The renderer loads lazily. `loadMarkdown()` loads it and resolves to whether it loaded.
Until it has, `inlineMarkdownFragment(text)`, `renderMarkdown(text)` and `paintMarkdown`
render the escaped source, so a module painting changing prose repaints once loading
completes, and `markdownReady()` says whether the renderer has loaded.
`inlineMarkdownFragment(text)` returns a fragment of inline Markdown, and
`renderMarkdown(text)` returns block Markdown as a safe HTML string for a template's
`unsafeHTML`. `markdownWords(text)` is the words a Markdown string renders to.

A changing numeric readout keeps surrounding text still with tabular numerals and a slot
wide enough for its largest value.

### Code

`syntax(source, lang)` colours code: it resolves to the code's tokens, `[{text, style}]` in
source order, where `style` holds CSS declarations from the page's syntax theme.
`synNodes(tokens)` turns tokens into nodes, and `tokenLines(tokens)` cuts them into one
array per line for a widget that numbers its lines. `lang` is one of the registry's
`$languages` names; `langForPath(path)` derives one from a file name, or returns
`undefined`, and `ensureSyntaxLanguage(lang)` loads a language before it is needed.
`highlightBlocks(root)` colours each `pre > code` block in `root`, `root` included, whose
`language-…` class names a language, as Leaf colours authored code.

Leaf adds a Copy button to each `pre > code` block in the page document itself. For any
other block of source text a widget draws, such as code in its shadow stage,
`copyBlock(block, source, noun)` returns a Copy button standing at the block's top right,
which copies `source()` when pressed; `noun`, such as `"code"`, names what it copies.
Call it once the styled block is connected, and append the button as a child of the
widget. The button shows while a pointer is over the widget or focus is inside it, which
a tap on the block gives a finger, and Enter on the block copies too.

### Text alignment

`alignText(before, after)` shows how one text became another: it returns runs
`{kind, text}`, where `kind` is `same`, `delete` or `insert`, aligned by words. The `same`
and `delete` runs join to `before`, and the `same` and `insert` runs to `after`; a very
large rewritten middle comes back as one delete and one insert. To align a rewritten
paragraph by sentences instead, pass an `Intl.Segmenter` with `granularity: "sentence"` as
the third argument.

### Image comparison

`compareImages(a, b)` compares two decoded images, such as an `HTMLImageElement` or an
`ImageBitmap` at natural size, which must not taint a canvas. It resolves to
`{width, height, changed, throughout, regions}`: the size compared, the larger of the two
images on each axis; the number of pixels that differ; whether they differ over most of
the image; and outlines `{x, y, width, height, side, kind}` drawn on the `before` image
(`a`) or the `after` image (`b`) around content that `changed` or `moved`.
`differenceKind(reading)` classifies a reading as `identical`, `throughout`, `slight` or
`areas`; `describeDifference(reading)` words it for the reader, and `countAreas(regions)`
counts the changed and moved areas, each once. `compareImagePixels(a, b)` reads the same
pair pixel by pixel and returns `{width, height, data}`, black RGBA whose alpha is opaque
where a pixel changed by as much as an outline needs, faint where it changed less, and
clear elsewhere, for use as a mask. The comparison is experimental; `lf-shot` is the
worked example.

### Media URLs

Resolve canonical `/media/…` paths from typed data with `scopedMediaUrl(path)` before
assigning them to generated images or links: it uses the page's public root across
ordinary and published pages, while the source keeps its canonical path.
`isCanonicalMediaUrl(href)` says whether a path is one of those canonical `/media/…`
paths.

### Icons

`iconElement(name, className)` and `iconTemplate(name, className)` draw Leaf's shared
icons, as an element and as a template. Use `"comment"` for a thread control, with
`lf-action-icon` inside an `lf-icon-action` button for the inherited stroke and hit area.
The icon is decorative; the button supplies its accessible label.

## Page readings

Each page reading below has a `watch…(owner, callback)` subscription; register it once for
each owner. `watchQuestions`, `watchQueues`, `watchThreads`, `watchReports` and
`watchHistory` share these rules. Each calls the callback on the microtask after
subscribing, then again, at most once per microtask, whenever the application publishes
a new reading, a drag starts or stops holding the page's projection back ("Pointer
presses"), or the page dispatches `PRESENTATION` ("Startup and presentation"). Several
of these in one task make one call. It pauses while the owner is away and reads
again on a return by the rule in "Connection lifetimes"; moving the owner within one
mutation batch keeps it. The returned function retires the subscription for good,
including queued reads and clock paints. Its `refresh()` reruns the same clock-tracked
reading synchronously, on the return when asked while the owner is away; use it when a
mechanical change, such as revealing held news or entering print, needs a repaint, since
calling the renderer directly would leave its new time readings outside the
subscription. Package semantic behavior subscribes to its own widget's state through its
controller.

### Reading asks and obligation queues

`readQuestions()` returns the publisher's immutable `{phase, all, user, unanswered}`, and
`watchQuestions(owner, callback)` calls `callback(readQuestions())`. `all` holds widget,
prose and stamped-version approval asks, including answered and withdrawn asks whose
sources remain. `user` selects open asks currently awaiting the user; `unanswered`
includes every open ask, even one held with the agent or hidden behind a later prompt.
Each record contains:

```js
{
  id: "widget:release-disposition", // or "reply:<agent-message-id>"
  source: {kind: "widget", id: "release-disposition", tag: "lf-options"},
  thread: null,
  message: null,
  prompt: {text: "When should this ship?", target: "release-context"},
  answer: {value: ["release-later"], event: null},
  status: "answered", // open | answered | answered_elsewhere | withdrawn
  end: null,          // a prose ask the agent ended: {detail, event}
  next_actor: null,   // user | agent | null
}
```

- A widget ask's `x-awaits.value` selects the state verb holding its typed answer, and
  `x-awaits.answered` independently decides completion. `answer` is `null` before answer
  content exists. Partial values can appear while `status` is `open`, and a completed
  empty selection has `answer.value === []`. `answer.event` names the admitted answering
  action, or is `null` for authored or carried state. An optional `x-question-context`
  wrapper contributes the ask's heading and arrival target without changing its identity
  or answer owner; `lf-ask` is one such wrapper.
- A prose ask has `source.kind === "reply"` and its agent message's id as `source.id`. Its
  answer holds the settling user message or reaction and its event reference. When the
  agent ends it with `leaf task end` instead, `answer` stays `null`, `status` is
  `answered_elsewhere` for `done` and `withdrawn` for `dropped`, and `end.detail` says
  where the answer is or why it no longer applies. A message carrying a widget ask does
  not also pose a prose ask.
- An approval ask has `source.kind === "approval"`, `source.version` naming the stamped
  version, and id `approval:v<version>`. Its answer is `null` until that version's approval
  settles it with typed `answer.value === true`; Undo reopens it. Its arrival reaches the
  banner's Approve control.

`thread` and `message` name a frozen widget ask's Thread and exact message, and a prose
ask's Thread and source message; both are null for page-widget and approval asks.
`prompt.text` can be `null` when a widget has no context heading; `prompt.target` names the
element or source the user can visit. Widget membership and completion change when an
authoritative reading is adopted, while pending widget input supplies its typed value at
once. A pending prose reply changes `next_actor` without inventing an admitted answer. A
required-version approval and its Undo update that ask at once, and a refusal restores the
admitted record. Page-widget asks follow the shown document version; frozen-thread asks are
page-wide.

`questionWords(question)` formats the answer of a widget, prose or approval ask, using the
widget family's `answerWords` ("Declared widget state"). It may return empty words and owns
no answer state. Display words are not canonical answer data.

`asksIn(region, asks = readQuestions().all)` selects the asks a region of the page holds:
each widget ask, not withdrawn, whose source element is `region` or stands under it. It is
the rule a side-list `lf-tabs` row and `lf-tally` read, so a page module that marks or
counts asks per card, section or item reads the same set: filter what it returns by
`status` for answered and open, or pass `readQuestions().user` for the asks waiting on the
user.

`questionActions.open(id)` resolves the current ask and follows its arrival, including to
earlier prose prompts and completed asks, and resolves to `false` when that ask is
unavailable. `questionActions.next({within, dir})` steps to the next ask waiting on the
user inside the element `within`, or the previous with `dir: -1`, as `q` steps through
Questions: from the one the user stands on, else from their place in document order,
coming round at either end. From outside the region it counts from the ask the user last
went to when that ask is in the region, so Tab from an ask to a control above it and
Enter steps on; otherwise from the first of the region's asks in sight, the next if it
waits and the one after if it is answered; and with none in sight it enters at the
region's edge. It resolves to whether it arrived. A control that calls it keeps focus where the user stands on a press
(`mousedown` default prevented), so a second press steps on. Answering uses the source's
declared command; asks expose no separate answer API.

`readQueues()` and `watchQueues(owner, callback)` supply the immutable
`{phase, questions, tasks, done}` that the Questions panel and `q` navigation use. Ask rows
have `kind === "ask"` and their canonical `ask` record, whose `source.kind` is `widget`,
`reply` or `approval`. To-do rows have `kind === "todo"`; response obligations and delivery
retries keep their own kinds. An ask is not also a to-do. Live rows carry their workflow or
`null`, plus `offers: {open, done}` for current command availability. Keep local filters and
ordering separate. `queueItemKey(row)` names a row across a move between lists, and
`queueTitle(row)` names its subject with the same conversation or ask title the Questions
panel uses.

`queueActions.open(key)`, with a row's `queueItemKey`, resolves the current row and follows
Leaf's arrival, and resolves to `false` for an unavailable row. `queueActions.done(key)`
returns an admission promise only for a current to-do on `questions`, one the agent opened
on the user, and `null` otherwise. A widget ask ends through its widget, a prose ask through
a reply, a settling reaction or the agent's `leaf task end`, and an approval ask through its version's banner approval.
Done removes its to-do optimistically, a duplicate cannot send again, and a refusal restores
the admitted reading; the server stays final. Collections keep their shape while `phase` is
`waiting`, `ready` or `offline`; activate only a ready collection.

### Work hierarchies

`readWork(scope)` reads a page-owned work hierarchy from the current publication. The page
declares `$work.widgets` roles: `scope` bounds one hierarchy; `goal` names a recorded
`state` attribute and its `done` and `stopped` values; `worker` names its recorded `state`,
its `running` and `retired` values, and an optional assignment attribute `on`; `evidence`
declares an observed-data seat. The result's `goals`, `workers`, terminal `leaves`,
`stopped` goals, `liveWorkers`, `running` and `quiet` workers keep their authored `element`
identities, and `done` counts the finished leaves. A stopped goal includes held threads and
outstanding interventions; a worker keeps when it was last heard and the remit of its
closest scope or goal. No dashboard stores another copy. `workRole`, `workElements`,
`directWorkElements` and `workAncestor` read the same role declaration for page-owned
adapters. Atlas in `examples/command-hub.page/` demonstrates the composition, and its
domain tags belong to that page.

### Page history and reports

A widget that renders the page's history declares `x-history` and reads it through
`watchHistory(owner, callback)`: the server's rows, newest first, each already carrying its
thread, whether it was undone, the name an agent's row is shown under as `agent`, and a
gesture's words as the document it was made in had them. The widget words those facts; it
does not fold the log. The callback's second argument is `{ready}`, whether the
authoritative application is ready. A widget that restores a tab-local reading keeps it
through preparation, then compares it with the ready history; a preparation reading is no
new baseline.

A widget an agent reports on reads the reports with `watchReports(this, callback)`, which
calls the callback with `reportSequence(this)` once the widget has painted every report it
holds. Each entry is one report about the widget, in log order, carrying `id`, `target`,
`source`, `action`, `detail`, its words as `text`, `ts`, and `disposition`: `effective`,
`outranked` by a newer report on its coordinate, or `settled` by a stamped version. Pass
`{kind: "thread", id}` in place of the element to read a Thread's reports, or call
`reportSequence()` with nothing to read every report. `saidAt(element)` is when the message
holding `element` was sent, or when the page was published for an element on the page, for
a widget that shows how long a worker has gone unheard.

### Reading version changes

`comparisonChanges(owner)` returns the changed descendant elements in the standing version
comparison, excluding the owner itself; omit the owner to read every changed element. It
reads the comparison's own record, not CSS markers, and returns an empty array with no
comparison standing. `watchComparison(owner, callback)` calls the callback when the owner
first connects and on each change to the comparison; on a return it calls only when the
comparison changed while the owner was away. A callback that throws is reported, and the
next change calls it again. Its returned function ends the watch. Use `comparisonChanges`
in the callback to update counts or other local presentations.

`revisionLabel(event.revision)` is the name the page gives the version an event was
recorded in, for a widget that lists its own history.

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
their geometry changed; call it after any such rendering change. An `x-visual.parts`
declaration may set `complete: true` where listing some drawn parts while leaving their
peers unaddressable would confuse a reader: the render check then requires a nonempty
authored list to name every registered part, and omitting the attribute keeps the visual
as one target.

## Threads

### Reading and opening Threads from a widget

`readThreads()` returns the same immutable `{phase, threads}` collection the Threads panel
reads, and `watchThreads(owner, callback)` calls the callback with it ("Page readings").
`threads` holds conversations; a bare reaction without a spoken turn is not a listed
Thread. Each widget keeps its own search, filter and order state and derives its displayed
rows from the collection. `threadTurns(thread)` selects a Thread's displayed turns, and
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
current vocabulary and `choices`, including labels, glyphs and standing reactions.

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
reply needs non-empty text. `setReaction` names the desired standing state, so a stale
control cannot invert a concurrent change: `false` withdraws a standing reaction, and the
token must be in the current layer's vocabulary on an addressable agent message.
`create` accepts `text`, an optional `anchor`, `attempt`, `holds`, `about`, `drawing` and
`suggestion`; empty text needs a drawing. It returns `{key, delivery}` synchronously, where
`key` is its minted or supplied attempt and `delivery` is the admission promise, and in a
ready reading its pending Thread appears at once. Creation needs no Thread reading; its key
selects the Thread when the collection becomes ready. Leaf's reply editors keep one durable
draft per Thread, and a package's own input keeps its own ("Text entry and drafts").

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
native instance, in this reader or in the fallback Threads panel. `mountThreadViews` stays
useful for optional mirrors of it.

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
whole conversation does. The package keeps layout, ordering, selection, scroll and
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
visible size changes with `HeldReading` ("Holding the reader's place"): hold only layout
identities and allocations, update surviving records and controls at once, and leave
retired slots their space with no interactive descendants. An owner that scrolls inside a
box of its own is a reading region: a page bounds it with `data-bound`, which registers it,
and a widget whose theme makes it scroll calls `registerReadingRegion`. At narrow widths
the owner stays where touch and the keyboard reach it. Omitting either consumer keeps the
core Threads and Questions routes.
