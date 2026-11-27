# Authoring behavior modules

Read this file before writing browser behavior: a page script, a page-owned widget, or
a reusable package widget. [page-behavior.md](page-behavior.md) covers where a script
goes, its imports, and how long it lives across revisions. A widget's declarations are
in [packages.md, "A widget"](packages.md#a-widget), and its state and data sources in
[package-data.md](package-data.md).

## The interface

A widget is a custom element that Leaf drives from outside. On an element whose tag
declares `verbs` or `inputs`, Leaf sets the widget's state and its bound data as
properties, and the element answers with events: one records a gesture, one takes it
back, and others say that it is drawing, holding something for the user or failing.
[module-plain-elements.md](module-plain-elements.md) gives each property, event and
mark of that protocol. A widget that only records state and reads bound data imports
nothing. One that draws with Lit usually extends `LeafElement`, the Lit element on that
protocol, and one that draws from a page reading either does (`module-plain-elements.md`,
"`LeafElement`") or is an Effect UI component that `defineWidget` defines
(`/runtime/effect-widget.js`, whose header gives its contract): Leaf's reading and
what its `inputs` read arrive as props, and its events record.

Whatever a package leans on Leaf for is one of these kinds, and each kind has its own
form. Find a need's kind, then read the section that describes its form:

| A package leans on Leaf for                    | The form it takes                       | Described in                               |
| ---------------------------------------------- | --------------------------------------- | ------------------------------------------ |
| What Leaf must know before any module runs     | A key of the tag's declaration          | `packages.md`, "A widget"                  |
| What changes while the page runs               | The widget protocol                     | `module-plain-elements.md`                 |
| What a widget and a page's author both need    | An element Leaf defines on every page   | `module-state.md`, "Time readings"         |
| What only Leaf can do or know                  | A function from `widget-api.js`         | "Functions", below                         |
| A theme's choice                               | A custom property the sheet reads       | `package-themes.md`, "Theme tokens"        |
| A fact about where the widget's box stands     | A custom property Leaf or a Layout sets | `packages.md`, "Styles and composition"    |
| What the widget's box tells Leaf               | A custom property the sheet sets        | `package-themes.md`, "A theme change"      |
| Leaf's look for a part the widget draws        | A control built by its role, or a class | `module-controls.md`                       |
| A part of an element Leaf builds in the widget | A class on that part                    | `module-input.md`, "Text entry and drafts" |

An element Leaf defines has an entry in the page's vocabulary, as any tag does. A custom
property about scrolling or a sticky header is described with that subject, in
`module-scroll-and-motion.md`, and the parts of a widget's resolved threads in
`module-annotations.md`. What HTML, CSS and the browser's own APIs already do, a widget
writes as any web page does. That is no part of Leaf's interface, and nor is the
library ("Shared web code").

Whatever an element can't do through the protocol, such as reading the page's words or
its obligations, keeping the user's place, moving focus or keeping a draft, is a
function it imports from `/runtime/widget-api.js`, as a page script does; "Functions"
lists them all. Lit's templates come from `/vendor/lit.js`, Lit's own module, the one path its names
come from, such as `render`, `html`, `svg`, `nothing`, `repeat`, `keyed`, `live`,
`ref`, `createRef`, `classMap`, `styleMap`, `guard`, `unsafeHTML` and `noChange`. Of
the runtime's other modules, import only the library's ("Shared web code"). Don't query
Leaf's own chrome or copy a runtime helper.

### Functions

Every export of `widget-api.js` is here, under the section that describes it, and is
public for independent and bundled packages alike. A function's full contract is in the
header of the module `widget-api.js` re-exports it from, and a function that acts on
the DOM takes the element it acts for as its first argument.

In this file:

- "Connection lifetimes": `whileConnected` holds a connection's listeners and observers.
- "Startup and presentation": `afterPresentation` and `whenNear` defer heavy work,
  `growthIsSeen` says whether growing now would move what the user sees, and
  `whileInterfaceConnected` connects a page script to a widget.
- "Retained nodes": `setChildren`, `setChildLists`, `move` and `setRenderedChildren`
  place nodes the module keeps.
- "Shadow stages and styles": `shadowStage` builds a shadow root that wears the page's
  styles.
- "Scheduling paints": `frameFor` schedules one paint a frame.
- "Contained examples and scoped appearance": `mountSample` mounts a contained Leaf
  page, and `wear` gives an element a scoped appearance.

In [module-state.md](module-state.md):

- "State only this tab keeps": `tabStore` keeps a string for this tab, and
  `viewMembers`, `openingView` and `keepView` show one member of a widget at a time,
  which Leaf remembers, names in the address and returns the user to their place in.
- "Time readings": `clockValue` reads the server's time.
- "Editing a bound file": `boundFile`.
- "Authenticated HTTP connections": `connection`.
- "LLM generation": `generate`.

In [module-reading.md](module-reading.md):

- "Reading the page": `says`, `named` and `phrasing` read an element's words, and
  `elementById` finds the element an address names.
- "Naming": `nameOf`, `titledElement` and `anchorLabel`.
- "Following a reference": `navigateToDatum` takes the user to a part of another
  widget.
- "Markdown": `pageLinks`.
- "Code": `langForPath`, `dressCode` and `copyControl`.
- "Media URLs": `scopedMediaUrl`.
- "Reading obligations and the On lists": `readObligations`, `readQueues`,
  `answerWords` and `obligationActions`.
- "Work hierarchies": `readWork`.
- "Page history and reports": `readHistory` and `readReports`.
- "Reading version changes": `comparisonChanges`.

In [module-input.md](module-input.md):

- "Walks": `rowWalk` gives a list of rows its arrow keys.
- "Focus and layers": `focusDestination` moves focus, `holdFocus` keeps it across a
  redraw, `placeOf` and `onCurrentLocation` read where the user is, and `onPress` and
  `onPressAway` follow a pointer's press.
- "Delayed work": `retainUserIntent`.
- "Pointer presses": `aimedAt` says what a click on a container was for, and
  `onUserInput` hears each input before Leaf handles it.
- "Text entry and drafts": `wireInput` wires a text box, `draft` keeps its draft, and
  `leafEditorView` wraps a CodeMirror editor.

In [module-scroll-and-motion.md](module-scroll-and-motion.md):

- "Reading regions": `scrollerFor`, `preserveReadingRegions` and `showReadingSubject`.
- "Holding the reader's place": `holdPlace` and `HeldReading`.
- "Scrolling to a destination": `scrollIntoView`, `alreadyShown`, `scrollersOf`,
  `landingInsets` and `shownWindow`.
- "Motion": `motion` and `backgroundFlash`.

In [module-annotations.md](module-annotations.md):

- "Margin contributions": `registerContribution` and `presentContributionEntry`.
- "Reading and opening Threads from a widget": `readThreads`, `threadActions`,
  `threadInput`, `landInThread` and `agentName`.
- "Owning the primary conversation presentation": `registerThreadPresentation`.
- "Widget-local Thread placement": `threadSurface`.
- "Page annotation presentation": `placePageThreads`.

In [module-previews.md](module-previews.md):

- "Previews": `placePreview`.

In [module-controls.md](module-controls.md):

- "Generated controls": `searchField`.

### Shared web code

`/runtime/lib/` is a library of web code that Leaf's runtime and its bundled packages
share, such as the constructors of Leaf's controls, a time axis, a move's rank, code's
syntax colours and the words for a thrown value. It is not part of Leaf's interface: a
library module keeps none of the page's state and calls nothing of Leaf's. A widget
imports a module by its path, as it imports Lit, and the module works off Leaf too.
Like `widget-api.js`, the library can change in any update.
[The directory](../../../browser/runtime/lib/) lists the modules, and each module's
header and comments say what it exports. A module Leaf writes in TypeScript keeps its
types in the `.ts` beside the `.js` a widget imports.

### A widget that also runs off Leaf

A widget reused off Leaf imports `/runtime/portable-api.js`, which `widget-api.js`
re-exports, and may import the library's modules too. The portable functions are
[that file's exports](../../../browser/runtime/portable-api.js): each loads on a page
without Leaf, where `widget-api.js` can't. The host page serves the install's
`browser/runtime/` and `browser/vendor/` directories (`leaf --root` prints the install)
at `/runtime/` and `/vendor/`, or maps those paths to them with an import map, serves
the widget's own module, and gives the element its drawing box. For the widget's look it
links the layer's `portable.css`, served beside `/widgets/` (`packages.md`, "Styles and
composition").

`says()`, `named()` and `motion` are not among the portable functions, so the widget
does without them, on a Leaf page too:

- In place of `says()` and `named()`, it takes a part's name from an attribute, as
  `lf-timeline` takes an event's from `label`, and reads a data body with the
  library's `data-body.js` or from a bound input (`module-reading.md`, "Reading the
  page"). It takes no other words from an element the author wrote: on a Leaf page
  that element can also hold words Leaf wrote, which its `textContent` or a copy of
  its nodes would carry along.
- In place of `motion`, it moves a box with a transition in its stylesheet, as
  `lf-timeline` moves its playhead (`module-scroll-and-motion.md`, "Motion").

Leaf adds its services through the protocol's properties, events and declarations
(`module-plain-elements.md`), and a plain host ignores them all: there the widget's
`state` is never set, it binds no key, shows no preview, offers no comment target and
says nothing aloud. Off Leaf:

- A button that must work there makes its own press, from its own click listener: its
  command row names it as `control` and has no `run`, and the widget draws it
  `aria-disabled` while the press can't act, which is the availability Leaf reads
  (`module-input.md`, "Command rows").
- Leaf finds a block's Copy control (`module-reading.md`, "Code") and a quiet word
  (`module-scroll-and-motion.md`, "Notices and spoken words") in the page and in the
  shadow stages it builds (`shadowStage`), not in a shadow root a page script attaches
  itself.
- `tabStore` keeps nothing: a read answers null. Focus, scrolling and controls use the
  document's native behavior, and `langForPath` reads shipped defaults in place of the
  page's composed language map.
- Leaf stops no motion there for a user who asked for less, so the widget's sheet
  declares its motion under `@media (prefers-reduced-motion: no-preference)`.

`lf-chart` and `lf-code` in the default package, `lf-diagram`, `lf-motion` and
`lf-timeline` are the worked examples.

## What a behavior module owes

This is what a widget owes; a page script owes only what `page-behavior.md`, "A page
script", lists.

- Build once, behind a first-connection guard, and hold each connection's listeners,
  observers and registrations in `whileConnected` ("Upgrade", "Connection lifetimes").
- Wire no input inside an exhibit, which Leaf marks `data-lf-exhibit` ("Upgrade").
- Read the page's words with `says()`, and name a part with `named()`,
  never with `textContent` (`module-reading.md`, "Reading the page"). A widget that
  also runs off Leaf imports neither ("A widget that also runs off Leaf").
- Build injected controls, and a press that looks like Leaf's controls by its role,
  with the library's control constructors (`module-controls.md`). Mark words the
  widget writes apart from the author's with `data-lf-gen` (`module-plain-elements.md`,
  "Words it writes").
- Keep the widget's visible geometry stable as its state updates ("First paint"), and
  meet the rest of [interface-goals.md](interface-goals.md).
- Schedule paints with `frameFor`, observe size through the library's frame pass, and
  write a value only where it changes ("Scheduling paints", "Writes that change
  nothing").
- Keep each kind of state where `module-state.md`, "Where a widget keeps its state",
  puts it: record what the user makes with `lf-action`, and keep how they look at the
  widget in `tabStore`.
- Declare commands at upgrade, as an element's `lfCommands` (`module-input.md`,
  "Commands and keyboard routes").
- Move focus with `focusDestination`, never `element.focus()` (`module-input.md`,
  "Focus and layers").
- Animate with `motion` or in a stylesheet, never with `element.animate`
  (`module-scroll-and-motion.md`, "Motion").

## Upgrade

A custom element builds behind a guard that passes only on its first connection, since
`connectedCallback` runs again each time a revision or a thread puts the element back.
The library's [`once.js`](../../../browser/runtime/lib/once.js) holds that guard, and an
element that imports nothing keeps a flag of its own. Use `disconnectedCallback` only
for teardown that must happen at once, such as cancelling a grab or removing hoisted
UI.

A widget inside an element whose `exhibit` declaration applies (including its optional
`when` condition), such as `lf-sample`, is quoted, and Leaf marks that element
`data-lf-exhibit`. A quoted widget never takes the user's edits. Its verbs are never
`available`, and before wiring a drag grip, a command or anything else that sends
input back, it asks `this.matches("[data-lf-exhibit] *")`. Its presentation and view
state still work.

When an upgrade or one part of it fails, the widget shows the failure in place of what
failed rather than a blank, and dispatches the `error` event
(`module-plain-elements.md`, "`error`"). The library's
[`failure.js`](../../../browser/runtime/lib/failure.js) does both, and its header says
where the box goes and what removes it.

## Connection lifetimes

A revision or a thread can take a widget out of the page and put it back. Behind the
element's first-connection guard, register `whileConnected(element, start)` once for
what a connection holds:

```js
connectedCallback() {
  if (this.built) return;
  this.built = true;
  const schedulePaint = frameFor(this, () => this.measure());
  whileConnected(this, (signal) => {
    window.addEventListener("resize", schedulePaint, { signal });
    // What the signal can't end is this connection's cleanup.
    const sizes = sizeObserver(schedulePaint);
    sizes.observe(this.body);
    return () => sizes.disconnect();
  });
}
```

Leaf calls `start(signal)` now and on each return. When the element leaves, Leaf aborts
the signal and runs the cleanup `start` returned. If `start` throws, Leaf never calls
it again. `whileConnected` returns a function that ends the registration for good.

Moving an element within the page doesn't count as leaving. When a revision replaces a
widget, the old element's cleanup runs before the new one's `start`, so a registration
only one element may hold, such as `registerThreadPresentation`, passes to the
replacement.

Have `start` restore what its cleanup removed, and when the element leaves, drop
unfinished work but keep finished nodes.

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
its state, declares nothing. With `lfPatch`, a revision would put the members back in
the order it gives them and set no `state` again, so the widget would show the authored
order. Without it, the revision replaces the widget, the new widget's first draw places
the members, and a control the module keyed with `data-lf-carry` takes the user's focus
back (`module-input.md`, "Focus and layers").

Leaf also replaces a widget that declares `lfPatch` when a revision changes what its
module drew from, which it takes to be the element's own attributes. A module that also
draws from which children it has, or from their attributes, as a tab strip shows each
tab's `label`, declares `content: members` or `views`. Leaf then also replaces the
widget when a direct child is added, removed, reordered or given other attributes.
Without either declaration the module keeps its first drawing of a child the revision
changed. Leaf compares only each direct child's tag and attributes, and a revision
doesn't redraw a widget it keeps. So a module that draws from what its children hold,
or can declare neither, reads them again when they change, from a `MutationObserver`
on the children the author wrote, as `lf-pane` does, and never on the nodes the module
draws, whose changes would call it again without end. A widget that draws its own content (`content` `data`, `markdown` or `empty`) is
always replaced.

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

A module can listen on `document` for two startup events. `lf-presentation` fires once,
when the page's complete layout is first in place; UI drawn from element geometry takes
its first measurements there. `lf-page-interface` fires at startup and again when a new
revision is applied in place; UI built from the authored structure rebuilds there and
passes any asynchronous preparation to `detail.present(promise)`.

A page script reaches a widget's methods only once the widget has upgraded.
`whileInterfaceConnected(element, {declare, connect})` runs `declare()` once, for what
the widget accepts once per lifetime, then `connect(signal)` at the first
`lf-page-interface`, holding presentation until it returns, and again at once on each
reconnection; the cleanup `connect` returns runs as the element leaves. A playground's
page script is the worked example (the playground package's author instructions,
"Stateful previews").

Run a heavy renderer that can wait until the user has the page through
`afterPresentation(() => …)`, or until they come near its element through
`whenNear(element, () => …)`, which returns the step that stops waiting. Hand work that
starts now but need not delay presentation, such as a slow load whose result moves
nothing visible, to `afterPresentation(() => promise)`. Checks and tests that wait for
the page wait for the work each has started; `page check --render` starts what
`whenNear` holds.
Before deferring work that resizes the widget, ask `growthIsSeen(element)`: if growing
now would move what the user sees, say the work with a `pending-task` event instead
(`module-plain-elements.md`, "Drawing"), so it lands before presentation.

### First paint

Each widget renders when its module loads, then updates that same view from Leaf's
readings.

- Draw a widget's complete view in one place, its `state` setter or its one `render()`.
  The same drawing handles fresh mounts, thread messages and later updates; do not add
  a second initial renderer or transfer generated nodes between renderers.
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

### Retained nodes

To place nodes the module keeps, use `setChildren(parent, nodes)`, which makes `nodes`
the parent's only children, moving what is out of order and removing every other child,
the whitespace between authored elements included, or `move(parent, node, before)` for
one node. Where nodes move between parents, place every list at once with
`setChildLists([[parent, nodes], …])`, outer parents first. For a subtree the renderer
owns entirely, `setRenderedChildren(parent, nodes)` edits only changed text and keeps a
text selection the user made in it. A `LeafElement` places retained nodes in its
`render()`, which then returns `nothing`.

These helpers, `render` and `repeat` keep the user's focus in a moved node, so a reorder
needs no `holdFocus`; a plain `append` or `insertBefore` of a node already in the page
blurs it. A moved editable loses its selection even under `moveBefore`, so a
custom element holding a Leaf editor view (`leafEditorView()`) calls the view's
`placeSelection()` from its `connectedMoveCallback`.

### Shadow stages and styles

Declare `shadow` where the user should quote and comment on the words a widget's
shadow root shows; a root attached any other way is opaque to comments.

An element that attaches an open shadow root and says `lf-connect` gets the page's
shared stylesheet and comment support there (`module-plain-elements.md`,
"`lf-connect`"), as a `LeafElement` whose class says `static shadow = true` does.
Attaching the root says where the widget draws, and the tag's `shadow` says the user
may quote what it draws, so a widget that wants both does both. Use native slots for
authored children, and read presentation inputs from the host and those children.

An imperative renderer uses `shadowStage(host, nodes)`, never `attachShadow`; it applies
the same styles and returns the root. Stage a retained container and render into that
container. This API clears authored light children and supplies no slots, so read what
the renderer needs before staging.

On a plain host `shadowStage` stages only the renderer's content; a Leaf page supplies
its theme, annotation support and page watches from outside the widget.

Wrap stylesheet text the module writes itself in `@layer lf-base { … }`, so its rules
sit with the widgets' defaults in `lf-base`, above the page's `base` layer and below
Layouts, package overrides and the page's other layers and unlayered rules.

### Scheduling paints

`frameFor(element, paint)` returns a function that schedules one call to `paint` for the
next render, however often it is called. It does nothing while the element is out of the
page, and leaving cancels a scheduled paint, so schedule it again from `start`.

Schedule a widget's other rendering work, and observe size, through the library's
[`frame-pass.js`](../../../browser/runtime/lib/frame-pass.js), in place of
`requestAnimationFrame` and `new ResizeObserver`. That module holds the one pass per
frame that every rendering callback on the page runs in, which `frameFor` schedules on,
and the size observer that goes with it. The page doesn't count as settled until that
work runs, nor while sizes change, so motion that may run until the user stops it, such
as playback, calls the browser's `requestAnimationFrame` instead.

Have a size observer's callback schedule a paint from `frameFor` rather than draw. A
drawing made inside a size delivery has the browser report a ResizeObserver loop, which
`page check` counts as a fault.

### Writes that change nothing

Writing a value a node already has still reaches screen readers and can repaint the
whole document, so write an attribute or a node's words only when they would read back
differently. For a flag such as `hidden`, `toggleAttribute(name, force)` writes only
when the flag changes, where the `hidden` setter rewrites the attribute on every set.
Round a measured length to layout's 1/64px before writing it into a style, so a measure
that jitters below that writes nothing new. The library's
[`keeps.js`](../../../browser/runtime/lib/keeps.js) holds guards for attributes, words
and measured lengths.

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

The host gives a block's frame its child's height, as the frame's content height, so
set none yourself; a window's frame keeps the height its styles give it. A resize the
user did not ask for waits while it would move what they are reading.

The host's `ready` promise belongs to its current child, and changes when loading
starts again. `on(type, callback)` returns an unsubscribe function. Its notices are
`loading`, `departed`, `input` (with the event's `{type}`) and `current-location` (with
`{focused}`). The host counts the child's arrival in the page's readiness itself.
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
