# Commands, focus, and text entry

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers commands and keyboard routes, focus, layers and pointer presses, and text entry with its drafts.

## Commands and keyboard routes

A widget declares each command once, at upgrade, with
`commands(element, title, rows, options)`. The key handler, shortcut bar, command
reference, `aria-keyshortcuts` and inline hints all read that one declaration. `options`
is the scope's `when`, alone or as `{when}`.

For controls Leaf draws, such as margin entries, build the scope as a value with
`commandScope(title, rows, options)` and put it on the entry's `scope`
(`module-annotations.md`, "Margin contributions"). Where the same commands also apply to
the widget's own elements, attach that value with `commands(element, scope)`:

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

In a template, `commandsOn(title, rows, options)` attaches a scope to the element it is
bound on, takes the current rows on each render, and detaches when the element goes.
Where the rows need the element, pass a function of it, such as
`commandsOn(title, (summary) => [{ keys: () => DISCLOSE(summary), … }])`.

### Command rows

Leaf checks each row as it is registered and throws for a malformed one.

A row's `id` is a stable, lowercase dotted name such as `draft.save`; keep it when keys
or words change. `title` names the command, `description` adds detail for the command
reference, `line` gives the shortcut bar a shorter word (`false` keeps the row off the
bar), and `label` replaces the keycap. `title` may be a function where state changes it.

`keys` lists bindings in canonical spelling, such as `"a"`, `"Shift+a"` or
`"Mod+Enter"`, or is a function returning them. `repeat: true` also runs on a held key's
repeats, and `native: true` runs without preventing the browser's default. Where one
row's keys mean different things, `routes` lists subcommands, each with its own `id`,
`title`, `binding` or `contextKeys`, and optional `when`; the command reference lists
and runs each route.

`run(binding, context)` performs the command; a row without `run` names a press the
browser or an outer handler makes. `control` is the visible element that activates it.
`when` says whether it is available, and a route may have its own. `reach` is the short
phrase the command reference shows while it isn't, such as `in an open draft editor`.
Set `runFromCommandReference: false` for a step the reference can't run without a choice
it lacks. `ready` is described in `module-authoring.md`, "Startup and presentation";
`decision` and `contextKeys` in "Decisions and forwarded keys" below; and `bindingBadge`
in "Inline shortcut hints".

Leaf re-evaluates a `when` or a computed field when the readings it uses change, such as
a widget's state or the threads. For other state it reads, hold the value in a `signal`
or call `paintKeys()` after changing it, since Leaf can't see a plain variable change.

### How scopes compose

A key goes first to the scope on the focused control, then to the widgets around it,
then to the page. A scope takes only keys whose rows have a `run`, so other keys pass
outward. A row keeps its key while unavailable, so the key never falls through to a
different meaning further out; an unavailable Escape, though, passes on to the next
Escape, which also means one step back. Text fields keep their editing keys ahead of
every widget scope.

A menu or other scope that covers the page passes `allButCommandReference` as its
`claims` option (`{ claims: allButCommandReference }`), so the page's keys wait while
the user is in it and only the command reference still opens.

Give a native button's row both `control` and `run`, and Leaf runs `run` for its click
and its key alike. Don't add a click listener, and don't call the button's own `click()`
from `run`. Put every condition in `when`: Leaf shows the button disabled with
`aria-disabled` and refuses the press while keeping focus there. Native inputs keep
their own activation and editing.

Leaf already answers Enter, Space and the opening arrow on a `details > summary` or a
button with `aria-expanded`. A row that names the same press uses `DISCLOSE(element)` as
its `keys`. `rowArrows(node)` returns `[back, ahead]` arrow keys for the text direction,
and `PRESS` is Enter and Space. `labelOf(row)` is the key text a row shows, for a
tooltip, and `saying(rows)` words what a set of rows answers, for an announcement.

### Decisions and forwarded keys

`keys` work inside the widget. `contextKeys` work there too, and Leaf also forwards them
from the enclosing ask's question and from its margin controls and threads. Number a
widget's choices by the choice, not by what is available: a classifier declares Pass as
`1` and Keep as `2`, and disabling `1` must not turn `2` into something else. The page
keeps `m` and `Shift+m` for moving through On me.

`decision: true`, which needs a `control`, marks a command that starts, advances,
answers or revises the ask holding it; it forwards no keys by itself. A forwarded key
runs the original row, if available. Register each command once, not on every nearby
button.

### Inline shortcut hints

To show a command's key on the page, set `bindingBadge` on its row or route: an empty
element the widget positions in or beside its control, or `null` for a badge at the
control's corner. Leaf gives the element the class `lf-binding-seat`, which keeps it
absolutely positioned, and writes the key into it while the key works. A command with
`contextKeys` and no badge has a key nothing shows, and `leaf package check --render`
reports it (`shows-context-keys`, packages.md, "Seeing it").

### Walks

A list of focusable rows gets its arrow keys from `rowWalk({id, noun, plural, rows})`,
whose two returned rows go into the list's scope: ArrowUp and ArrowDown step, Home and
End reach the ends, and each step announces a position such as `Option 3 of 7`. `rows()`
returns the list at each press, `landed(row)` runs after a move, and `scroll: false`
keeps the page still.

A widget that steps through something itself, such as a diff's hunks, calls
`beginWalk(key, noun, read)` at each step and announces what it returns, such as
`Hunk 3 of 7`. `read()` returns the position, usually from
`listWalkPosition(items, current, {identity})`. A step that lands where the last one did
shows the walk has reached its end.

