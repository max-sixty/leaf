# Commands, focus, and text entry

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Commands and keyboard routes

A widget declares its commands as data on the element they apply in: set the element's
`lfCommands` to the scope and call `commandsChanged(element)`. The scope holds `title`,
the heading the command reference lists it under, and `rows` ("Command rows"). It may
also hold `when`, whether the page has the scope at all, which gates the reference as a
row's own `when` gates its press; `ready` (`module-authoring.md`, "Startup and
presentation"); `claims` ("How scopes compose"); and `escape: "inner"`, for a scope
whose own Escape step comes before every step outside it.

Leaf reads the declaration when `commandsChanged` runs, binds its keys, lists them in
the command reference and hints, and is the only writer of `aria-keyshortcuts`. A page
without Leaf reads nothing, so a widget that also runs there (`module-authoring.md`, "A
widget that also runs off Leaf") binds no key. Declare at upgrade, once the element
exists; it may still be out of the page.

Assigning a new object to `lfCommands` and calling `commandsChanged` replaces the
scope, and Leaf checks the new rows then: `commandsChanged` throws where one is
malformed. `null` withdraws the scope. Calling `commandsChanged` with the same object
only has Leaf read its rows' titles and availability again, so a row or title edited in
place goes unchecked; assign a new object to change them.

```javascript
this.lfCommands = {
  title: "On a code block",
  rows: [{ id: "code.wrap", keys: ["w"], title: "wrap lines", run: toggleWrap }],
};
commandsChanged(this);
```

For controls Leaf draws, such as margin entries, build the scope as a value with
`commandScope(title, rows, options)` and put it on the entry's `scope`
(`module-annotations.md`, "Margin contributions"). Where the same commands also apply to
the widget's own elements, that value is their `lfCommands`:

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
classifier.lfCommands = actions;
commandsChanged(classifier);
```

In a template, `commandsOn(title, rows, options)` attaches a scope to the element it is
bound on, takes the current rows on each render, and detaches when the element goes.
Where the rows need the element, pass a function of it, such as
`commandsOn(title, (summary) => [{ keys: () => DISCLOSE(summary), … }])`.

### Command rows

A row's `id` is a stable, lowercase dotted name such as `draft.save`; keep it when keys
or words change. `title` names the command and may be a function where state changes
it, and `label` replaces the keycap. `description` is the command reference's tooltip
for it and the line under its title where a touch menu or an On Me card offers it. A
`decision: true` row answers an obligation, `recommended: true` marks the answer
the page advises, which an On Me card names, and `commits: true` marks the press that
commits an answer the user composed, such as a group's Done, which an On Me card draws
as that commit rather than as one more answer.

`keys` lists bindings in canonical spelling, such as `"a"`, `"Shift+a"` or
`"Mod+Enter"`, or is a function returning them. `repeat: true` also runs on a held key's
repeats, and `native: true` runs without preventing the browser's default.
`travels: true` marks a command that takes the user somewhere, such as a step to the
next item, so its result may scroll away the control it was pressed on; every other
command leaves that control where it stood on screen, unless it brings the control
whole into a scroller that showed only part of it. Where one
row's keys mean different things, `routes` lists subcommands, each with its own `id`,
`title`, `binding` or `contextKeys`, and optional `when`; the command reference lists
and runs each route.

`run()` performs a command whose meaning is independent of its key. Use
`runKey(binding)` instead when the binding determines the action; Leaf supplies the
actual binding that invoked it, including when the command reference selects a route.
A row declares at most one of these handlers. A row without either names a press the
browser or an outer handler makes, and one that names a `control` is pressed by a
click on it. `control` is the visible element that activates it. `lands(from)` says
where the user stands after Leaf runs the row for a key, a command-reference pick or
a click on its `control`: Leaf calls it right after the run, so it reads the state the
run left, with the element the press came from (where the user was for a key or a
pick, the button for a click), and puts the user on the element it returns as a move,
or leaves them for `null`. A margin entry's activation keeps its own focus handling.
`when` says whether it is available, and a route may have its own. `reach` is the short
phrase the command reference shows while it isn't, such as `in an open draft editor`.
Set `runFromCommandReference: false` for a step the reference can't run without a choice
it lacks. `ready` is described in `module-authoring.md`, "Startup and presentation".

Android's back gesture takes the step Escape would. A row whose `run` throws away words
the user wrote and hasn't sent, such as an editor's Escape, also declares `keep`, which
back runs instead: it closes the editor without losing the changed words. Where a press
away from the editor saves them, `keep` saves them too, as `lf-draft` does; otherwise it
keeps them where reopening finds them and shows that the widget holds them.

Leaf re-evaluates a `when` or a computed field when the readings it uses change, such as
a widget's state or the threads. For any other state it reads, hold the value in a
`signal` or call `commandsChanged(element)` after changing it.

### How scopes compose

A key goes first to the scope on the focused control, then to the widgets around it,
then to the page. A scope takes only keys whose rows make a press, by a `run` or by
naming a `control` Leaf clicks, so other keys pass outward. A row keeps its key while unavailable, so the key never falls through to a
different meaning further out; an unavailable Escape, though, passes on to the next
Escape. Text fields keep their editing keys ahead of every widget scope. A key other
than typing or Escape, pressed while the user has scrolled the focused control out of
sight, lets go of the control first and goes to the page, so neither a widget's command
nor the browser's own Enter and Space acts on what the user can't see. That key stops at
the document, so a listener on the control or the widget doesn't hear it, and a script's
own listener on the document or window hears it only in capture.

A menu or other scope that covers the page gives `allButCommandReference` as its
declaration's `claims`, so the page's keys wait while the user is in it and only the
command reference still opens.

Give a native button's row both `control` and `run`, and Leaf runs `run` for its click
and its key alike. Don't add a click listener, and don't call the button's own `click()`
from `run`. Put every condition in `when`: Leaf shows the button disabled with
`aria-disabled` and refuses the press while keeping focus there. Native inputs keep
their own activation and editing.

Leaf already answers Enter, Space and the opening arrow on a `details > summary` or a
button with `aria-expanded`; a row that names the same press uses `DISCLOSE(element)` as
its `keys`. `rowArrows(node)` returns `[back, ahead]` arrow keys for the text direction,
and `PRESS` is Enter and Space. `labelOf(row)` is the key text a row shows, for a
tooltip, and `saying(rows)` words what a set of rows answers, for an announcement.

A flex or grid summary draws no native marker. Give it, or an `aria-expanded` button,
the `lf-disclosure-marker` class, and it shows the one every disclosure on the page
shows, as its `::before`, turning with its state; the widget's own rules place it.

### Decisions and forwarded keys

`keys` work inside the widget. `contextKeys` work there too, and Leaf also forwards them
from the enclosing `lf-ask`'s question and from its margin controls and threads. Number
a widget's choices by the choice, not by what is available: a classifier declares Pass
as `1` and Keep as `2`, and disabling `1` must not turn `2` into something else. The
page keeps `m` and `Shift+m` for moving through On Me.

`decision: true`, which needs a `control`, marks a command that starts, advances,
answers or revises the obligation holding it; it forwards no keys by itself. A forwarded
key runs the original row, if available, so register each command once, not on every
nearby button.

### Inline shortcut hints

To show a command's key on the page, set `bindingBadge` on its row or route: an empty
element the widget positions in or beside its control, or `null` for a badge at the
control's corner. Leaf gives the element the class `lf-binding-seat`, which positions it
absolutely, and writes the key into it while the key works. `leaf package check
--render` reports a command with `contextKeys` and no badge (`shows-context-keys`,
[packages.md, "Seeing it"](packages.md#seeing-it)).

### Walks

A list of focusable rows gets its arrow keys from `rowWalk({id, noun, plural, rows})`,
whose two returned rows go into the list's scope: ArrowUp and ArrowDown step, Home and
End reach the ends, and each step announces a position such as `Option 3 of 7`. `rows()`
returns the list at each press, `landed(row)` runs after a move, and `scroll: false`
keeps the page still.

A row whose press carries the user along a list of its own, as a timeline's arrows
carry a user on its step list to the new step's row, declares `lands(from)` ("Command
rows") rather than moving focus in its `run`.

A widget that steps through something itself, such as a diff's hunks, calls
`beginWalk(key, noun, read)` at each step and announces what it returns, such as
`Hunk 3 of 7`. `read()` returns the position, usually from
`listWalkPosition(items, current, {identity})`. A walk that comes round at its ends
steps with `cycledRow(items, current, direction)`, which returns the item it lands on.

### Go-to targets

Every visible button, checkbox, radio or selectable control a widget builds with
`offer()` or `selectableOffer()` is a target the `g` key reaches, with nothing more to
declare.

## Focus and layers

Move focus with `focusDestination(element, cause)`. The cause tells Leaf why focus
moved:

- `"move"`: a route taking the user somewhere, such as to the next row, whose landing
  previews nothing ("Previews");
- `"return"`: putting them back, as a widget's Escape does, or a redraw handing them to
  the control that replaced theirs;
- `"step"`: the widget's own Tab loop, whose landing previews as Tab's does;
- `"press"`: landing on a control to press it for them.

A return marked as a move looks like the user arriving, and can release held news or
open options they never went to. An element that isn't a control gets a Tab stop while
it has focus. `{caret: [start, end, direction]}` places a text field's caret. Moving
focus never scrolls; reveal the destination with `scrollIntoView`
(`module-scroll-and-motion.md`, "Scrolling to a destination").

Before hiding or replacing nodes the user may be in, as a redraw that rebuilds a row
does, call `const restore = holdFocus(scope)`, and call `restore?.()` after; `holdFocus`
returns `null` when the user is outside `scope`. Moving nodes needs no hold
(`module-authoring.md`, "Retained nodes"). `restore` puts the user back on the same
node, or on a stand-in passed to it, unless they have gone elsewhere since. For a keyed
list, `holdFocus(list, { key })` names the attribute holding each item's key, and the
user lands on the same item, or the nearest survivor.

A live revision moves focus from a generated control to its replacement by a
`data-lf-carry` key, unique within the control's nearest authored ancestor with an id.

`focused()` is the focused element across shadow trees, and `currentLocationIn(scope)` says
whether focus is in a scope. `placeOf(node)` returns the page node a place stands for,
so focus on a margin entry or in a thread card reads as being at its passage or
obligation; a module asks it whether the user is on its content from either.
`onPressAway(away, dismiss)` hears each primary press that begins and
ends where `away(path)` is true of its composed path, as an open editor that a tap
elsewhere should save does, and calls `dismiss(path, from)` before the press's click; it
ignores a touch scroll the browser cancels, and returns its unsubscribe function. A group
the user moves through with arrow keys offers one Tab stop with `rove(items, stop)`.

`onPress(begin)` follows the primary pointer's press through its native compatibility
events. `begin(pointerdown, path)` may return `end(event, completed)`: release calls
it with `completed: true`; cancellation, a native context menu, or leaving the document
calls it with `false`. The function returned by `end` runs when that press is over,
after any compatibility mouseup and click it owes. Keep press-local work in these
callbacks. Register inside `whileConnected`; the returned unsubscribe stops new
presses, and the connection's abort signal ends any work still running when the widget
disconnects.

`onCurrentLocation(read)` calls `read(node, cause, left)` synchronously when focus
changes, including inside a declared shadow root, and returns its unsubscribe function;
register it inside `whileConnected` and call that function in the cleanup. The causes
are `return`, `press`, `step`, `move`, and `drop`; a dropped place is `null`.

The current location is marked by `data-lf-focus`, and its composed ancestry by
`data-lf-focus-within`. Draw focus rings from `data-lf-focus-visible` and
`data-lf-focus-visible-within` instead. Controls and reading destinations follow the
browser's `:focus-visible`, and keyboard routes request visible focus, so a
pointer-focused control can reveal its actions without a keyboard ring; text editors
show their entry cue. The same names without `data-` are public shadow parts.

A box that shows the focus of a control inside it, as a row rings its checkbox, is
named by the control: declare `--lf-focus-box` in the control's rule, as a selector,
such as `.row > input { --lf-focus-box: .row; }`. Leaf marks the nearest box around
the focused control that matches it `data-lf-control-focus`, and
`data-lf-control-focus-visible` while the focus is visible, so the box's rule reads its
own attributes. Don't ask with `:has()` where focus is, by a mark or by `:focus`: in
Chromium that makes every focus move restyle the page.

### Layers

A widget opening its own layer, such as a list over its contents, calls
`openLayer(layer)`, which records where focus was, and closes it with
`closeLayer(close, land)`. `close` hides it, and `land` puts the user where closing takes
them, usually `() => handBack(openerOf(layer))`. `handBack(...destinations)` lands on the
first destination that can take focus. The layer's Escape is an ordinary command row.

Open a native dialog or popover with `showNativeLayer(layer, {source})`, adding
`modal: false` for a nonmodal dialog, and close it with `closeNativeLayer(layer)`.
Inside a live sample they suppress the browser's own focus moves, so place the arrival
with `focusDestination`. `isNativeLayer(node)` says whether a popover is open or a
dialog modal.

A control that opens a popover, such as a menu of choices, names it with
`popovertarget`, or passes itself as the source of `showNativeLayer(popover, {source})`.
Leaf puts the user on a `popovertarget` control as the popover opens, so closing it
returns them there. Every such control declares `aria-expanded="false"`, and Leaf keeps
it current as the popover opens and closes, however it opened. To land the user on a
control inside the popover, call `focusDestination(control, "move")` from the
popover's `toggle` event when its `newState` is `"open"`. The `lf-popover` class gives an open
popover Leaf's raised surface and names it as the ground its controls paint; its own
rule sets only its place, size and padding.

### Delayed work

A widget's own navigation that waits, such as for a file or renderer to load, calls
`const intent = retainUserIntent()` in the gesture that starts it, before the first
wait. After every wait, it moves focus or scroll only if `intent()` is still true; it
turns false once the user presses, types, scrolls, leaves the window or moves focus. If
the navigation then opens or closes a surface that moves focus, wrap that change in
`intent.handoff(() => changeSurface())` so the move doesn't count as the user's; it
returns false if the change had already moved focus. `threadActions.open` handles this
itself (`module-annotations.md`, "Reading and opening Threads from a widget").

### Previews

Pointing reads; pressing acts (`interface-goals.md`). Leaf previews an element when a
pointer rests on it, when Tab brings the keyboard to it or something inside it, and when
a finger holds it, beside the element over the page, in one face: a name with key chips,
then lines of detail. A command's landing, such as a walk's, previews nothing, since
what the user asked the command for is in front of them ("Focus and layers"). The preview holds no control, so a control the user presses stays
on the widget; a pointer may cross onto it to read it, and a finger's long press reads
it and presses nothing, so a widget's click answers a tap alone.

A control needs no declaration. It previews its accessible name where its face shows a
symbol or doesn't say that name, and as chips each key that presses it from where the
user is, as the attribute `aria-keyshortcuts` says it. A control whose face says its name
and that no key reaches previews nothing. Its
`aria-description` stays a screen reader's; a line the eye should read too goes in
`detail`.

A widget adds to that, or previews an element that isn't a control, by declaring the
element's `lfPreview(route)`, with no import, as it declares `lfCommands`. Leaf calls it
once each time the preview shows, with the route that asked: `"pointer"`, `"focus"` or
`"hold"`, and again for each new presentation of the document while the preview
stands, so what it says follows the page without tracking its own inputs; words that
come back the same leave the preview as it is. It returns:

- `{name, keys, detail, list, at, about, excerpt}`, every field optional. `name`
  replaces the control's accessible name in the preview, or names an element that has
  none. `keys`
  lists presses the register can't see, each as the steps its chips draw, as a control's
  own activation keys a drag grip names. `detail` is lines under the name, each words or
  an `html` template; a falsy line is left out. `at` is where the preview stands, the
  declaring element by default: another element, as a message's age stands its preview
  by its `<time>`, or a box in client coordinates (`{left, top, right, bottom}`, such as
  a `DOMRect`) inside the element, as a chart's value stands over its point, which the
  preview stands above and takes no pointer, so the pointer goes on reading the element
  beneath it. `about` is the element the preview is about, which Leaf leaves
  in view as it places the preview, as a margin entry's passage or a time's message;
  the box it stands by is always left in view, and the preview shows only while some
  of that box does, so a point scrolled out of view takes its preview with it, though
  its element still shows, and a focus preview comes back as it returns.
  `excerpt: true` gives a preview that quotes a block of the page the face's wider room. A preview taller than the room beside its element shows the
  lines that fit and ends the last in an ellipsis; no preview scrolls, so what pressing
  the element opens says the rest. `list: {items, more}` is items under the lines, each
  words or a template, as the threads standing at one place: Leaf shows as many as the
  room holds, through every resize, and under them `more(count)`'s words for the rest,
  such as "and 26 more threads", so the items need no measuring of their own; the rest
  are hidden from sight and from a screen reader alike.
- `null` where the element adds nothing now, including where the words it would say
  already show on it or beside it: a control keeps its own preview, and the search goes
  on to what holds the element.
- `false` where nothing should preview here or around it, as a pinned card already
  shows what its phrase would.

What it throws is reported, and nothing shows. Where what an element previews changes
while the user's aim stays on it, as a chart's pointer, key or finger reaches another
point, or a grip's words stop being true once its card is grabbed, the widget calls
`previewChanged(element)`, from `portable-api.js` (`widget-api.js` re-exports it): Leaf
calls `lfPreview` again and redraws a standing preview where it stands, or shows the
new one to a pointer resting on the element or a finger holding it, and off Leaf the
call does nothing. It never brings back a preview the user put away, nor opens one on
focus: only the user aiming again does. Where the user aimed at something new inside the
element, as a chart's pointer or arrow key reaching another point, the widget says so,
`previewChanged(element, {aim: true})`, and the new target shows its preview whatever
put the last one away, to the pointer, the keyboard's focus or a finger. A mark the widget draws for what its preview
reads, as a chart's ring on the point it names, comes off when Leaf dispatches
`PREVIEW_ENDED` (`"lf-preview-ended"`, from the same module) at the element, a
`CustomEvent` whose `detail.declared` is the object `lfPreview` returned for the
reading that ended, as the preview goes for any reason: the pointer or focus leaving,
the pointer leaving the window, the next touch after a finger's hold, Escape, or
another target's preview taking its place. A focus preview hidden while the box it
stands by is out of sight hasn't ended, so the mark stays. `lfPreview` returns a new
object for each reading, since that object is how a widget tells the reading that ended
from one it has returned since. A redraw with new words is no ending. A widget that has returned a
newer reading since, as focus arriving reads the point a pointer's preview had, keeps
the mark for that one.

A `title` stays the browser's: a pointer over an element with one, or inside one, gets
the browser's tooltip and no preview, and focus and a finger, which the browser's
tooltip never reaches, read its words in the preview. Leaf neither writes nor removes
it. A widget that wants Leaf's face for the pointer too, its key chips included,
declares the words in `lfPreview` and writes no `title`. Off Leaf nothing reads
`lfPreview`.

A thread's words preview the thread to a pointer or a finger only where nothing else
there takes the pointer: a control, native or ARIA, an element with a `title` or an
`lfPreview`, or a widget that draws its content itself (`x-content` `data` or
`empty`). There the element's own preview shows, or none, and the thread is reached
by its margin entry. Words a widget holds of the author's markup, outside any control
in it, preview their thread.

A link an author wrote to a place on the page previews that place with no declaration.
A link a widget draws previews nothing of the place unless the widget declares it,
since only the widget knows whether its words already say what the place holds; to
show the place, return `placePreview(element)`, the name, first lines, answer and
threads Leaf shows for an authored link.

### Pointer presses

A handler that takes over a click, such as a link that opens a source line, acts only on
`plainPress(event)`, the primary button with no modifier, so a modified click keeps its
usual meaning.

A control labelled with the page's own words skips a click where
`reachedForWords(control)` is true, since the user was selecting the words, but lets a
click made with Enter or Space through, checking `pressIsKeyboardActivation(event)`
first. A container that takes a click anywhere on it, as an option card does, asks
`worksInside(event.target, container)` for the control inside that the click was aimed
at.

Call `dragging(this, true)` when the user starts dragging the widget and
`dragging(this, false)` when the drag ends, is cancelled or the widget disconnects;
meanwhile the page applies no revision or undo. A widget whose drag moves its own nodes
holds its drawing with `defer()` (`module-state.md`, "The widget controller").
`motionPreview(label)` makes the image that follows the pointer.

A surface that must stop moving before Leaf handles a gesture, such as a playing
animation, subscribes with `onUserInput(callback)`, which runs before Leaf handles each
press, key, input, wheel or touch on the page, or the window losing focus. Act only on
events whose target is in the surface; the callback doesn't consume the event. Call the
returned function when the surface disconnects.

Before a drawing stroke reads its coordinates, Leaf dispatches `lf-inspect` on the
element drawn on; a moving visual listens for it and freezes what it shows.

## Text entry and drafts

A widget's own text box is `offer(TEXT_FIELD)`, Leaf's Markdown editor, which behaves
like a textarea and fires `input` only for the user's edits. `TEXT_FIELD` is its
tag. The field matches `:state(ready)` once
it draws its words; where it replaces text the user was reading, leave that text in
place until then, so the scroller doesn't shrink.

Wire the box with `wireInput(box, options)`. Enter sends on a physical keyboard,
Shift+Enter writes a newline, and Mod+Enter sends anywhere; on a touch screen the
visible control sends. A box for one line, such as a name, carries
`aria-multiline="false"` before it is wired: Enter then sends from every keyboard, a
phone's included, Shift+Enter writes nothing, and a pasted line break becomes a space.
The options are `sendClass`, placement classes for the generated send control (default
empty); `sends`, its action in words; `hint`, the placeholder, after which a focused box on a physical keyboard names its send key and, where Enter sends a box that holds lines, the key for a new line; `save(value)`, called with the whole draft on each
edit; `send(text, raw, owns)`, called on send with the trimmed and raw draft; `busy()`
and `hasContent(raw)`, which hold sending back. Write `.value` only to seed the box
before wiring it.

`wireInput` returns `sync`, which reads or sets the whole draft, a pasted image
included: `sync.value()` reads it, `sync.load(value)` replaces it, and `sync()` repaints
after the box's state changes. `sync.button` is the generated send control.

Drafts survive a reload, a new version and a closed tab, and every tab of the page
shares them. Keep each under a context string unique on the page, such as `option:` and
its id:

- `loadDraft(ctx)` returns the stored draft record, or `null`. Seed the box with
  `loadDraft(ctx)?.text ?? ""`; its `payload` holds the saved send data.
- `saveDraft(ctx, text, payload)` records an edit, from `save`, with any `payload` the
  send needs.
- `watchDraft(ctx, callback, {input: box})` calls `callback(text, payload)` when the
  draft changes other than by typing in this box: another tab, a send emptying it, or a
  refusal returning the words. Put them in the box with `sync.load(text ?? "")`, and
  register the watch in `whileConnected`.
- `sendDraft(ctx, owns, send)`, called from `send`, calls your `send(attempt, payload)`
  if the box still shows the stored draft and `owns()` is true, and resolves to the
  delivery's result. One `attempt` stands for one version of the words, so a resend
  after a reload reuses it.
- `clearDraft(ctx)` drops the draft, as Discard does.

`lf-options`' box for adding an option (`lf-options-addition.js`) is the worked example.

For a CodeMirror editor, construct the class `leafEditorView(codemirror)` returns in
place of `EditorView`, so focus and reveals go through Leaf. Pass the module your widget
imports (`import * as codemirror from "/vendor/codemirror.esm.js"`).
