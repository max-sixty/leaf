# Commands, focus, and text entry

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

## Commands and keyboard routes

A widget declares its commands as data on the element they apply in: set the element's
`lfCommands` to the scope, `{title, rows, when}`, and call `commandsChanged(element)`.
Leaf reads the declaration then, and `commandsChanged` throws where a row is malformed.
Leaf binds its keys, lists them in the command reference
and hints, and is the only writer of `aria-keyshortcuts`; a page without Leaf reads
nothing, so a widget that also runs there (`module-authoring.md`, "A widget that also
runs off Leaf") binds no key. Declare at upgrade, once the element exists; it may still
be out of the page. Setting a new declaration and calling `commandsChanged` again
replaces the scope, and `null` withdraws it. `when` is optional.

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
for it and the line under its title where a touch menu or an On me card offers it. A
`decision: true` row answers an obligation, and `recommended: true` marks the answer
the page advises, which an On me card names.

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

`run(binding, context)` performs the command; a row without `run` names a press the
browser or an outer handler makes. `control` is the visible element that activates it.
`when` says whether it is available, and a route may have its own. `reach` is the short
phrase the command reference shows while it isn't, such as `in an open draft editor`.
Set `runFromCommandReference: false` for a step the reference can't run without a choice
it lacks. `ready` is described in `module-authoring.md`, "Startup and presentation".

Android's back gesture takes the step Escape would. A row whose `run` throws away words
the user wrote and hasn't sent, such as an editor's Escape, also declares `keep`, which
back runs instead: it closes the editor without losing the changed words. Where a press
away from the editor saves them, `keep` saves them too, as `lf-draft` does; otherwise it
keeps them where reopening finds them, shows that the widget holds them, and says so
with `notice("Edit kept")`.

Leaf re-evaluates a `when` or a computed field when the readings it uses change, such as
a widget's state or the threads. For any other state it reads, hold the value in a
`signal` or call `commandsChanged(element)` after changing it.

### How scopes compose

A key goes first to the scope on the focused control, then to the widgets around it,
then to the page. A scope takes only keys whose rows have a `run`, so other keys pass
outward. A row keeps its key while unavailable, so the key never falls through to a
different meaning further out; an unavailable Escape, though, passes on to the next
Escape. Text fields keep their editing keys ahead of every widget scope.

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
page keeps `m` and `Shift+m` for moving through On me.

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

- `"move"`: a route taking the user somewhere, such as to the next row;
- `"return"`: putting them back, as a widget's Escape does, or a redraw handing them to
  the control that replaced theirs;
- `"step"`: the widget's own Tab loop;
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
`whenLeft(element, leave)` runs `leave` once when focus
leaves an element. `onPressAway(away, dismiss)` hears each primary press that begins and
ends where `away(path)` is true of its composed path, as an open editor that a tap
elsewhere should save does, and calls `dismiss(path, from)` before the press's click; it
ignores a touch scroll the browser cancels, and returns its unsubscribe function. A group
the user moves through with arrow keys offers one Tab stop with `rove(items, stop)`.

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

### Delayed work

A widget's own navigation that waits, such as for a file or renderer to load, calls
`const intent = retainUserIntent()` in the gesture that starts it, before the first
wait. After every wait, it moves focus or scroll only if `intent()` is still true; it
turns false once the user presses, types, scrolls, leaves the window or moves focus. If
the navigation then opens or closes a surface that moves focus, wrap that change in
`intent.handoff(() => changeSurface())` so the move doesn't count as the user's; it
returns false if the change had already moved focus. `threadActions.open` handles this
itself (`module-annotations.md`, "Reading and opening Threads from a widget").

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

A control that shows only part of its word, with the whole in `title`, carries the class
`HOLDS_WORD`; a held finger reads the word, and the package's CSS shows it whole under
`data-lf-held-word`.

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
like a textarea and fires `input` only for the user's edits. `TEXT_FIELD` is its tag,
and `TEXT_BOX` matches it or a native textarea. The field matches `:state(ready)` once
it draws its words; where it replaces text the user was reading, leave that text in
place until then, so the scroller doesn't shrink.

Wire the box with `wireInput(box, options)`. Enter sends on a physical keyboard,
Shift+Enter writes a newline, and Mod+Enter sends anywhere; on a touch screen the
visible control sends. A box for one line, such as a name, carries
`aria-multiline="false"` before it is wired: Enter then sends from every keyboard, a
phone's included, Shift+Enter writes nothing, and a pasted line break becomes a space.
The options are `sendClass`, placement classes for the generated send control (default
empty); `sends`, its action in words; `hint`, the placeholder; `save(value)`, called with the whole draft on each
edit; `send(text, raw, owns)`, called on send with the trimmed and raw draft; `busy()`
and `hasContent(raw)`, which hold sending back. Write `.value` only to seed the box
before wiring it.

`wireInput` returns `sync`, which reads or sets the whole draft, a pasted image
included: `sync.value()` reads it, `sync.load(value)` replaces it, and `sync()` repaints
after the box's state changes. `sync.button` is the generated send control.

Drafts survive a reload, a new version and a closed tab, and every tab of the page
shares them. Keep each under a context string unique on the page, such as `option:` and
its id:

- `loadDraft(ctx)` returns the words to seed the box, or `null`.
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
