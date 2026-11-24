# Authoring behavior modules

Read this file before writing browser behavior: a page script, a page-owned widget, or
a reusable package widget. All three use the same helpers; only a registry-declared
widget gets a widget controller. Then read the sections your behavior needs in the
files beside this one:

- [module-reading.md](module-reading.md): the page's words, elements and declarations,
  content helpers for Markdown, code, images and icons, and page readings such as
  obligations and history;
- [module-state.md](module-state.md): the widget controller, declared state, data
  subscriptions, and editing a bound file;
- [module-plain-elements.md](module-plain-elements.md): a widget written as a plain
  custom element, which Leaf drives by properties and events;
- [module-input.md](module-input.md): commands and keyboard routes, focus, pointer
  presses, and text entry;
- [module-previews.md](module-previews.md): the preview Leaf shows of an element the
  user points at, tabs to or holds;
- [module-controls.md](module-controls.md): the controls a widget builds, and marking
  the words it writes into the page;
- [module-scroll-and-motion.md](module-scroll-and-motion.md): reading regions,
  scrolling, travel, motion, and notices;
- [module-annotations.md](module-annotations.md): margin contributions, visual
  parts, and Threads.

[page-behavior.md](page-behavior.md) covers where a script goes, its imports, and how
long it lives across revisions. A widget's declarations are in
[packages.md, "A widget"](packages.md#a-widget), and its state and data sources in
[package-data.md](package-data.md).

## The helper surface

Import behavior helpers from `/runtime/widget-api.js`, or its portable part ("A
widget that also runs off Leaf"), and Lit's templates from `/vendor/lit.js`.
Don't import the runtime's
other modules, query Leaf's own chrome, or copy a runtime helper. Each helper is
described in the section for the task it serves, and its full contract is in the header
of the module `widget-api.js` re-exports it from. Every export is public for independent
and bundled packages alike. A DOM helper takes the element it acts for as its first
argument.

`/vendor/lit.js` is Lit's own module, the one path its names come from, such as
`render`, `html`, `svg`, `nothing`, `repeat`, `keyed`, `live`, `ref`, `createRef`,
`classMap`, `styleMap`, `guard`, `unsafeHTML` and `noChange`. From Preact Signals
`widget-api.js` exports `signal`, for private state a command's `when` reads
(`module-input.md`, "Command rows").

### A widget that also runs off Leaf

A widget reused off Leaf imports `/runtime/portable-api.js`, re-exported by
`widget-api.js`. The portable helpers are
[that file's exports](../../../browser/runtime/portable-api.js): each loads on a page
without Leaf, where `widget-api.js` can't. The host maps `/runtime/` and `/vendor/` to
a Leaf install with its own import map and gives the element its drawing box. For the
widget's look it links the layer's `portable.css`, served beside `/widgets/`
(`packages.md`, "Styles and composition"). Use `LeafElement` ("Drawing what a widget
reads") or extend `HTMLElement`; a plain element that only records state and reads
bound data needs no import at all (`module-plain-elements.md`). Leaf adds its services
through events and element declarations that a plain host can ignore:

- Drawing under way: `this.dispatchEvent(new PendingTaskEvent(promise))`, the Web
  Components Community Group's `pending-task` protocol. Leaf holds the page's
  presentation until `promise` settles, as it does for `present(promise)`
  (`module-state.md`, "The widget controller").
- A failure: `failSoft` and `reportFailure` dispatch an `error` event ("Upgrade"),
  which Leaf reports to the author as the page's error.
- Keys: an element's `lfCommands` and `commandsChanged` (`module-input.md`, "Commands
  and keyboard routes"). A plain page binds none and advertises none. A button that must
  work off Leaf makes its own press, from its own click listener: its row names it as
  `control` and has no `run`, and the widget draws it `aria-disabled` while the press
  can't act, which is the availability Leaf reads. Where a key takes the user is the
  row's `lands(from)` (`module-input.md`, "Command rows"), which only Leaf calls.
- A preview: an element's `lfPreview()` (`module-previews.md`). A plain page
  shows none.
- A Copy control: a block's `data-lf-copy` and `lfCopy()` (`module-reading.md`,
  "Code"), and a quiet word: `data-lf-quiet` (`module-scroll-and-motion.md`,
  "Notices and spoken words"). Leaf finds these in the page and in the shadow stages
  it builds (`shadowStage`), not in a shadow root a page script attaches itself, where
  the widget shows neither.
- Comment targets: `data-lf-part` marks or `registerVisualParts`
  (`module-annotations.md`, "Visual parts"), which only Leaf reads.
- Words for a listener: `announce(message)` (`module-scroll-and-motion.md`, "Notices
  and spoken words"), which only Leaf says.
- State only this tab keeps, in `tabStore`, which keeps nothing on a plain page: a read
  there answers null.

`lf-chart` and `lf-code` in the default package, `lf-diagram`, `lf-motion` and
`lf-timeline` are the worked examples.

## What a behavior module owes

This is what a widget owes; a page script owes only what `page-behavior.md`, "A page
script", lists.

- Build once, in a widget's `setup()` or behind `once()` in any other element, and
  hold each connection's listeners, observers and registrations in `whileConnected`
  ("Upgrade", "Connection lifetimes").
- Check `quoted()` before wiring anything that sends input back ("Upgrade").
- Read the page's words with `says()`, and name a part with `named()`,
  never with `textContent` (`module-reading.md`, "Reading the page").
- Build injected controls with `offer()`, `offered` or `selectableOffer()`, a press
  that looks like Leaf's controls with `offerAction()` or `offeredAction` by its role, and
  mark the words they write with `generatedElement()` (`module-controls.md`).
- Keep the widget's visible geometry stable as its state updates ("First paint"), and
  meet the rest of [interface-goals.md](interface-goals.md).
- Schedule paints with `frameFor`, observe size with `sizeObserver`, and write repeated
  values through `keeps` ("Scheduling paints", "Writes that change nothing").
- Keep each kind of state where `module-state.md`, "Where a widget keeps its state",
  puts it: record what the user makes through the widget controller, and keep how they
  look at the widget in `tabStore`.
- Declare commands at upgrade, as an element's `lfCommands` (`module-input.md`,
  "Commands and keyboard routes").
- Move focus with `focusDestination`, never `element.focus()` (`module-input.md`,
  "Focus and layers").
- Animate with `motion`, never `element.animate` (`module-scroll-and-motion.md`,
  "Motion").

## Upgrade

A `LeafElement` builds itself in `setup()` ("Drawing what a widget reads"). Any other
custom element starts `connectedCallback` with
`if (!once(this)) return;`, since `once(this)` is true only on the element's first
connection, or with a guard of its own where it imports nothing. Use `disconnectedCallback` only for teardown that must happen at once, such
as cancelling a grab or removing hoisted UI. A `LeafElement` that overrides either
callback calls the `super` method.

`quoted(element)` is true for a widget inside one whose `exhibit` declaration
applies (including its optional `when` condition), such as `lf-sample`. A quoted widget
never takes the user's edits, so check `quoted` before wiring a choice, a drag grip or
anything else that sends input back. Its presentation and view state still work.

When an upgrade or one part of it fails, `failSoft(element, error, source)` replaces
the widget or part with an error box naming it, with `source` beneath when given, and
dispatches an `error` `ErrorEvent` on the element, bubbling and composed, or on the
window while the element is out of the document. Leaf reports it as a page error
naming the widget, which fails `page check`. The widget's next draw removes the box,
a template render into the element included.
A native renderer that retains its nodes can register `placesFailure(element, place)`
to place the box beside them: `place(box)` returns true when it handles the box, and
the renderer removes it when the failed content recovers. An element has one placer,
which registering again replaces. Where the widget shows a
failed part its own way, as `lf-diff` does for a patch it cannot draw,
`reportFailure(element, error)` only reports.

## Connection lifetimes

A revision or a thread can take a widget out of the page and put it back. In
`setup()`, or after `once(this)`, register `whileConnected(element, start)` once for
what a connection holds:

```js
schedulePaint = frameFor(this, () => this.measure());

setup() {
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
it again. `whileConnected` returns a function that ends the registration for good.

Moving an element within the page doesn't count as leaving. When a revision replaces a
widget, the old element's cleanup runs before the new one's `start`, so a registration
only one element may hold, such as `registerReadingRegion`, passes to the replacement.

A `LeafElement` draws nothing while it is away and draws the current reading once on
return, keeping unchanged template nodes. Have `start` restore what its cleanup removed,
and when the element leaves, drop unfinished work but keep finished nodes.

## Revisions

A revision that changes anything in a widget's markup replaces the whole widget with a
new element, and the user loses what they had open in it. A module that builds beside
the widget's authored content, and leaves every node the author wrote where it is,
declares `static lfPatch = "members"` on its element's class. Leaf then keeps the
widget and patches the markup inside it as it patches the rest of the page: it writes
the words, attributes and elements the revision changed, and puts each element's
children back in the order the revision gives them.

Inside such a widget Leaf still replaces two things whole when the revision changes
anything in them. One is a widget with a module of its own, unless that module's class
declares `lfPatch` too. The other is an element that no longer holds every node the
author wrote in it, the whitespace between its children included. `setChildren` removes
that whitespace ("Retained nodes").

A module that moves its authored members itself, as `lf-board` orders its cards from
its state, declares nothing. With `lfPatch`, a revision can leave the members in the
order it gives them, without redrawing the widget. Without it, the revision replaces
the widget, the new widget's first render places the members, and a control the module
keyed with `data-lf-carry` takes the user's focus back (`module-input.md`, "Focus and
layers").

Leaf also replaces a widget that declares `lfPatch` when a revision changes what its
module drew from, which it takes to be the element's own attributes. A module that also
draws from which children it has, or from their attributes, as a tab strip shows each
tab's `label`, declares `content: members` or `views`. Leaf then also replaces the
widget when a direct child is added, removed, reordered or given other attributes.
Without either declaration the module keeps its first drawing of a child the revision
changed. Leaf compares only each direct child's tag and attributes, and a revision
doesn't redraw a widget it keeps. So a module that draws from what its children hold,
or can declare neither, reads them again when they change: `lf-pane` watches its
children with a `MutationObserver`, and a `LeafElement` calls `requestUpdate()` from
one. A widget that draws its own content (`content` `data` or `empty`) is always
replaced.

## Startup and presentation

The authored page shows at once, and `body[data-lf-presented]` is set once the page's
first complete presentation has rendered, from the server's state or, offline, from the
authored page alone. Leaf turns off arrival transitions until then, in shadow stages
too, so a widget needs no guard against animating in. Leaf doesn't hold back a dialog
or popover, so open one only after presentation or in response to a user gesture.

Printed keys typed during startup wait until `body[data-lf-upgraded]` and then run in
order. A command whose input is still
loading declares `ready()` on its scope, row or route, the most specific winning; while
it returns false, that key and every later one keep waiting. A row with
`decision: true` waits until the page's saved state has loaded.

A module can listen on `document` for two startup events. `PRESENTATION` fires once,
when the page's complete layout is first in place; UI drawn from element geometry takes
its first measurements there. `PAGE_INTERFACE` fires at startup and again when a new
revision is applied in place; UI built from the authored structure rebuilds there and
passes any asynchronous preparation to `detail.present(promise)`.

A page script reaches a widget's methods only once the widget has upgraded.
`whileInterfaceConnected(element, {declare, connect})` runs `declare()` once, for what
the widget accepts once per lifetime, then `connect(signal)` at the first
`PAGE_INTERFACE`, holding presentation until it returns, and again at once on each
reconnection; the cleanup `connect` returns runs as the element leaves. A playground's
page script is the worked example (the playground package's author instructions,
"Stateful previews").

Run a heavy renderer that can wait until the user has the page through
`afterPresentation(() => …)`, or until they come near its element through
`whenNear(element, () => …)`, which returns the step that stops waiting. Pass work that starts now but need not delay
presentation, such as a slow load whose result moves nothing visible, to
`deferredArrival(promise)`. Checks and tests that wait for the page wait for the work
each has started; `page check --render` starts what `whenNear` holds.
Before deferring work that resizes the widget, ask `growthIsSeen(element)`: if growing
now would move what the user sees, pass the work to the widget controller's
`present(promise)` instead, so it lands before presentation.

### First paint

Each widget renders when its module loads, then updates that same view from Leaf's
readings. A control that needs JavaScript or saved state waits only for its own
behavior or reading; native disclosures, links and authored content need no such wait.

- Return a widget's complete view from `LeafElement.render()`. The same rendering
  root handles fresh mounts, thread messages and later updates; do not add a second
  initial renderer or transfer generated nodes between renderers.
- Size the widget in the package theme, including its initial authored drawing.
  A shadow template uses native slots for authored children, keeping their nodes and
  browser state in the light DOM.
- Where the markup can't say how tall the drawing will be, declare `height` and add
  the class `lf-rendered` once drawn.
- A widget that shows one member at a time declares `views: {members: "selector"}`;
  the browser matches the selector against each direct authored child, including
  while HTML is still arriving. A selector that depends on descendants, such as
  `:has()`, can change membership as they arrive; use the child's own start tag for
  stable first-paint membership. Open and keep its members as `module-state.md`, "State
  only this tab keeps", describes. A holder whose members share the surrounding page's
  flow declares `flow`, as its members do, so a member's wide blocks and sidebar take
  the page's room.

## Rendering

### Template rendering

`render(template, container)` draws synchronously, so a gesture's result shows in the
same turn. Render only into containers the module generated, never into authored
children, and once `render` draws into a container, change its children only through
`render`. `repeat(items, identity, template)` keeps a row's nodes when rows reorder, but
rebuilds a row that moves to another `repeat`; place nodes you keep yourself as
"Retained nodes" describes. A widget keeps no reactive copy of its state; it reads it
again in each render.

Bind a property the user can also change with `live`, as in `.value=${live(value)}`, so
a refused gesture restores the recorded value even when the template input is
unchanged. Don't bind an initial default onto a property the browser owns.

### Drawing what a widget reads

`LeafElement` is a `LitElement` that draws everything in one `render()`.
A `shadow` widget uses an ordinary shadow root; other widgets draw into
themselves or a generated part `createRenderRoot()` returns, never over authored
children. One-time setup goes in `setup()`, before the first render; work needing the
rendered nodes goes in `firstUpdated`. A `setup()` that throws shows its failure and
the widget draws nothing after it.

`render()` reads through Leaf's readers: `this.reading` and `this.state`, the
property a bound source sets (module-state.md, "Bound data and projections"), and page
readings such as `readObligations`,
`reportSequence` or `ago`. The element redraws whenever anything it read synchronously
changes, parents before children; DOM reads and reads after an `await` are not
tracked. Return a template, `nothing` when the render places retained nodes itself, or
`noChange`. Work that reads what the render drew goes in `updated()`, and drawing that
finishes later starts there and extends `getUpdateComplete` (`module-state.md`, "The
widget controller"). Call `requestUpdate()` after a change Leaf can't see, such as
revealing held news, and `performUpdate()` to draw at once.

`LeafElement` is portable: a plain host supplies reactive properties and chooses
`createRenderRoot()`. Leaf adds page readings, controllers, presentation and
bound-data delivery. `this.defer()` holds drawing through a synchronous rewrite; its
idempotent release draws current properties.

Portable focus, scrolling and controls use the document's native behavior; Leaf
adds reading regions and chrome styling. `langForPath` reads shipped defaults on
a plain host and its composed language map on Leaf. `beginWalk` declares navigation
position; only Leaf supplies the status presentation.

### Retained nodes

To place nodes the module keeps, use `setChildren(parent, nodes)`, which makes `nodes`
the parent's only children, moving what is out of order and removing every other child,
the whitespace between authored elements included, or `move(parent, node, before)` for
one node. Where nodes move between parents, place every list at once with
`setChildLists([[parent, nodes], …])`, outer parents first. For a subtree the renderer
owns entirely, `setRenderedChildren(parent, nodes)` edits only changed text and keeps a
text selection the user made in it.

These helpers, `render` and `repeat` keep the user's focus in a moved node, so a reorder
needs no `holdFocus`; a plain `append` or `insertBefore` of a node already in the page
blurs it. A moved editable loses its selection even under `moveBefore`, so a
custom element holding a Leaf editor view (`leafEditorView()`) calls the view's
`placeSelection()` from its `connectedMoveCallback`.

### Shadow stages and styles

Declare `shadow` where the user should quote and comment on the words a widget's
shadow root shows; a root attached any other way is opaque to comments.

For `shadow`, `LeafElement` creates the root, applies the shared stylesheet and
annotation support, and owns its Lit render. Return the template from `render()` and
use native slots for authored children. Read presentation inputs from the host and its
authored children; read decisions through `this.reading` and `this.state`.

An imperative renderer overrides `createRenderRoot()` to keep Lit out of its stage
and uses `shadowStage(host, nodes)`, never `attachShadow`; it applies
the same styles and returns the root. Stage a retained container and render into that
container. This API clears authored light children and supplies no slots, so read what
the renderer needs before staging.

On a plain host `shadowStage` stages only the renderer's content; a Leaf page supplies
its theme, annotation support and page watches from outside the widget.

Wrap stylesheet text the module writes itself in `inBaseLayer(css)`, so its rules sit in
the theme's `lf-base` cascade layer, below Layouts, theme packages and the page's own
stylesheet.

### Scheduling paints

`frameFor(element, paint)` returns a function that schedules one call to `paint` for the
next render, however often it is called. It does nothing while the element is out of the
page, and leaving cancels a scheduled paint, so schedule it again from `start`.

`nextRender(callback)` runs in the rendering pass under way, or the next frame's, and
`nextFrame(callback)` always waits a frame; cancel either with `cancelRender(id)`. The
page doesn't count as settled until this work runs, so motion that may run until the
user stops it, such as playback, calls the browser's `requestAnimationFrame` instead.

Use `sizeObserver(callback)` in place of `new ResizeObserver`, so the page counts as
unsettled while sizes change; pass `{counted: false}` for boxes that keep moving while
the page plays. Have its callback schedule a paint from `frameFor` rather than draw:
a drawing that settles inside a size delivery lets Leaf present the page there, which
moves boxes the browser has just measured, and the browser reports a ResizeObserver
loop that `page check` counts as a fault.

### Writes that change nothing

Writing a value a node already has still reaches screen readers and can repaint the
whole document. `keeps(node, name, value)` writes an attribute only when it would read
back differently; pass booleans and counts as they are, and `null` to remove it.
`keepsText(node, text)` does the same for words. For a flag such as `hidden`,
`toggleAttribute(name, force)` writes only when the flag changes, where the `hidden`
setter rewrites the attribute on every set. Round a measured length to layout's 1/64px,
as `Math.round(length * 64) / 64`, before writing it into a style, so a measure that
jitters below that writes nothing new.

## Contained examples and scoped appearance

`mountSample(frame, {template, window})` asynchronously mounts the authored template
with that id as a contained Leaf page in an iframe; `{source}` in place of `template`
mounts a complete HTML document the module passes (`live-samples.md`, "Generated
samples"). `window` defaults to `false`;
`true` gives the child a full-window layout. Await the returned host, then its `ready`
promise before reading its presentation. `reset()` replaces the child's isolated
history, `setWindow(boolean)` changes its allocation, and `destroy()` releases the
child and its listeners; call it when the owning widget is disposed. A sample keeps
its own state and theme scope. Declare its template in the authored document, following
[live-samples.md](live-samples.md).

The host's `ready` promise belongs to its current child, and changes when loading
starts again. `on(type, callback)` returns an unsubscribe function. Its notices are
`loading`, `departed`, `input` (with the event's `{type}`), `current-location` (with
`{focused}`), and `height` (with `{height}`). The host counts the child's arrival in
the page's readiness itself. Use `height` to size a block frame, holding
growth the user did not request as described in `module-scroll-and-motion.md` until a
`click`, `keydown` or `input` notice says they acted in the child.
`restoreCurrentLocation()` returns focus to the child's last focused control;
`showThread(id, {surface, status, signal})` opens a child Thread with an AbortSignal
for the owning gesture's lifetime. `surface: "panel"` selects the child's panel,
with `status` selecting its thread list; otherwise the child's own thread presentation
opens the conversation. Showing a child Thread does not take focus. These operations
wait for the current child's `ready` and reject if that child is replaced or destroyed.

`wear(element, {attributes, properties})` applies a complete scoped appearance: each
map contains its CSS attributes or custom properties, and a later call removes members
missing from the replacement. Use it on an element the package owns, with the public
style inputs from [package-themes.md](package-themes.md). The same appearance reaches
contained samples under that element, including their first paint and resets. Calling
`wear` on an inner owner replaces an outer owner's appearance for samples beneath it.
This does not authorize writing Leaf's computed geometry or styling another package's
internals.
