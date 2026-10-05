# Authoring behavior modules

Use this reference for browser behavior in a page script, a page-owned widget, or
a reusable package widget. Read "What a behavior module owes" before writing it,
then the API sections its behavior needs. The same public helpers serve each form;
DOM helpers take the element whose behavior they implement. Semantic controllers
require a registry-declared widget; ordinary elements use the general DOM helpers.

[page-authoring.md, "Page behavior"](page-authoring.md#page-behavior) owns script placement,
imports, and revision lifetime. [packages.md, "A widget"](packages.md#a-widget)
owns element declarations; its ["User state"](packages.md#user-state) and
["External or derived data"](packages.md#external-or-derived-data) sections own
state and source contracts. Add or change those declarations when the module needs
a new capability.

## Public API

`/runtime/widget-api.js` is the whole Leaf API a behavior module gets: a module imports
only that public helper surface, and does not reach into the runtime's private owners,
query private chrome, or duplicate a runtime helper inside itself. Resolve canonical
`/media/…` paths from typed data with `scopedMediaUrl(path)` before assigning them to
generated images or links. It uses the page's public root across ordinary and
published pages while the source retains its canonical path.

For a vertical navigation that must retain sideways reading, use
`scrollIntoReadingBand(target, holder, block, behavior)`: `target` is an element or
Range, and `holder` is the element whose reading regions contain it. Element targets
support `start`, `center`, or `nearest` for `block`; a Range is always centered. It places the
target in the innermost reading band and reveals it in enclosing regions, across
shadow roots, without changing horizontal offsets.
Use it for an explicit arrival; entering visible controls and ordinary repainting
preserve their current reading position.

Registry-declared inline Markdown formats authored text, not strings a module assigns
with `textContent`. For changing Markdown prose, load the renderer with `loadMarkdown()`
and paint the current value with `inlineMarkdownFragment()`; repaint that value when
loading completes. A changing numeric readout keeps surrounding text still with
tabular numerals and a slot wide enough for its largest value.

## Startup and presentation

`body[data-lf-presented]` means the initial authoritative projection, or the deliberate
offline fallback, is safe for recorded interaction. Authored content is already visible:
Leaf disables its arrival transitions and durable widget actions before that stamp.
Printed keys pressed earlier are held and reach the page's key handlers only after the
stamp lands, in order, so a package's keys need no arrival guard either.
Package styles need no arrival guard. A package opens a dialog or popover only after that
stamp or in response to a user gesture; Leaf does not defer top-layer UI during startup.
A widget that keeps part of its own upgrade off the presentation path — a heavy renderer
it earns the right to load only once the user has the page — runs that work through
`afterPresentation(() => …)`, which is both the wait and the declaration. The page then
answers for it: until every such arrival lands, the page reads as still arriving, so a
user outside it waits on the page rather than on a widget it would have to know about.
A declared `x-shadow` widget gets the same transition protection when it builds its root
with `shadowStage`.

## What a behavior module owes

A behavior module follows these rules:

- Use `says()` over `textContent`.
- Use `offer()` and `relabel()` for injected UI. Reserve its space in
  `measure`. After a view swap, call `layoutChanged` and await its promise before
  restoring scroll. A registry-declared widget registers asynchronous visible
  preparation through `controller.present(promise)`.
- Read UI based on element geometry synchronously from `PRESENTATION` for its
  first paint, then through normal layout signals. Reconcile UI derived from
  authored structure at `PAGE_INTERFACE`, at startup and each in-place revision
  activation. Retain surviving nodes with `setChildren` to preserve focus and
  native view state.
- Use `nextRender`/`cancelRender` for paints and `sizeObserver` for size
  observation, so checks and tests wait for that work too. `nextRender` runs in
  the current rendering callback's frame, or in the next frame when called
  elsewhere. Use `nextFrame` for a step that must run in a later frame, such as
  an animation tick. A playback loop keeps `requestAnimationFrame`, so playing
  does not prevent the page from settling.
- Use `afterScript(callback)` to coalesce a stable callback at the current
  script's microtask checkpoint when synchronous updates yield one final
  mechanical reading.
- Use `keeps(node, name, value)` for names or state a reactive render writes,
  passing booleans and counts directly. Unconditional `setAttribute` repeats
  writes on every publication; `toggleAttribute` already handles flags.
- Use `once()` in a `connectedCallback` that remains safe after reconnection.
  In `disconnectedCallback`, remove hoisted UI and clear any `indicate`
  with `null`.
- Register `commands()` at upgrade. Use `DISCLOSE(el)` for folding controls,
  whose commands the runtime owns. Check `quoted()` before wiring input and
  controller command availability before a semantic widget’s optimistic gesture.

Each helper's header under `runtime/` explains its contract.

### Declared widget state

A registry-declared widget implements a total, idempotent `renderState(state)`.
Record user state through `widgetController(owner).dispatch()` with detail matching
the declared browser schema. Ordinary script-owned elements do not acquire a
semantic controller; use the general helpers for their local behavior.

`renderState` receives the state of every declared verb, keyed by verb name, including
the initial values an undo returns to. A widget-unit verb's state is `{action, value,
detail}`: `action` is null for authored state; `value` is the typed record value, or
the verb's name for a recordless verb that stands (null means undecided); `detail`
retains generated-child labels and other declared event data. A per-part verb's state
contains `units`, keyed by unit id, and a position verb's also contains `value`, a map
from container id to the complete ordered ids it holds, and `ranks`, each listed unit's
rank. A position record carries a rank rather than an index, so a unit's placement
stands whichever other moves stand, until a version authors the container's units
differently and its markup places the unit: dispatch `rankAt(state.<verb>, container, index,
unit)` from `runtime/widget-api.js` for a unit dropped at `index` among the container's
other units. Missing recordless units are
undecided. Render the final composition and keep independent
nested widgets mounted; never recreate the owner to restore an initial state.
The controller ignores the renderer's return value. A live editor or pointer/keyboard
rearrangement calls `controller.defer()` before its first local DOM mutation and invokes
the returned one-shot resume only after dispatch has synchronously staged the semantic
result, or after cancellation has restored the prior local DOM. Resume reconciles the
newest publisher reading. Optional recorded scalar attributes have a null initial
value and must be removed when that value returns.

A widget that declares `x-awaits` says what its answered Ask was answered with: its class
declares `static answerWords(state, element)`, returning concise words for the Asks
drawer's row and a queue's row. `state` is the same complete state `renderState`
receives, and `element` is the widget, for authored markup such as an option's name;
read nothing the module renders. Leaf calls it only while the Ask is answered, with the
state of the publication that carries the Ask inventory, so the words never wait on a
render; it normalizes their whitespace and bounds what it displays. A widget without one
names no answer.

## The widget controller

`widgetController(owner)` is the one semantic interface; callers supply no options.
Leaf captures the owner's identity and revision-bound declaration before upgrade, so an
author change to those facts fails closed. Its methods are `read`, `subscribe`,
`dispatch`, `defer`, and `present`.

`read()` returns an immutable `{authored, state, thread, provenance, actions}`
snapshot. `authored` is the typed baseline decoded from
validated source markup; `state` is that baseline with admitted and unresolved records
folded over it; `thread.heldBy` is the `id` of the open, admitted Thread whose root
holds this widget, or `null`. Each `actions` entry carries its availability and
exact history or Undo candidates. Guard every optimistic mutation with its entry's
availability; `dispatch()` repeats the same check.

`subscribe(callback)` invokes immediately, returns cleanup, and should be stopped on
disconnect; reconnecting subscribes again. For each reading the controller calls the
module's `renderState(state)` first and these subscribers after. Report-only and quoted
semantic widgets subscribe too, even with no interactive controls. What the declaration
alone determines, such as a holder's settlement (`x-retired-when`), Leaf paints whether
or not the module subscribes.

`dispatch({kind: "action", verb, detail, attempt?})` and
`dispatch({kind: "undo", target})` return `null` when the newest reading refuses the
command, otherwise `{reading, delivery}`. The returned reading already holds the
optimistic result; delivery later yields the admitted event or null, and a refusal
restores authoritative state. Undo targets only a stable `id` or `attempt` from the
current entry's candidates. The server remains final admission for every command.

## Reading regions

A pane declares `x-reading-role: pane` and keeps `x-content: markup`: exactly one direct
body element between an optional native `header` first and an optional native `footer`
last. The validator reads the role rather than the tag name, and delivery paints it into
the served document as `data-lf-reading-role`, which the kernel's theme and the
workspace Layout lay out as a pane from the first paint, so every package's pane takes
the same rules; its module registers the pane's body as described below.

Whether a pane's body scrolls is the workspace Layout's (`layouts.css`). Where the
window is large enough, the workspace is full-height: it fills the window, and the
Layout gives its body a definite height, so a pane that is the body or a direct cell of
it may shrink below its content and scrolls its body; a pane inside a section of the
body, or inside another pane's body, flows with what holds it, and elsewhere every pane
takes its content's height. Nothing in a module measures a minimum or chooses a
posture. While the workspace is full-height, the Layout sets `--lf-full-height: 1` on
`main`, and a widget that should grow to fill the height it is given, such as a
playground's stage, keys its rules on `@container style(--lf-full-height: 1)`. A behavior
module that composes regions out of boxes it generates, such as a playground's controls
beside its preview, takes the pane rules by marking those boxes
`data-lf-reading-role="pane"` and `data-lf-generated`, with the pane grammar of one
header, one body, and one footer. A generated pane scrolls its body wherever it stands in
a full-height workspace, since its widget sizes it, and its widget draws the frame around
it: the workspace joins only the panes a page wrote into its hairline grid. The
attributes are the module's to write and never an author's, since `page check` refuses `data-lf-` markup. Keep the
package theme to placement inside that grammar, such as track sizes and chrome; a
package copy of the full-height rules is a second posture decision that drifts from the
Layout's. Generate boxes rather than `lf-pane` elements themselves: those are authored
words the render gate pairs with the file.

`registerReadingRegion({id, host, body})` binds a region's identity to its host and to
the body that scrolls it whenever the theme makes it scroll. The host makes focus in a
pane's header or footer select that pane. Register from `connectedCallback` and call
the returned cleanup from `disconnectedCallback`, so a reconnect can claim the same id.
`readingPosture(node)` is `bounded` exactly while the region's body is its own
scroller, and `watchReadingRegionTransitions(listener)` receives a `shift` when a
region's scroller changes without a gesture; the continuity owner records the user's
place as they scroll and restores it there.

A compound widget whose parts scroll independently registers each with
`registerReadingRegion({id, host, body})`, taking a stable id from
`compoundReadingRegionId(owner, localName)`. A composition that hides or reveals regions,
such as a tab switch, runs the change through `preserveReadingRegions(owner, change)`,
which awaits the change's returned layout promise before restoring the visible regions'
scrollers. `runtime/reading-regions.js` describes the region model.

A widget that re-renders or resizes content inside a scroller of its own holds the
user's place with `placeKeeper(scroller, {items, identity})` rather than by restoring a
`scrollTop`; `runtime/user-place.js` describes it.

A widget that remembers where the user was reading, in a view it hides and shows again,
keeps a place rather than an offset: `capturePlace()` reads the page's place as a
landmark in its own words, and `restorePlace(place)` returns to it however the page has
moved since (`runtime/reading-place.js`). A widget that adds same-document history
entries adds them with `pushEntry(url)` and `replaceEntry(url)`, and places the page
itself at Back or Forward to one of them by claiming that traversal with
`claimTraversals(claim, {signal})`. Every other traversal returns the user to the offset
the entry was left at (`runtime/history.js`), unless the element the entry's fragment
names is no longer shown: that one reaches the widget holding it shut as `lf-reveal`
and lands on it, as a followed link to it does.

A sticky header, a sticky box over the top of its scroller, has a stated height, sticks
at `var(--lf-top)`, and adds its height to `--lf-top` for what it stands over. Its
holder passes the value it met on under a second name, since a custom property cannot
read itself:

```css
.file { --lf-top-outer: var(--lf-top); }
.file > .head { position: sticky; top: var(--lf-top); block-size: var(--head-h); }
.file > .rows { --lf-top: calc(var(--lf-top-outer) + var(--head-h)); }
.file .row { scroll-margin-top: var(--head-h); }
```

The rows' `scroll-margin-top` has a landing on a row, native or the runtime's, arrive
below the header. The runtime reads what passes under it as off screen from `--lf-top`,
for read acknowledgement, arrival checks, and chrome placement, so nothing is declared.
The stacked value goes on a box that does not itself scroll, since the runtime reads a
box that scrolls where it stands. A box a package makes scroll starts `--lf-top` again
at `0px`, on the box that scrolls and only there.

A composition allocates a Leaf element's outer box. The package owns how the element's
contents use that allocation, based on its available inline size rather than the page
shell or a reading posture. Prefer intrinsic grid or flex layout. When the contents need
a discrete breakpoint, make the element a query container and apply the conditional
rules to its descendants. A host rule inside that block does not fail: an unnamed query
answers from the nearest ancestor container, and `body` is a container, so the rule
silently follows the page shell instead. Keep the host's own layout intrinsic, or put
the properties that change on a descendant layout box.

## Focus, motion, and travel

A module that puts the user somewhere calls `focusDestination(element)` rather than
`element.focus()`, wherever that place is not already a control. It lends the element the
tab stop a control has for exactly as long as it holds it, so the browser's own Tab order
continues from there and no `tabindex` is left on the page behind the user. What needs
it is a widget's own Escape step landing them back in the thing it took them out of: the
patch a file filter belongs to, the exhibit a box was about.

A module that moves, hides, or replaces nodes the user may be standing in, as a reorder or
a re-render does, calls `holdFocus(scope)` before the change and the function it returns
after it. Moving a focused node drops its focus to the page body; the returned function
puts the user back on that node, with its caret, or on the first drawn stand-in it is
passed, such as the replacement keyed on the same identity. It does nothing once focus was
placed elsewhere in the meantime, and `holdFocus` returns `null` where the user stands
outside `scope`.

A module that takes the user to a thread calls `openThread(id, {focus})`
with the Thread's `id`. It opens the thread where the page shows it, inline beside
its passage or widget, and in Threads when it has no place on the page, the same choice a
mark and `t` make. `focus: "thread"` lands on the card or native summary;
`focus: "reply"` reveals its available reply editor. Omitting `focus` follows the
surface's ordinary route: a compact passage card starts at the card, while a widget
conversation or Threads starts at its reply. The call returns a `Promise<Element|null>`:
the actual destination after reveal and placement, or `null` when the Thread no longer
stands or newer input has superseded the move. Leaf owns the original gesture's
continuity inside this route. The returned, still-focused destination is the capability
for a continuation: a separate predicate captured on the button would reject the
route's own move to that editor. A continuation uses the returned element only while
it still holds focus:

```js
const editor = await openThread(thread.id, {focus: "reply"});
if (editor?.matches(":focus") && editor.setSelectionRange) {
  editor.setSelectionRange(0, editor.value.length);
}
```

A place on the page is an ordinary fragment link; Leaf follows it the
way it travels to a thread, clearing a panel that covers the page and opening whatever
holds the element.

A module that names an element away from it, in a feed row or a summary, reads the page's
shared names rather than its own. `addressableLabel(element)` is what the chrome calls
it: first the name the authoring contract gives it (the attribute its entry declares
with `x-name`, else a leading `<summary>`, heading, or titled member's `<strong>`,
inside a leading `<header>` or `<hgroup>` too), else its caption or `aria-label`. An element whose
words are its own, such as a paragraph or a list item, is otherwise named by those
words cut short; any other element takes the name of the nearest element holding it
that has one, so a question's options are named by the question. Past that, plain
markup is named by its words cut short and a widget by nothing: the label is empty, and
`addressableWord(element)` is the word for its kind. A
widget whose title is an attribute, as a column's `label` is, declares `x-name`.
`anchorLabel(anchor, about)` names a comment's anchor the way Threads does, and
`markdownWords(text)` is the words a Markdown string renders to.

A message's widget markup is a document of its own, and it may repeat the shapes the page
holds. A module that finds a partner element by reference, as a seat names the widget it
serves, searches `authoredScope(element)`: the page's `main`, or the body of the message
whose markup holds the element. A search of the whole `document` lets quoted markup answer
for the page.

A module that moves something calls `motion(element, keyframes, ms)` rather than
`element.animate`. The stylesheet's reduced-motion guard reaches CSS animation and
transitions, not a Web Animations call a module makes for itself, so `motion` is where a
user who asked for stillness is answered: it returns `null` under that preference,
before `body[data-lf-presented]`, and while standing state is being restored into
replacement markup, and a caller treats no animation and a finished one as the same
state. `reducedMotion()`, `scrollBehavior()`, and `onMotionPreferenceChange()` answer the
same preference where a module has to branch on it, and `FOLD_MS` is how long a unit takes
to leave, so a widget retiring one uses that constant rather than choosing a number. Spend
a duration only on letting the eye follow a box from where it was to where it is. A result
the module can already draw is drawn in the gesture rather than after a wait.

A module implementing its own navigation captures `retainUserIntent()` in the gesture
that starts it, before its
first wait, and checks the returned predicate after every wait before moving focus or
scroll: loading a file, a deferred value, or a renderer is a wait, and a user who pressed on
in the meantime is not moved back. A predicate taken after a wait would carry a newer
gesture's authority. If the navigation itself opens or closes a surface that moves
focus, `currentIntent.handoff(() => changeSurface())` preserves that synchronous focus
transfer without renewing the original input generation. After a wait, check the
predicate before starting that synchronous handoff. If the synchronous work already
moved focus, the handoff keeps and adopts that destination instead of running the old
focus move. A skipped move returns false, so a caller that requires the surface change
can decline; adoption alone does not report that the move ran. Leaf's navigation
primitives own that retention already; `openThread` returns its completed destination
as described above.

When Leaf travels to a target, such as a comment anchor or an Ask, it first dispatches
`lf-reveal` on each ancestor of the target and the target itself, outermost first, with
`detail: {target, mayReveal, present, replacedView}`. A widget that folds content listens
for it and opens whatever holds `target`. `mayReveal` is the traveller's retained intent:
an asynchronous listener checks it after each wait. A widget replacing a mutually
exclusive visible view opens it and calls `replacedView()` synchronously during dispatch.
Travel places that destination immediately. Expanding content within the current view
does not report replacement and retains ordinary scrolling. A listener joins later
layout completion through `present(promise)`; travel waits for those promises and reads
fresh geometry for its final placement. `lf-tabs` is the worked example.

`registerContribution({key, target, source?, read, activate})` is the package boundary for
shared page actions and statuses. `read()` returns the contribution's complete current reading,
including immutable `contributionEntry({...})` records; it never returns controls. Leaf renders
those same records independently in the target's Margin cluster and in Page Map.
Reading items in `readings` have nonempty `id` strings, unique within that contribution;
other contributions may reuse an ID. `kind` names what the contribution is, as one of the
margin's reading kinds (`change`, `comment`, `ask`, `action`, …; `action` where it
declares none): where a pin with a primary and one more control finds no room for both,
it stands folded to one control wearing that kind's face and name, which opens to them. Leaf retains each projected control by the opaque
contribution key and entry key while its native kind remains compatible. Actions and disclosures are buttons; statuses are spans,
so crossing that semantic boundary replaces the host instead of emulating a button.
`target` is an
element or a function returning the element that currently anchors the action. `source`
defaults to that target and may separately name the semantic owner when presentation has
to move to a surviving ancestor.
An entry that presents a declared command sets `scope` to its `commandScope` capability
and `activation` to that command's stable id. Leaf derives the entry's disabled state
from the command's availability and invokes the same `run(binding, context)` callback
as its keyboard route. Keep its semantic action in `run`; no separate `activate`
callback is needed for these entries. Other actions use `activate(token, context)`.
The context carries the projected origin,
surface, input kind, current entry, and a focus capability. That capability moves the
current surface only when activation owned keyboard standing and otherwise returns
false. The returned registration
exposes `entry`, `control`, `contains`, `activate`, `activateReading`, `focus`,
`update`, and `unregister`. Auxiliary reading activation callbacks stay with the live
registration; projected readings contain data, and `activateReading(id)` invokes the
current capability for that reading.

`update()` replaces the whole reading and may synchronously present it or focus a
surviving key. Keep text fields, history, and other mechanical editing state in the
widget. Publish only action and status records to the margin, with explicit `element` or
`entries` relations when a disclosure owns another surface or entry.

An entry needs `key`, `label`, and exactly one of `glyph` (text) or `icon` (a Leaf
icon name). `kind` belongs to the whole reading, never an entry. Entries default to
`behavior: "action"`, `tone: "neutral"`, `rank: "primary"`, and `state: "idle"`;
`activation` defaults to their key. `CONTRIBUTION_ENTRY_SCHEMA`, exported by
`/runtime/widget-api.js`, gives the accepted values for those four fields.
For example, inside an existing widget whose `saveDraft()` owns the effect:

```js
import { contributionEntry, registerContribution } from "/runtime/widget-api.js";

connectedCallback() {
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
    activate: () => this.saveDraft(),
  });
}

syncActions() { this.actions.update(); }
disconnectedCallback() { this.actions.unregister(); }
```

Call `syncActions()` when the widget's state changes. Return the actions available
in that state from `read()`; every surface receives the same current records.
Leaf's native controls and Page Map provide keyboard routes. A widget adding its
own commands calls `actions.activate(key)` from those rows, so keyboard and pointer
input reach the same effect.

A contribution stands in its target's cluster wherever that cluster stands: in the rail
beside a column page, or as a pin over the page by the target, where an unfolding
cluster grows leftward. Leaf inserts nothing into the
page's content for it, so its controls come after the page's content in the tab order;
the margin's own keyboard routes, `t`, and the Page Map reach them from the target.
Nothing about the contribution changes with the posture, and a package never places or
sizes its controls itself.

## Following a reference

A module reaches another widget through an attribute its entry declares in `x-refers`
([packages.md, "References between widgets"](packages.md#references-between-widgets)) rather than looking the id up itself. Leaf
resolves the attribute in the owner's own authored document first, so a widget in a
reply finds its message's element before a page element with the same id, as the server
does, and then in the page, which a reply's widget may name. Both verbs below
throw a `TypeError` for an attribute the owner's entry does not declare.

A key addresses elements under the named widget in one key space: a registered visual
part's id, a projected datum's key, or, where the widget's parts have a private address,
whatever its `lfElementsFor(key)` maps to elements under itself. `lf-code` answers its
`hi` grammar, so `"3-5,8"` addresses those lines.

`navigateToDatum(widget, attribute, key, messages)` travels to the first element a key
addresses. Leaf resolves declared shadow trees, asks the target to hydrate lazy data or
draw a visual part it shows only in another state, opens its containing disclosure, focuses
the addressed element, updates the fragment, and announces the supplied `success` or
`missing` message. Commands at that focus use the datum's identity. A lazy target may implement
`lfRevealDatum(key)` to return its hydration promise and `lfDataDatum(key)` to map a
semantic key to the rendered projected element.

### Indicating (experimental)

The signature and the `lfElementsFor` hook may change. `indicate(widget, attribute,
key)` marks the elements a key addresses, in place of whatever that widget last
indicated through the same attribute, and returns whether anything is marked; `null`
clears it. Leaf paints the marked elements with `data-lf-indicated` and nothing else,
leaving the target's own ARIA state alone, and never scrolls, focuses, reveals, hydrates,
or announces for them, so a driver may move its indication every animation frame without
moving the page; the driver's own narration says what the mark means.
An indication is browser state, like hover: the log never records it, and a new revision
does not carry it. A widget whose parts have a face of their own styles
`[data-lf-indicated]` on them; the default is an accent outline. A target that re-renders
what a key addresses calls `layoutChanged(this)`, and every standing indication resolves
again.

## Commands and keyboard routes

A widget contributes each command once with `commands(source, title, rows, options)`.
The dispatcher, shortcut bar, command reference, `aria-keyshortcuts`, and inline hints
consume those same declarations. Every row and route has a stable dotted `id` and a
required concise `title`, such as `"Pass"`; the title may be a function when state changes
the action name. An optional `description` supplies extra detail in the reference.
The bar defaults to the title; `line` overrides its short wording and `line: false`
keeps a reference-only command out of the bar. `label` overrides the keycap, not the
action name. A keyless command still has its title in the reference.

Declare ordinary local bindings in `keys` and explicitly forwardable aliases in
`contextKeys`. Both arrays work inside the widget. Only context aliases are exposed at
the enclosing Ask's opening and its associated margin controls and threads. A route can
declare its own `contextKeys`; an ordinary key on another route is never forwarded.
Numbers are widget choices, not an Ask allocation: options own their stable numeric
assignments, and a swipe deck declares Pass as `1` and Keep as `2`. The page owns `a`
and `Shift+a` navigation between Asks. Do not assign numbers based on currently available
actions: disabling `1` must not turn `2` into a different action.

```javascript
const actions = commandScope("In a swipe deck", [
  {
    id: "swipe.pass",
    title: "Pass",
    keys: ["ArrowLeft"],
    contextKeys: ["1"],
    decision: true,
    control: passButton,
    bindingBadge: passHint,
    when: canSwipe,
    run: () => swipe("pass"),
  },
]);
commands(deck, actions);
```

For a native button, `control` and `run` declare one activation path: Leaf invokes
`run` for both its click and its keyboard command, and paints native disabled state
from `when`. Remove a separate button click listener and disabled painter. Call
`paintKeys()` after private state used by `when` changes; closures are not reactive.
Use the semantic action directly in `run`, never the same button's `click()`. Native
inputs keep their platform activation and editing behavior; a row that focuses an
editor or activates a checkbox does not replace that native behavior. Generated
contribution controls use the same callback through their surface-aware registration
("Focus, motion, and travel" above).

Set `decision: true` and provide `control` when a command starts, advances, answers, or
revises the Ask containing `source`. This semantic role neither assigns a binding nor
makes ordinary keys forwardable. A numeric command need not be a Decision. Forwarding
retains the original source, scope, row, and route identity, rechecks their current
availability, and invokes the original callback or native control. Replacing or removing
the source attachment withdraws its old routes. A nearer widget owns its declared keys;
an unavailable implemented binding reserves its key against a different outer meaning.

Declare `bindingBadge` on a row or route to request an inline shortcut hint, whether or
not the command is a Decision. An element names an empty face the widget positions;
`null` requests a badge at the control's corner. Each supplied face belongs to one
action. The shared keyboard presenter writes its first reachable binding while the
whole face is connected, visible, and uncovered; a reachable Ask alias takes precedence
over an intrinsic binding for the same command. Otherwise it paints a corner badge at
the visible control. Commands without `bindingBadge` do not request an inline hint.
The presenter reads the dispatcher's effective bindings, so hints withdraw outside the
scope, during native text entry, or when the command is unavailable. A widget owns the
face's placement, not its text or active state. Routes let one parameterized row
contribute distinct controls and intrinsic bindings. Do not maintain a second
Ask-control list or paint binding text in the package.

Command scopes compose by focused ancestry. The exact control scope is nearest, followed
by containing widget scopes and Leaf's outer page scopes. A scope owns only the bindings
whose rows implement a Leaf invocation, so an undeclared key falls outward. An
implemented declaration keeps its key while its command is unavailable, so the key never
exposes an ancestor's different meaning: liveness removes execution and projections, not
the claim. Escape means one step back at every depth, so no ancestor's Escape is a
different meaning, and a dead inner Escape declaration passes the key to the next live
return rather than stranding it. A row without
`run` only presents native behavior or a shared outer handler and does not shadow it. Text
fields and other native interactions retain their editing keys ahead of ancestor widget
scopes and all context aliases, including aliases attached directly to an editor. Ordinary
exact-control keys keep their existing precedence for Save, Escape, or submit.

Use `commandScope(title, rows, options)` when Leaf, rather than the widget, creates the
focusable control. Put the returned capability on a margin-entry record's `scope`; each
projection attaches that scope to its own visible control. When the same command set
also applies to retained widget DOM, attach that one capability with
`commands(element, scope)` instead of declaring the rows again. Use
`commands(element, title, rows, options)` for a scope that exists only on widget-owned
DOM.

Every visible press a widget builds with `offer()` or `selectableOffer()` also joins the
generated target map after `g`. Packages do not declare another `g` binding or repeat
those controls in a destination list. Text and range inputs remain ordinary Tab stops;
buttons, checkboxes, radios, and selectable controls are addressable because they have a
discrete activation. A custom element with a complete host-level `focus()` and `click()`
contract passes `true` as `offer()`'s fifth `pressable` argument; its tag then supplies the
same addressable marker as a native control.

Register the command once, not every nearby button. Evidence nested inside an
option is not an answer, and a shared-margin entry may sit outside the Ask source. When
controls or availability change, keep the row fields computed and call `paintKeys()`;
every command projection then updates together. A package that needs the page-wide open
Ask set calls `watchAsks(owner, callback)`. It invokes `callback(openAsks)` on the
microtask after subscribing and again after each state change, at most once per
microtask and possibly with an unchanged set; it skips calls while `owner` is
disconnected, and returns a cleanup function the owner calls on disconnect. Each
Ask is an immutable `{id, tag, sourceId, sourceTag, thread}` record; resolve a node only
to present or focus it, never to decide membership or answered state. The set is empty
until the page's first server reading is admitted, and it changes with each later
reading rather than when a gesture is sent, because only the log says which authored
Asks still stand and which of them are answered. Package semantic behavior subscribes only through its
controller.

Every row passed to `commands()` has a stable dotted `id`, such as `draft.save`. Keep that
identity when its key or wording changes: the command browser and repeated widget
instances use it instead of display prose. If one compact row binds keys with different
meanings, add `routes` with an `id`, `title`, and ordinary `binding` or explicit `contextKeys` for each meaning. A route may
declare its own `when` when its control is available independently of its siblings. The
shortcut bar stays compact, while the command reference lists and runs each route on its own.
Use `runFromCommandReference: false` only for a parameterized step that cannot be run without a
choice the command reference does not have, such as a generated hint tied to the live viewport. An
optional `reach` on a row or scope supplies the short place phrase shown when a command
is not available (for example, `in an open draft editor`).

A list of focusable rows takes its walk from `rowWalk({id, noun, plural, rows})`, whose
two returned rows go into the list's own scope: ArrowUp and ArrowDown step and clamp,
Home and End reach the ends, and each landing shows its position, such as `Option 3 of
7`. `rows()` returns the list as it stands at each press.

A widget-owned composition box is the runtime's text field, `offer(TEXT_FIELD)` from the
widget API: a Markdown editor that shows the draft the way the sent message will read
and answers the textarea members a box needs (`value`, the selection, `placeholder`,
`readOnly`, `name`, `aria-label`), firing `input` for the user's edits only. Wire it
with `wireInput()`, which registers Enter for the contextual action on physical
keyboards and leaves Shift+Enter as a newline. On touch keyboards, Enter stays a newline
and the visible control submits; Mod+Enter is also available where a modifier key
exists. The helper also owns shared draft persistence, busy state, and shortcut
projections. A direct editor that needs more commands, such as Save and Cancel,
registers those rows on its box with the same text-entry meanings. `TEXT_BOX` matches
the text field and any native textarea, for code asking whether an element takes typed
paragraphs.

A field has `:state(ready)` once its editor view exists. When it replaces a reading
surface, keep that surface in flow until the field is ready: measuring a connecting
empty field must not shrink the scrollport and lose the user's reading position.

The call returns the box's one seam onto its draft, and a box holds more than its
`.value`: an image pasted into one is kept as Markdown and shown as a thumbnail beside
the words, never in the field. So `sync.value()` reads the whole draft, `sync.load()`
replaces it — a stored record, a draft arriving from another tab, the emptiness a send
leaves — and `sync()` says the box's standing changed. The send button, placeholder, and
whatever the widget's own `paint` option draws from the box repaint once, in the
runtime's next standing paint, before that frame shows. Write `.value` only to seed the
box before wiring it.

## Visual parts

A visual with generated part ids declares accepted `x-visual.prefixes` and calls
`registerVisualParts(source, read, {reveal, label})`. The `read` function returns
the parts currently drawn as `{id, element, label}` records. `reveal(id)` draws an
absent part when someone follows its thread; `label(id)` names that part in
Threads without changing the visual's state, and returns `null` for an unknown id.
An `x-visual.parts` declaration may set `complete: true` when listing some drawn
parts while leaving their peers unaddressable would confuse a reader. The render
check then requires a nonempty authored list to name the full registered inventory;
omitting the attribute keeps the visual as one target.

## Page history

A widget that renders the page's history declares `x-history` and reads it through
`watchHistory(owner, callback)`: the server's rows, newest first, each already
carrying its thread, whether it was undone, the name an agent's row is shown under
as `agent`, and a gesture's words as the document it was made in had them. The
widget words those facts; it does not fold the log.

## Data subscriptions and projections

The source declarations and producer workflow are in [packages.md, "External or derived
data"](packages.md#external-or-derived-data).

A module subscribes through its own input declaration:

```js
this.stopWatching = watchData(this, "builds", (snapshot) => render(snapshot));
```

The callback receives `null` while the source has no readable value, otherwise a clone
of `{source, contract, revision, updated, value, origin}`. `revision` identifies the
value itself, so a renderer can distinguish two writes even when their wall clock
timestamps coincide. It runs immediately and again when that source revision changes.
A value that fails its contract is delivered as `null`; `page state` and `page check`
report why.
Return the cleanup function from the element's disconnect path. The callback must
state the whole rendering and remain idempotent.

Time readings made synchronously in controller, `watchData`, `watchUpdates`, and
`watchHistory` callbacks subscribe that paint to Leaf's shared clock. Calls to `ago`,
`shortAgo` and `quietSince` refresh the callback only when their result changes. `ago(ts)`
says how long ago `ts` was as the page words it everywhere ("2h ago"), and `shortAgo(ts)`
is the same reading for a tight seat ("2h"). `quietSince(ts)`
says whether working last heard at `ts` has gone unheard past the server's working
grace, the same bound the page's own activity reads. For another
rounded time reading, use `clockValue((now) => reading)`, whose `now` argument is the
calibrated server-now value in milliseconds. For a paint outside these
subscriptions, wrap it with `clocked(element, paint)` and call the returned function
where state changes; call its `.stop()` on disconnect. Time reads after an `await`
belong in a separate synchronous `clocked` paint. The timer does not reapply state or
redeliver unchanged data to keep a timestamp current.

`origin` identifies the declared `input`, concrete `source`, `contract`, and source
`revision`. An unchanged source keeps that origin when another source changes. Passing
`{snapshot}` to `projectData` supplies this default origin. When the emitter knows the
exact JSON coordinate within the source value, its `originOf(record, index)` returns
`{...snapshot.origin, path: [...]}`;
path segments are object keys or array indices. A formatted or parsed record may only
name its whole input. This identifies construction inputs, not an inverse edit mapping.

Render the value with `projectData(root, records, keyOf, render, options)`. The root is an
id-bearing authored seat and owns the projection's children. `keyOf` returns a
non-empty rendering key, unique in that projection; `render` receives
`(record, priorNode, index)` and returns its element, reusing `priorNode` where that
preserves a focused control or selection. Leaf marks those words as readable data
rather than authored prose and reconciles their order by key. A renderer
that owns a nested layout passes `{nested: true}` and returns its existing descendants;
Leaf labels those nodes without moving them, and the module orders each container with
`setChildren(parent, nodes)`, which moves only what is out of place and keeps the user
in a node it moves. For a subtree whose entire contents and descendant attributes
belong to the renderer, use `setRenderedChildren(parent, nodes)`: it matches unchanged
nodes and edits only changed text, preserving native selections in text the source kept.
Keep independently stateful controls outside that subtree. Add `labelOf(record, index)`
when a thread
should name a projected datum with a human coordinate; the rendering key remains opaque to
the runtime. A widget declaring `x-data` passes `{snapshot}` with the delivery from
`watchData`, including `null` when no current value exists. Leaf stamps the projection
with that snapshot's source and revision. Pass `identify(record, index)` when the
emitter can name the same subject across source replacements. Its non-empty string
need not equal the rendering key and must be unique within the projection; a comment
follows that subject and retains the quote from the value the user saw. A reused
identifier for a new subject needs a new identity. Other projected keys remain exact
only within the captured revision; replacing that value marks their placement outdated.
Derived projections omit `snapshot`
and retain their section/key identity. If a `watchData` callback renders asynchronously,
it returns that promise so Leaf publishes the source revision as ready only after the
projection settles. A rejection is reported as that subscriber's page
error; it does not make later state
reads repeat the same page-wide failure. A rejection from the callback's first run is
stronger: Leaf drops that subscription, so the callback is not asked to restate again
until the element is reconnected.

Leaf records the default origin or `originOf(record, index)` result as JSON in
`data-lf-origin` on each datum; a null origin removes any previous provenance. Derived records outside the data
store can instead name their contributing widget seats as `{derived: [{widget: id}]}`.
Leaf never infers them from displayed
text or datum keys.

## Reading and opening Threads from a widget

`readThreads()` returns the same immutable `{phase, threads}` collection the
Threads panel reads. `threads` contains conversations; a bare reaction record without
a spoken turn is not a listed Thread. `watchThreads(owner, callback)` calls a connected
widget with that collection initially and after relevant application updates; it returns a stop
function for `disconnectedCallback`. Each widget keeps its own search, filter, and
order state and derives its displayed rows from the collection. `threadTurns(thread)`
selects a Thread's displayed turns, and `threadSummary(thread)` gives its topic and
latest activity. An agent-authored message or closing event carries `agent`, the
name it is shown under. `openThread(thread.id)` takes the user to Leaf's canonical
conversation surface for that Thread. The widget does not need to render or own the
conversation to provide that route.

`threadActions` lets a package add its own controls over the current Thread reading
and Leaf's optimistic event path:

```js
threadActions.reply(thread.key, text);
threadActions.resolve(thread.key);
threadActions.reopen(thread.key);
threadActions.toggleReaction(thread.key, agentMessage.id, token);
```

Each method returns `null` when the current reading does not offer that action,
otherwise a promise resolving to the admitted event or `null` if admission refuses it.
The action changes `readThreads()` immediately; the server remains final. A reply
requires non-empty text. A reaction requires an addressable agent message and a token
in the current layer's vocabulary; pressing an already standing token takes it back.
Use the Thread's stable `key`, which survives admission of a locally opened Thread.
Leaf's reply editors keep one durable draft per Thread; a package input retains its
own draft.

## Rendering Threads in a widget

`mountThreadViews(owner, render)` lets a package supply containers for Leaf's core
conversation view. It registers one consumer per Element and returns a handle with
`read()`, `update()`, and `unregister()`. The callback receives the same immutable
Thread collection as `readThreads()` on its initial presentation and on later
publications. A Thread waiting on the user has unresolved
`attention.kind === "needs_user"`, which
includes recovery after a failed response; `"waiting"` means it is with the agent.
A Thread's `id` is the name Asks and workflows give it; its `root` is the first
message it still holds, whose id differs where the log lost the opening message.
Each Thread's `key` survives admission of a pending gesture, and its `anchor`
names the `section` (the widget's id) and `datum` it rests on. A returned promise
delays that widget's mirror repaint without holding up Leaf's panel, margin, or
read presentation. The second argument's `signal` is aborted when a newer render
supersedes it or the consumer unregisters. Asynchronous callbacks check it before
changing their UI. The owner unregisters on disconnect.

For a Thread list or dashboard, `surfaces.render(thread.key, outlet)` shows a
conversation in an Element inside the widget. Each widget chooses its own Threads,
containers, filters, and order. Several widgets may render the same Thread, and
removing one does not remove another's view. These are mirrors: they do not take the
Thread away from its page or margin position. Leaf renders the messages, reply editor,
reactions, resolution controls, and receipts. An authored message's interactive
widgets open in the Threads panel, as they do from other inline Thread views.

```js
this.threads = mountThreadViews(this, (collection, surfaces) => {
  for (const thread of collection.threads) {
    const outlet = this.outletFor(thread.key);
    if (outlet) surfaces.render(thread.key, outlet);
  }
});
```

The widget owns outlet creation and layout. Leaf requires every outlet to remain
inside its owner, and a consumer may render each Thread only once per callback.
The handle's `update()` requests a new render after a local layout change.

## Widget-local Thread placement

A widget declares `"x-thread-surface": true` to place Thread UI beside its own
projected data. Use `consumeThreads(owner, render)` with
`surfaces.place(thread.key, outlet)` for an exact datum and
`surfaces.placeComposition(outlet)` for its active composer. The callback
selects its Threads and hands each an outlet it owns. Here
`this.outletFor` stands for the widget's own method, which finds or creates the outlet
element beside the datum and returns `null` when the datum is not displayed
(`lf-diff`'s `threadOutletFor` is the worked example):

```js
this.threadSurface = consumeThreads(this, (collection, surfaces) => {
  for (const thread of collection.threads) {
    if (thread.anchor?.section !== this.id || !thread.anchor.datum) continue;
    const target = surfaces.target(thread.key);
    const outlet = target && this.outletFor(target);
    if (outlet) surfaces.place(thread.key, outlet);
  }
  const outlet = surfaces.composition && this.outletFor(surfaces.composition);
  if (outlet) surfaces.placeComposition(outlet);
});
```

`target(key)` returns `{anchor, placement}` only for an exact datum belonging to the
widget, otherwise `null`; `placement.datumElement` is the rendered datum. It also
returns `null` for a thread the agent starts at an on-screen datum where the widget
draws no thread yet, since the outlet it opened would move what the user is reading:
the thread waits in the margin until the user presses its marker, adds a turn of their
own, or scrolls the datum out of the window.
`composition` supplies the equivalent placement for the active composer, which may
precede any Thread. The widget owns outlet creation, removal, and layout.
Leaf validates target ownership and outlet containment before committing placements.
Core moves its one composer node or renders retained messages, replies, reactions,
settlement controls, and receipts into each outlet. A claimed thread does not also
appear in the margin projection; the Threads panel remains the complete index. With
Threads closed, `t`/`T` lands on this local surface before trying the margin-projection
fallback. Clicking the Threads toggle from the focused surface carries the same thread
into the panel.

The consumer omits placements for data that is filtered, collapsed, or not yet hydrated.
That keeps lazy widgets lazy and restores the margin-projection fallback. Deliberate thread
travel may reveal the datum through `lfRevealDatum`; the ordinary reconciliation pass
then invokes the consumer again. The registration handle's `update()` invalidates layout-only
visibility changes, and `unregister()` removes the surface when the widget disconnects.
If a callback throws, Leaf reports a page error, clears that registration's core-owned
views, and returns its threads to the margin. Other registrations continue, and the
next ordinary reconciliation retries the consumer. Outlets must remain inside their
widget after the callback completes; disconnected outlets claim no threads. Core message-rendering
errors still fail the state application rather than accepting a partial thread.

The registration handle's `open(datum, { origin })` accepts one projected element owned
by the widget. Core captures its full datum coordinate, including external-data source
revision, opens the ordinary anchored draft, and seats the response bar in the consumer's
outlet when the datum still resolves exactly. `origin` is the widget control to which
Escape may return focus. Widgets do not receive draft, submission, or event APIs.

## Page annotation presentation

With `data-annotations="page"` on `body`, one connected Element may register
`consumePageThreads(owner, render)` to nominate page-owned conversation outlets.
Its callback receives the current immutable Thread collection and the same
`target`, `place`, `composition` and `placeComposition` capabilities as a
widget-local surface. Page targets include exact passages and visual details,
as well as projected data. `target(key)` expresses candidacy: widget-local
outlets that survive final validation take priority. A held widget arrival stays
with its existing notice until the user opens it. Source-target coverage and
outlet containment are separate: the source may be elsewhere in the document,
but the outlet must stay inside its registered owner. Core validates both again
at the sole conversation/composer commit. Failure of this selected page callback
fails presentation instead of claiming an empty successful view.

The same owner can register `consumeAnnotations(owner, render)` for Asks,
updates, status and contributed actions. It receives the current immutable
inventory after the conversation cohort commits, plus these capabilities:

- `view.items(entry)` gives generated items not already represented by an owner's
  visible native contribution controls. `view.activate(item)` uses the current
  canonical action; a view never sends an event itself. Retain items by the
  exported `contributionItemKey(item)`: each contribution owns its reading IDs.
- `view.controls(entry)` returns the retained native contribution controls in
  canonical order. Seat those actual nodes; their registration owns activation,
  command scopes, disabled state and focus. `view.controlKey(control)` identifies
  that current control by its contribution owner and entry key;
  `view.controlRecord(control)` reads its canonical immutable contribution entry,
  including its owner. Do not copy markup.
- `view.arriving` says an explicit contribution focus is arriving at this view.
  Release held layout before seating that current reading so its control is reachable.
- `view.place(entry, row)` associates a contained row with its current source for
  commenting, standing and Escape. `view.target(entry)` reads that exact target.

Annotation paint is synchronous and joins the existing conversation presentation
proof. `controls` and `place` accept only entries in that paint's current reading;
holding layout never authorizes old actions. Both handles provide `read()`,
`update()` and `unregister()`. Unregister on disconnect. Retain keyed rows and
hold visible size changes with the shared `HeldReading` mechanism. Hold only layout
identities and allocations, while updating surviving records and controls immediately;
retired slots retain space with no interactive descendants. The bundled `lf-annotation-rail` is the worked
implementation. Omitting either consumer retains the core Threads and Asks routes.