### Go-to targets

Every visible button, checkbox, radio or selectable control a widget builds with
`offer()` or `selectableOffer()` is a target the `g` key reaches, with nothing more to
declare. Text and range inputs stay ordinary Tab stops.

## Focus and layers

Move focus with `focusDestination(element, cause)`, never `element.focus()`. The cause
tells Leaf why focus moved:

- `"move"`: a route taking the user somewhere, such as to the next row;
- `"return"`: putting them back, as a widget's Escape does, or a redraw handing them to
  the control that replaced theirs;
- `"step"`: the widget's own Tab loop;
- `"press"`: landing on a control to press it for them.

A return marked as a move looks like the user arriving, and can release held news or
open options they never went to. An element that isn't a control gets a Tab stop for as
long as it has focus. `{caret: [start, end, direction]}` places a text field's caret.
Moving focus never scrolls; reveal the destination with `scrollIntoView`
(`module-scroll-and-motion.md`, "Scrolling to a destination").

Before hiding or replacing nodes the user may be in, as a redraw that rebuilds a row
does, call `const restore = holdFocus(scope)`, and call `restore?.()` after: `holdFocus`
returns `null` when the user is outside `scope`. Moving nodes needs no hold
(`module-authoring.md`, "Retained nodes"). `restore` puts the user back on the same
node, or on a stand-in passed to it, unless they have gone elsewhere since. For a keyed
list, `holdFocus(list, { key })` names the attribute holding each item's key, and the
user lands on the same item, or the nearest survivor.

A live revision moves focus from a generated control to its replacement by a
`data-lf-carry` key, unique within the control's nearest authored ancestor with an id.

`focused()` is the focused element across shadow trees, and `standingIn(scope)` says
whether focus is in a scope. `whenLeft(element, leave)` runs `leave` once when focus
leaves an element. A group the user moves through with arrow keys offers one Tab stop
with `rove(items, stop)`.

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
turns false once the user presses, types, scrolls, leaves the window or moves focus, so a
user who moved on isn't pulled back. If the navigation then opens or closes a surface
that moves focus, wrap that change in `intent.handoff(() => changeSurface())` so the
move doesn't count as the user's; it returns false if the change had already moved
focus. `threadActions.open` handles this itself (`module-annotations.md`, "Reading and
opening Threads from a widget").

### Pointer presses

A handler that takes over a click, such as a link that opens a source line, acts only on
`plainPress(event)`, the primary button with no modifier, so a modified click keeps its
usual meaning.

A control labelled with the page's own words skips a click where
`reachedForWords(control)` is true: the user was selecting the words. It lets a click
made with Enter or Space through, checking `pressIsKeyboardActivation(event)` first. A
container that takes a click anywhere on it, as an option card does, asks
`worksInside(event.target, container)` for the control inside that the click was aimed
at.

A control that shows only part of its word, with the whole in `title`, carries the class
`HOLDS_WORD`; a held finger reads the word, and the package's CSS shows it whole under
`data-lf-held-word`.

Call `dragging(this, true)` when the user starts dragging the widget and
`dragging(this, false)` when the drag ends, is cancelled or the widget disconnects.
Meanwhile the page applies no revision or undo. A widget whose drag moves its own nodes
holds its drawing with `defer()` (`module-state.md`). `motionPreview(label)` makes the
image that follows the pointer.

A surface that must stop moving before Leaf handles a gesture, such as a playing
animation, subscribes with `onUserInput(callback)`, which runs before Leaf handles each
press, key, input, wheel or touch, or the window losing focus. Leaf calls it for every
such event on the page, so act only on events whose target is in the surface. The
callback doesn't consume the event; call the returned function when the surface
disconnects.

Before a drawing stroke reads its coordinates, Leaf dispatches `lf-inspect` on the
element drawn on; a moving visual listens for it and freezes what it shows.

## Text entry and drafts

A widget's own text box is `offer(TEXT_FIELD)`, Leaf's Markdown editor, which shows the
draft as the sent message will read, behaves like a textarea, and fires `input` only for
the user's edits. `TEXT_FIELD` is its tag, and `TEXT_BOX` matches it or a native
textarea. The field matches `:state(ready)` once its editor exists. When the field
replaces text the user was reading, leave that text in place until the field is ready,
so the scroller doesn't shrink.

Wire the box with `wireInput(box, options)`. Enter sends on a physical keyboard,
Shift+Enter writes a newline, and Mod+Enter sends anywhere; on a touch screen the
visible control sends. The options are `sendBtn`, the send control; `sends`, its action
in words; `hint`, the placeholder; `save(value)`, called with the whole draft on each
edit; `send(text, raw, owns)`, called on send with the trimmed and raw draft; `busy()`
and `hasContent(raw)`, which hold sending back; and `paint()`, the widget's own drawing
from the box. Write `.value` only to seed the box before wiring it.

`wireInput` returns `sync`, the way to read or set the whole draft, which can hold a
pasted image as well as words. `sync.value()` reads it, `sync.load(value)` replaces it,
and `sync()` repaints after the box's state changes.

The words survive a reload, a new version and a closed tab, and every tab of the page
shares them. Keep them under a context string unique on the page, such as `option:` and
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
- `clearDraft(ctx)` drops the draft, as Cancel does.

`lf-options`' box for adding an option (`lf-options-addition.js`) is the worked example.

For a CodeMirror editor, construct `LeafEditorView` in place of `EditorView`, so focus
and reveals go through Leaf.
