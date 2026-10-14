# Authoring behavior modules

Read this file before writing browser behavior: a page script, a page-owned widget, or
a reusable package widget. All three use the same helpers, though only a
registry-declared widget gets a widget controller. Then read the sections your
behavior needs in the files beside this one:

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

[page-behavior.md](page-behavior.md) covers where a script goes, its imports, and how
long it lives across revisions. A widget's declarations are in
[packages.md, "A widget"](packages.md#a-widget), and its state and data sources in
[package-data.md](package-data.md).

## The helper surface

Import Leaf only from `/runtime/widget-api.js`. Don't import the runtime's other
modules, query Leaf's own chrome, or copy a runtime helper. Each helper is described in
the section for the task it serves, and the header of its module under `runtime/` has
the full contract. A DOM helper takes the element it acts for as its first argument.

From Lit, `widget-api.js` exports `render`, `html`, `nothing`, `repeat`, `keyed`,
`live`, `ref`, `createRef`, `classMap`, `styleMap`, `guard` and `unsafeHTML`. From
Preact Signals it exports `signal`, for private state a command's `when` reads
(`module-input.md`, "Command rows").

## What a behavior module owes

- Upgrade once with `once()`, and hold each connection's listeners, observers and
  registrations in `whileConnected` ("Upgrade", "Connection lifetimes").
- Check `quoted()` before wiring anything that sends input back ("Upgrade").
- Read the page's words with `says()` or `wrote()`, never `textContent`
  (`module-reading.md`, "Reading the page").
- Build injected controls with `offer()`, `offered` or `selectableOffer()` and label
  them with `relabel()` ("Generated controls").
- Keep the box the widget has at first paint ("First paint").
- Schedule paints with `frameFor`, observe size with `sizeObserver`, and write repeated
  values through `keeps` ("Scheduling paints", "Writes that change nothing").
- Record the user's choices only through the widget controller, and keep working state
  in `tabStore` (`module-state.md`, "The widget controller", "Tab-local working state").
- Register commands at upgrade (`module-input.md`, "Commands and keyboard routes").
- Move focus with `focusDestination`, never `element.focus()` (`module-input.md`,
  "Focus and layers").
- Animate with `motion`, never `element.animate` (`module-scroll-and-motion.md`,
  "Motion").

## Upgrade

Start `connectedCallback` with `if (!once(this)) return;`. `once(this)` is true only on
the element's first connection, so the widget is never built twice. Use
`disconnectedCallback` only for teardown that must happen at once, such as cancelling a
grab or removing hoisted UI, and hold everything else in `whileConnected`.

`quoted(element)` is true for a widget inside one the registry marks `x-exhibit`, such
as `lf-sample`. A quoted widget never takes the user's edits, so
check `quoted` before wiring a choice, a drag grip or anything else that sends input
back. Its presentation and view state still work.

When an upgrade fails, or one part of it, `failSoft(element, error, source)` replaces
the widget or part with an error box naming it, shows `source` beneath when given, and
reports a page error, which fails `page check`. The next `render` into the same
container, or the next `shadowStage` call, replaces the box. Where the widget shows a
failed part its own way and the rest keeps working, as `lf-diff` does for a file whose
patch it cannot draw, call `reportFailure(element, error)`, which only reports.

## Connection lifetimes

A revision or a thread can take a widget out of the page and put it back. After
`once(this)`, register `whileConnected(element, start)` once for what a connection
holds:

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

Leaf calls `start(signal)` now and on each return. When the element leaves, Leaf aborts
the signal and runs the cleanup `start` returned. If `start` throws, Leaf never calls
it again. `whileConnected` returns a function that ends the registration for good, for
an element that no longer needs it, such as one that has failed soft. Register what a
`watchData` callback uses before calling `watchData`.

Moving an element within the page doesn't count as leaving, since Leaf only decides
after reading the whole batch of DOM changes. When a revision replaces a widget, the old
element's cleanup runs before the new one's `start`, so a registration only one element
may hold, such as `registerReadingRegion`, passes to the replacement.

The controller's subscriptions, `watchData`, `watchComparison` and the page readings
pause while the element is away. On its return, Leaf calls a callback again only if its
reading changed meanwhile, or if the promise the callback returned had not settled when
the element left. A callback that throws or rejects is reported once and stays
subscribed. If `renderState` or a controller subscriber throws, the widget also shows its
fail-soft box. So return the promise of any paint that finishes later, drop unfinished
work when the element leaves but keep finished nodes, and have `start` restore what its
cleanup removed.

For a reading the module computes itself, build `const paint = readingPaint(element,
draw)` once, before `whileConnected`, and call `paint(key, ...args)` from `start`. It
calls `draw(...args)` only when `key` differs from the last key it drew or the last draw
was cut short; key authored content that never changes by its text. A failing `draw` is
reported as above and never makes `start` throw. `paint.refresh()` redraws the last
reading, `paint.forget()` makes the next call draw, `paint.owes(key)` says whether it
would, and `paint.stop()` retires it.

`Promise.race([work, aborted(signal)])` ends work when its signal aborts.

## Startup and presentation

The authored page shows at once, and `body[data-lf-presented]` is set once the page's
first complete presentation has rendered: from the server's state, or offline from the
authored page alone. Leaf turns off arrival transitions until then, so a widget needs no
guard against animating in, and an `x-shadow` widget that builds its shadow root with
`shadowStage` gets the same protection. Leaf doesn't hold back a dialog or popover, so
open one only after presentation or in response to a user gesture.

Letters and other printed keys typed during startup wait until `body[data-lf-upgraded]`,
when the page can take comments and drawings, and then run in order. A command whose
input is still loading declares `ready()` on its scope, row or route; the most specific
wins. While it returns false, that key and every later one keep waiting. A row with
`decision: true` waits until the page's saved state has loaded.

A module can listen on `document` for two startup events. `PRESENTATION` fires once,
when the page's complete layout is first in place, and is where UI drawn from element
geometry takes its first measurements. `PAGE_INTERFACE` fires at startup and again when a
new revision is applied in place; UI built from the authored structure rebuilds there
and passes any asynchronous preparation to `detail.present(promise)`.

A heavy renderer the widget loads only once the user has the page runs through
`afterPresentation(() => …)`. Work that should start now but need not delay
presentation, such as a slow load whose result moves nothing visible, goes to
`deferredArrival(promise)`. Either way, checks and tests that wait for the page also
wait for this work. Before deferring work that resizes the widget, ask
`growthIsSeen(element)`: if growing now would move what the user sees, pass the work to
the widget controller's `present(promise)` instead, so it lands before presentation.

### First paint

Upgrade should add behavior without moving anything: the widget's box at first paint is
the box it keeps. `leaf package check --render` reports a widget that moves as
`keeps-first-box` ([packages.md, "Seeing it"](packages.md#seeing-it)).

- Size the widget in the package theme under `html[data-lf-interactive]`, which Leaf
  sets before first paint wherever its runtime will run.
- A structure whose shape the log never changes, such as a row of count tiles, goes in
  `x-prepaint`. Delivery writes it into each occurrence, and the module removes it
  (`:scope > [data-lf-prepaint]`) in the same step that draws its replacement.
- A structure that depends on the instance's authored members or on its `tabStore`
  values (`module-state.md`, "Tab-local working state") goes in `x-initial`: the path of
  a committed classic script that calls
  `document.documentElement.lfInitial.register(tag, render)`. Delivery calls
  `render(host, {tabStore, offer, offerElement, keeps})` as soon as each host's markup
  arrives, so the widget first appears whole. It must be synchronous, fetch nothing and
  read nothing from the log; it may move authored nodes within the host, and returns the
  node references the module needs. The module calls `initialRender(host)` to get that
  result, drawn on demand for a host that arrived later, and adds behavior to those
  nodes. `x-initial` requires `x-upgrade: true` and excludes `x-prepaint`.
- Where the markup can't say how tall the drawing will be, declare `x-height` and add
  the class `lf-rendered` once drawn. For a drawing that can't fit any height,
  `page check --render` tells the author what height to state.
- A widget that shows one member at a time, as `lf-tabs` does, declares `x-views`.
  Before upgrade only the member marked `data-lf-opening` shows; on upgrade, open the
  member `openingView(holder, members)` returns, and record each member it shows with
  `keepView(holder, member)` so a reload reopens it.

## Rendering

### Template rendering

`render(template, container)` draws synchronously, so a gesture's result shows in the
same turn. Render only into containers the module generated, never into authored
children, and once `render` draws into a container, change its children only through
`render`. `repeat(items, identity, template)` keeps a row's nodes when rows reorder, but
rebuilds a row that moves to another `repeat`; place nodes you keep yourself as
"Retained nodes" describes. A widget that extends `HTMLElement` gets its state from
`widgetController` and keeps no reactive copy.

Bind a property the user can also change with `live`, as in `.value=${live(value)}`, so
a refused gesture restores the recorded value even when the template input is
unchanged. Don't bind an initial default onto a property the browser owns.

### Drawing what a widget reads (experimental)

`LeafElement` is a `LitElement` base class for a widget that draws everything in one
`render()`, into itself or into a generated part `createRenderRoot()` returns, never over
its authored children. One-time building goes in `setup()`, in place of `once(this)`.
`render()` reads through Leaf's readers: `this.reading` and `this.state`,
`this.data(input)` for a bound source, and page readings such as `readAsks`,
`reportSequence` or `ago`. The element redraws whenever anything it read changes. Return
a template, `nothing` when the render places retained nodes itself, or `noChange`.
`this.controller` is the widget controller. Call `requestUpdate()` after a change Leaf
can't see, such as revealing held news, and `performUpdate()` to draw at once.

### Retained nodes

To place nodes the module keeps, use `setChildren(parent, nodes)`, which moves only what
is out of order, or `move(parent, node, before)` for one node. Where nodes move between
parents, place every list at once with `setChildLists([[parent, nodes], …])`, outer
parents first. For a subtree the renderer owns entirely, `setRenderedChildren(parent,
nodes)` edits only changed text and keeps a text selection the user made in it.

These helpers, `render` and `repeat` keep the user's focus in a moved node, so a reorder
needs no `holdFocus`. A plain `append` or `insertBefore` of a node already in the page
blurs it. Where the browser lacks native `moveBefore`, as Safari does, an iframe inside a
moved node reloads. A moved editable loses its selection even under `moveBefore`, so a
custom element holding a `LeafEditorView` calls the view's `placeSelection()` from its
`connectedMoveCallback`.

### Shadow stages and styles

Build an `x-shadow` widget's shadow root with `shadowStage(host, nodes)`, never
`attachShadow`; it applies the theme's styles and returns the root. For a template,
stage a container with `shadowStage(host, [container])` and render into that container.

Wrap stylesheet text the module writes itself in `inBaseLayer(css)`, so its rules sit in
the theme's `lf-base` cascade layer, below Layouts, theme packages and the page's own
stylesheet.

### Scheduling paints

`frameFor(element, paint)` returns a function that schedules one call to `paint` for the
next render, however often it is called. It does nothing while the element is out of the
page, and leaving cancels a scheduled paint, which a return doesn't replay, so schedule
it again from `start`.

`nextRender(callback)` runs in the rendering pass under way, or the next frame's.
`nextFrame(callback)` always waits a frame, for a step such as an animation tick. Cancel
either with `cancelRender(id)`. The page doesn't count as settled until this work runs,
so motion that may run until the user stops it, such as playback, uses
`nextAnimation(callback)` instead. Cancel it with `cancelAnimation(id)` when the motion
stops or the element leaves.

`afterScript(callback)` runs a callback once when the current script finishes, for a
paint two steps of one script would otherwise trigger twice; pass the same function each
time, not a new arrow.

Use `sizeObserver(callback)` in place of `new ResizeObserver`, so the page counts as
unsettled while sizes change; pass `{counted: false}` for boxes that keep moving while
the page plays.

### Writes that change nothing

Writing a value a node already has still reaches screen readers and can repaint the
whole document. `keeps(node, name, value)` writes an attribute only when it would read
back differently; pass booleans and counts as they are, and `null` to remove it.
`keepsText(node, text)` and `keepsHidden(node, hidden)` do the same for words and
`hidden`. Write a measured length into a style as `layoutPx(length)`, which rounds to
layout's 1/64px; `atLayoutPrecision(length)` returns the rounded number.

## Generated controls

`offer(tag, className, label, inputType, pressable)` makes a native control, or a box of
controls, marked as Leaf-generated; the browser keeps its activation, focus and
accessibility. `inputType` is for an `input`. Pass `pressable: true` for a custom element
whose host implements `focus()` and `click()`. In a template, `<button
${offered("lf-btn")}>` does the same, with an input's `type` binding placed before
`offered`.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so build it with `selectableOffer(role, className, label)`, a focusable span
for which the widget supplies the keyboard behavior. `el(tag, className, text)` makes a
plain element for structure that isn't injected UI. Printing drops every offer, in a
shadow stage too, so build a box holding what the widget shows, such as an editor's
file, with `el`.

`relabel(node, label, {says})` writes a generated control's label. Set `says: true`
where the label is the page speaking, as a pick mark reading "chosen" does, `false` for an
action word, and `"echo"` for a copy of words the page shows elsewhere, such as a
worker's name. In a template, write `data-lf-gen="1"` plus `data-lf-said` or
`data-lf-echo` instead.

A widget can upgrade inside a shut panel where every box measures zero, so take
measurements inside `measure(element, take)`, which runs `take` once the element has a
box.

A label whose words change, such as a count, keeps one width so nothing beside it moves.
Put the words in the only child of an element whose `data-lf-room` lists every wording it
can show, one per line; the theme sizes the element to the widest, drawing the list
invisibly in its `::before`. Longer words are cut with an ellipsis, though the accessible
name keeps them whole.

After a view swap that rearranges a widget's contents without resizing it, await
`layoutChanged(element)` before restoring scroll. It dispatches `LAYOUT` to widgets that
measure what they hold, which pass their asynchronous work to `detail.present(promise)`.
A size change needs no call.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

To fold content it may show again, set its `hidden` to `HIDDEN`. Where the browser
supports `hidden="until-found"`, find-in-page and fragment links still reach the content
and fire `beforematch` on it, and the widget opens it there. Take a folded element that
is itself a Tab stop out of the Tab order.
