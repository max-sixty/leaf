# Authoring behavior modules

Use this reference for browser behavior in a page script, a page-owned widget, or a
reusable package widget. Read this file before writing one, then
the sections its behavior needs in the files beside it:

- [module-reading.md](module-reading.md): the page's words, elements and declarations,
  content helpers, and page readings such as asks and history;
- [module-state.md](module-state.md): the widget controller, declared state, data
  subscriptions, and editing a bound file;
- [module-input.md](module-input.md): commands and keyboard routes, focus, pointer
  presses, and text entry;
- [module-scroll-and-motion.md](module-scroll-and-motion.md): reading regions,
  scrolling, travel, motion, and notices;
- [module-annotations.md](module-annotations.md): margin contributions, visual
  parts, and Threads.

The same helpers serve each form. A semantic controller needs a registry-declared
widget; ordinary elements use the other helpers alone.

[page-behavior.md](page-behavior.md) owns script placement,
imports, and revision lifetime. [packages.md, "A widget"](packages.md#a-widget)
owns element declarations; [package-data.md](package-data.md) owns
state and source contracts. Add or change those declarations when the module needs
a new capability.

## The helper surface

`/runtime/widget-api.js` is the whole Leaf API a behavior module gets. A module imports
only from it: it does not reach into the runtime's other modules, query Leaf's own
chrome, or copy a runtime helper into itself. Each helper is documented once, in
this file or one beside it, in the section for the task it serves, and the header of
its module under `runtime/` states its full contract. A DOM helper takes the element whose behavior it implements.

Of Lit, the surface exports `render`, `html`, `nothing`, `repeat`, `keyed`, `live`,
`ref`, `createRef`, `classMap`, `styleMap`, `guard`, and `unsafeHTML`. Of Preact
Signals it exports `signal`, for private state a command's `when` reads
(`module-input.md`, "Command rows").

## What a behavior module owes

Each rule names the section that documents its helpers, and its file where that is
another one.

- Upgrade once with `once()`, and hold each connection's listeners, observers and
  registrations in `whileConnected` ("Upgrade", "Connection lifetimes").
- Check `quoted()` before wiring anything that carries input back ("Upgrade").
- Read the page's words with `says()` or `wrote()`, never `textContent`, and a widget's
  `<pre>` body with `bodyText()` or `dataBody()` (`module-reading.md`,
  "Reading the page").
- Build injected UI with `offer()`, `offered` or `selectableOffer()`, label it with
  `relabel()`, give a label whose words change the room of all of them with
  `data-lf-room`, and take measurements inside `measure` ("Generated controls").
- After a view swap that keeps the widget's outer box, await `layoutChanged()` before
  restoring scroll ("Generated controls").
- Keep the widget's first-paint box once the page presents ("First paint").
- Schedule paints with `frameFor` and observe size with `sizeObserver`, so checks and
  tests wait for that work too ("Scheduling paints"); write repeated state through
  `keeps` ("Writes that change nothing").
- Record durable user state only through the widget controller, and keep working state
  in `tabStore` (`module-state.md`, "The widget controller", "Tab-local working
  state").
- Register commands at upgrade (`module-input.md`, "Commands and keyboard
  routes").
- Place focus with `focusDestination`, never `element.focus()` (`module-input.md`, "Focus and layers").
- Animate through `motion`, never `element.animate` (`module-scroll-and-motion.md`, "Motion").

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
(`module-reading.md`, "Page readings") pause while their owner is away. On a return, a subscription calls
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

`body[data-lf-presented]` means the page's first authoritative presentation, or its
deliberate offline fallback, has rendered. Authored content is visible before then,
and Leaf disables its arrival transitions until the stamp. New comments and drawings
become available at `body[data-lf-upgraded]`, when the shown document and its anchors
are ready. Printed keys pressed earlier are held and handed to the command dispatcher
at upgrade. Ordinary UI commands use the shown document immediately. A scope, row,
or route that needs an incomplete reading declares `ready()`; rows and routes
override their scope. A false reading retains a printed key while startup waits
for saved state. Decision commands queue while saved state is loading; their owner's
availability still requires a complete reading. Offline presentation discards pending
keys and ends startup capture; it does not supply saved state. The shortcut bar names commands
available now; held keys have their own loading feedback. Packages need no arrival guard.
A package opens a dialog or popover only after the stamp or in response to a user
gesture; Leaf does not defer top-layer UI during startup. A declared `x-shadow` widget
gets the same arrival protection when it builds its shadow root with `shadowStage`
("Shadow stages and styles").

Startup dispatches events on `document`. `UPGRADE` fires when comment capture
is ready. `PRESENTATION` fires once, in the turn the
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
Work that should start at once but that presentation need not wait for, such as a
slow load whose landing moves nothing the reader sees, goes through
`deferredArrival(promise)` instead: it counts the running promise without waiting.
`growthIsSeen(element)` answers whether a change of the element's size now would move
what the user sees; where it would, register the work with the widget controller's
`present(promise)` instead, so it lands before the page presents.

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
  in `tabStore` (`module-state.md`, "Tab-local working state"), declare `x-initial` instead: the rooted
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
`lf-base` cascade layer, below Layouts, theme packages, semantic state and the page's
own stylesheet.

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
now when the element has a box and otherwise the first time it does.

A label whose words change, such as a count, keeps one width for all of them, so a
change moves nothing beside it. Put the words it can show, one per line, in
`data-lf-room` on an element whose one child holds the words, and write the words into
that child. The theme draws the element as an inline block as wide as its widest room
line in its own face, and no wider than its container; the room is invisible and stays
out of its text and accessible name. The element keeps its own `::before` free for the
room. Words wider than the room are cut with an ellipsis rather than widening it, so
list the longest words the label will show; cut words stay whole in the accessible
name.

After a view swap that rearranges descendants without resizing the widget's outer box,
call `layoutChanged(element)` and await its promise before restoring scroll. It
dispatches the bubbling, composed `LAYOUT` event, which a widget that measures what it
holds listens for; a listener joins asynchronous work through the event's
`detail.present(promise)`. A size change needs no call, since a `sizeObserver` hears it.

`searchField(className, {name, label, placeholder = label})` builds a search or filter
field with the shared frame, accessible label, native editor and Clear. The caller owns
its query and results. Put an auxiliary reading such as a match count in its `end` slot,
holding the room of its longest value as above.

A widget folds content it may show again by setting its `hidden` to `HIDDEN`. Where the
browser supports `hidden="until-found"`, find-in-page and fragment links still reach the
content and fire `beforematch` on it, and the widget opens it there; elsewhere the
content is plainly hidden. A folded element that is itself a Tab stop stays one, so the
widget withdraws it.
