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

Import behavior helpers from `/runtime/widget-api.js`, or its portable part ("A
widget that also runs off Leaf"). Templates use the same API and `/vendor/lit.js`.
Don't import the runtime's
other modules, query Leaf's own chrome, or copy a runtime helper. Each helper is
described in the section for the task it serves, and its full contract is in the header
of the module `widget-api.js` re-exports it from. Every export is public for independent
and bundled packages alike;
there is no separate bundled-package tier. Kernel implementation and check-only
observations live outside this surface. A DOM helper takes the element it acts for as
its first argument.

From Lit, `widget-api.js` exports `render`, `html`, `nothing`, `repeat`, `keyed`,
`live`, `ref`, `createRef`, `classMap`, `styleMap`, `guard` and `unsafeHTML`. From
Preact Signals it exports `signal`, for private state a command's `when` reads
(`module-input.md`, "Command rows").

### A widget that also runs off Leaf

A widget that must also run on a page without Leaf's runtime, such as a chart another
app shows, imports only from `/runtime/portable-api.js`, the part of the helper
surface any document can load; `widget-api.js` re-exports all of it.
The retained-node and write helpers under “Rendering” are available through either
surface too.
The control constructors and template directives under “Generated controls”
are portable too: use the same offers and generated-word markers on either host. The host maps
`/runtime/` and `/vendor/` to a Leaf install with an import map of its own, as a Leaf
page does, and runs none of Leaf's runtime. Such a widget extends `HTMLElement` and
draws into the box the page gives it. Leaf hears from it only through standard events
it dispatches on itself and declarations it leaves on its elements, which a plain page
ignores:

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
  can't act, which is the availability Leaf reads. Where a key leaves the user is the
  row's `lands(from)` (`module-input.md`, "Command rows"), which only Leaf calls.
- A Copy control: a block's `data-lf-copy` and `lfCopy()` (`module-reading.md`,
  "Code"), and a quiet word: `data-lf-quiet` (`module-scroll-and-motion.md`,
  "Notices and spoken words"). Leaf finds these in the page and in the shadow stages
  it builds (`shadowStage`), not in a shadow root a page script attaches itself, where
  the widget shows neither.
- Comment targets: `registerVisualParts` (`module-annotations.md`, "Visual parts"),
  which only Leaf reads.
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
- Read the page's words with `says()` or `wrote()`, never `textContent`
  (`module-reading.md`, "Reading the page").
- Build injected controls with `offer()`, `offered` or `selectableOffer()`, a press
  that looks like Leaf's controls with `offerAction()` or `offeredAction` by its role, and
  label them with `relabel()` ("Generated controls").
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

A widget extends `LeafElement` and builds itself in `setup()` ("Drawing what a widget
reads"). Any other custom element starts `connectedCallback` with
`if (!once(this)) return;`, since `once(this)` is true only on the element's first
connection. Use `disconnectedCallback` only for teardown that must happen at once, such
as cancelling a grab or removing hoisted UI. A `LeafElement` that overrides either
callback calls the `super` method.

`quoted(element)` is true for a widget inside one whose `x-exhibit` declaration applies
(including its optional `when` condition), such as `lf-sample`. A quoted widget never
takes the user's edits, so check `quoted` before wiring a choice, a drag grip or
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
`reportFailure(element, error)` only reports. `describeFailure(error)` returns a
short message for any thrown value when the widget presents its own recovery.

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
return, keeping unchanged template nodes. Start asynchronous rendering in `updated()`
and extend `updateComplete` to wait for it, so presentation waits for it and reports a
rejection (module-state.md, "The widget controller"). Have `start` restore what its
cleanup removed, and when the element leaves, drop unfinished work but keep finished
nodes.

`Promise.race([work, aborted(signal)])` ends work when its signal aborts.

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
`afterPresentation(() => …)`. Pass work that starts now but need not delay
presentation, such as a slow load whose result moves nothing visible, to
`deferredArrival(promise)`. Checks and tests that wait for the page wait for both.
Before deferring work that resizes the widget, ask `growthIsSeen(element)`: if growing
now would move what the user sees, pass the work to the widget controller's
`present(promise)` instead, so it lands before presentation.

### First paint

The document paints its authored HTML while browser modules load. Each widget renders
when its module loads, then updates that same view from Leaf's readings. A control
that needs JavaScript or saved state waits only for its own behavior or reading;
native disclosures, links and authored content need no such wait.

- Return a widget's complete view from `LeafElement.render()`. The same rendering
  root handles fresh mounts, frozen messages and later updates; do not add a second initial
  renderer or transfer generated nodes between renderers.
- Size the widget in the package theme, including its initial authored drawing.
  A shadow template uses native slots for authored children, keeping their nodes and
  browser state in the light DOM.
- For an imperative widget that moves authored children into a generated container,
  use `holdAuthoredBody(host, box)`. An `x-patch: members` revision edits inside that box.
  A markup container without `x-views` leaves those children as independent evidence;
  revisions can change them without rebuilding its generated controls. A renderer that
  consumes its children's identities or attributes declares structural members or
  `x-views`, so changing those inputs rebuilds its view.
- Where the markup can't say how tall the drawing will be, declare `x-height` and add
  the class `lf-rendered` once drawn.
- A widget that shows one member at a time declares `x-views: {members: "selector"}`;
  the browser matches the selector against each direct authored child, including
  while HTML is still arriving. A selector that depends on descendants, such as
  `:has()`, can change membership as they arrive; use the child's own start tag for
  stable first-paint membership. Delivery carries the selector so the same browser
  owner shows the chosen member before modules load. Their native `hidden` attribute
  is view state.
  Read `viewMembers(holder)` for the canonical member list, including holders a module
  creates. Reading members or the opening choice changes no DOM. During setup, open the
  member `openingView(holder)` returns, and show each later member with
  `keepView(holder, member)`, which applies native visibility and remembers it for reload.
  Passing null shows none without forgetting the last member. During an exit animation,
  `keepView(holder, member, leaving)` keeps one outgoing member visible too; call it
  again without that member when the animation ends. Only the selected member is
  saved. Pass `null` as a second argument to get null where neither the address nor
  the tab names a member, and choose then. A holder whose members share the
  surrounding page's flow declares `--lf-views-flow: page` in its stylesheet (the
  default is `box`), so Layouts can seat a member's sidebar in the page margin.

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

A widget extends `LeafElement`, a `LitElement` that draws everything in one `render()`.
An `x-shadow` widget uses an ordinary shadow root; other widgets draw into
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
finishes later starts there and extends `getUpdateComplete`. `this.controller` is the widget
controller. Call `requestUpdate()` after a change Leaf can't see, such as revealing held
news, and `performUpdate()` to draw at once.

`LeafElement` is also exported from `portable-api.js`. On a plain host it draws
reactive properties with Lit's schedule, runs `setup()` once, pauses drawing while
away and draws the current properties on return. The host supplies its properties
and chooses its render root through `createRenderRoot()`; no registry creates a
shadow root there. Leaf supplies page readings, controllers, presentation readiness
and bound-data delivery only on a Leaf page.

### Retained nodes

To place nodes the module keeps, use `setChildren(parent, nodes)`, which moves only what
is out of order, or `move(parent, node, before)` for one node. Where nodes move between
parents, place every list at once with `setChildLists([[parent, nodes], …])`, outer
parents first. For a subtree the renderer owns entirely, `setRenderedChildren(parent,
nodes)` edits only changed text and keeps a text selection the user made in it.

These helpers, `render` and `repeat` keep the user's focus in a moved node, so a reorder
needs no `holdFocus`; a plain `append` or `insertBefore` of a node already in the page
blurs it. A moved editable loses its selection even under `moveBefore`, so a
custom element holding a Leaf editor view (`leafEditorView()`) calls the view's
`placeSelection()` from its `connectedMoveCallback`.

### Shadow stages and styles

Declare `x-shadow` when the user should quote and comment on the words a widget's
shadow root shows. A root attached any other way, as a vendored component or a page
script's own custom element attaches one, is opaque to comments.

For `x-shadow`, `LeafElement` creates the root, applies the shared stylesheet and
annotation support, and owns its Lit render. Return the template from `render()` and
use native slots for authored children. Read presentation inputs from the host and its
authored children; read decisions through `this.reading` and `this.state`.

An imperative renderer overrides `createRenderRoot()` to keep Lit out of its stage
and uses `shadowStage(host, nodes)`, never `attachShadow`; it applies
the same styles and returns the root. Stage a retained container and render into that
container. This API clears authored light children and supplies no slots, so read what
the renderer needs before staging. It removes children individually because clearing
a shadow host with `replaceChildren()` unloads WebKit's shadow-tree frames.

`shadowStage` also loads through `portable-api.js` on a plain host. There it stages
only the renderer's content; a Leaf page supplies its theme, annotation support and
page watches from outside the widget.

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
user stops it, such as playback, uses `nextAnimation(callback)` and
`cancelAnimation(id)` instead.

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

## Time axes

`axisTicks(from, to, duration, pxPerMs)` returns `{time, major, label, step}` ticks
for a visible time span, clipped to the duration. Times and steps are milliseconds;
major labels use seconds. `assignRows(items, start, end)` maps each item's `id` to a
zero-based row, arranging the extents returned by `start(item)` and `end(item)` so
overlapping extents use different rows. `textWidth(text, font)` measures text in
pixels using a CSS font shorthand. These helpers support a drawing before widget
upgrade as well as later updates.

## Contained examples and scoped appearance

`mountSample(frame, {template, window})` asynchronously mounts the authored template
with that id as a contained Leaf page in an iframe. `window` defaults to `false`;
`true` gives the child a full-window layout. Await the returned host, then its `ready`
promise before reading its presentation. `reset()` replaces the child's isolated
history, `setWindow(boolean)` changes its allocation, and `destroy()` releases the
child and its listeners; call it when the owning widget is disposed. A sample keeps
its own state and theme scope. Declare its template in the authored document, following
[live-samples.md](live-samples.md).

The host's `ready` promise belongs to its current child, and changes when loading
starts again. `on(type, callback)` returns an unsubscribe function. Its notices are
`loading`, `departed`, `arrived`, `input` (with the event's `{type}`), `current-location`
(with `{focused}`), and `height` (with `{height}`). Use `height` to size a block frame,
holding growth the user did not request as described in `module-scroll-and-motion.md`
until a `click`, `keydown` or `input` notice says they acted in the child.
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
`wear` on an inner owner replaces an outer owner's appearance for samples beneath it:
the nearest dressed ancestor owns a sample's appearance. This does not authorize writing
Leaf's computed geometry or styling another package's internals.

## Generated controls

`PRESSABLE` is the selector for a generated control that offers a press. Use it when
a compound widget delegates events to its own controls.

`offer(tag, className, label, inputType, pressable)` makes a native control, or a box of
controls, marked as Leaf-generated; the browser keeps its activation, focus and
accessibility. `inputType` is for an `input`. Pass `pressable: true` for a custom element
whose host implements `focus()` and `click()`. In a template, `<div
${offered("my-tools")}>` does the same, with an input's `type` binding placed before
`offered`. `offerElement(node, className, pressable)` marks an existing node.

A button that looks like Leaf's own controls is built by its role, so every control of
one kind wears one face: `offerAction(role, className, label, {title, action})`, or
`<button ${offeredAction(role, className, label, {action})}></button>` in a template.
`offerActionElement(node, role, className, label, {title, action})` applies the same
face, symbol and name to an existing node. The roles are:

- `"symbol"`, a press that shows the symbol of its `action`, one of Leaf's actions
  (`module-reading.md`, "Icons"), and draws it for you. Its tooltip and accessible name
  are the action's name, or `label` where that says more, such as "Retry loading the
  file"; `title` replaces the tooltip where it says more still, such as the key that
  does the same.
- `"word"`, a press that says what it does; `label` is its words. A toggle is a word
  with `aria-pressed`, which draws as selected.
- `"commit"`, the one press on a surface that commits the user's work.
- `"mark"`, a small symbol seated on the thing it acts on, at its corner, which names
  its `action` as a symbol does.
- `"inline"`, a press read as part of the line of words it stands in, such as a feed's
  "Show activity" or a quote's "Full quote"; `label` is its words, drawn in the accent
  at the line's size. Give one that announces news waiting `data-lf-news`, which draws
  it in the danger ink.
- `"row"`, one row of a list or menu, its words in the ink; the row under the pointer
  or the keys is washed. Give the row the list stands on, such as the step a timeline
  shows, `aria-current`, which draws it with the accent's stripe and tint.

`className` places the control; don't restyle its face. Use a symbol where a standard
symbol for the action exists, one readers know from other software, and words where
none does.
Shared control styles (`page-layout.md`, "Page CSS and Leaf's controls") apply to
generated controls too.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so build it with `selectableOffer(role, className, label)`, a focusable
span. Leaf presses any span it offers as a button as it does a button, so with the
role `"button"` Enter and Space press it, on a page with Leaf or without it, and the
widget declares no keys for that press; for another role, such as `"tab"`, the widget
declares its keys. In a template, use
`<span ${selectableOffered(role, className)}>${label}</span>`. To give it a role's
face, such as `"row"` for a list whose rows are the page's words, name the role last:
`selectableOffer(role, className, label, "row")` or `selectableOffered(role,
className, "row")`. Printing drops every
offer, so build structure that isn't injected UI, such as an editor's file, with
`el(tag, className, text)`.

`relabel(node, label, {says})` writes a generated control's label. Set `says: true`
where the label is the page speaking, as a pick mark reading "chosen" does, `false` for an
action word, and `"echo"` for a copy of words the page shows elsewhere, such as a
worker's name.

Words a module writes into the page need no marking: setting an element's
`textContent`, appending a paragraph or rendering a template leaves them the page's
words, which the user can comment on. A version comparison reads each version's source
rather than the page, so they never read as a change. To set apart words the widget
writes beside the author's, such as a count after an authored sentence, mark their
element with `generatedElement(node, {says})`, which takes the same answers; in a
template, write `<h2 ${generated({ says: true })}>`. `wrote()` then leaves them out,
and a comment's quote doesn't run across them into the author's words. Don't write the
`data-lf-gen`, `data-lf-said` or `data-lf-echo` attributes yourself.

For changing text, use `page-layout.md`, "Space for changing text";
the same `data-room` layout applies to authored and generated controls.

A widget can upgrade inside a shut panel where every box measures zero, so take
measurements inside `measure(element, take)`, which runs `take` once the element has a
box. After a view swap that rearranges a widget's contents without resizing it, call
`layoutChanged(element)`, which dispatches `LAYOUT` to the widgets and runtime readers
that measure what they hold, so they read again.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

`relabel`, `nameAction`, `namedAction` and `searchField` also load through
`portable-api.js` on a plain host. Load `/vendor/webawesome.esm.js` to upgrade a
search field's editor.

To fold content it may show again, set its `hidden` to `"until-found"`. Find-in-page,
fragment links and Leaf's travel still reach it and fire `beforematch` on it, where the
widget opens it (`module-scroll-and-motion.md`, "Travel and history"); print shows it
open. Take a folded element that is itself a Tab stop out of the Tab
order, since the fold hides only what it holds.
