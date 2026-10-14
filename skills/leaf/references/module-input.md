# Commands, focus, and text entry

Read with [module-authoring.md](module-authoring.md), which holds what every behavior module owes. This file covers commands and keyboard routes, focus, layers and pointer presses, and text entry with its drafts.

## Commands and keyboard routes

A widget contributes each command once with `commands(element, title, rows, options)`,
at upgrade. The dispatcher, shortcut bar, command reference, `aria-keyshortcuts` and
inline hints all read those same declarations. `options` is the scope's own `when`
predicate, alone or as `{when}`.

`commandScope(title, rows, options)` declares the same scope as a capability, for
controls Leaf rather than the widget creates: put it on a margin entry's `scope`
(`module-annotations.md`, "Margin contributions"), and each projection attaches it
to its own visible control.
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
| `ready` | Whether the command's input is complete (`module-authoring.md`, "Startup and presentation"). A route may declare its own. |
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

What a `when` or a computed field reads from Leaf's readings, such as a widget's state,
the Questions or the threads, is tracked, and a widget's own render repaints the keys
inside it. Hold other private state they read in a `signal`, which is tracked the same
way, or call `paintKeys()` after it changes, since a plain closure over it is not
reactive; every projection of the commands then updates together.

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

A scope standing over the page, such as a menu a widget opens, passes
`allButCommandReference` as its `claims` option
(`commandsOn(title, rows, { claims: allButCommandReference })`), so while the user
stands in it the page's own keys wait, as they do in Leaf's own menus, and only the
command reference reaches past it.

A native button with a row's `control` and `run` has one activation path: Leaf invokes
`run` for both its click and its keyboard command, and paints its disabled state from
`when`. Remove a separate click listener and disabled painter, and run the semantic
action directly in `run`, never the same button's `click()`. Express every condition in
the row's, route's or scope's `when`: Leaf paints `aria-disabled` and guards activation,
so a refused press keeps focus, and the button's own `disabled` attribute is an output. A
disabled fieldset still constrains the button. Native inputs keep their platform
activation and editing behavior; a row that focuses an editor or activates a checkbox
does not replace it. Generated margin controls use the same callback
(`module-annotations.md`, "Margin contributions").

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
must not turn `2` into a different action. The page owns `m` and `Shift+m` for moving
through the user's On me list.

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
`scrollIntoView` (`module-scroll-and-motion.md`, "Scrolling to a destination"). In an embedded sample, it places focus
only while that child owns input.

A module that hides or replaces nodes the user may be standing in, as a re-render that
rebuilds a row does, calls `holdFocus(scope)` before the change and the function it
returns after it; moves keep the user's place themselves (`module-authoring.md`, "Retained nodes"). `holdFocus`
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
(`module-annotations.md`, "Reading and opening Threads from a widget").

### Pointer presses

A handler that takes over a press, as a link that travels to a source line does, acts
only on `plainPress(event)`: the primary button with no modifier. A modified press keeps
its platform meaning, such as a new tab or a context menu.

A control whose label is the page's own words checks `reachedForWords(control)` in its
click handler: true means the press ended a text selection on the control, so the user
was taking the words rather than pressing. A click the keyboard made, Enter or Space on
the control, took no words, so the handler asks `pressIsKeyboardActivation(event)` first
and lets that click through. A container that takes a press anywhere on its
box, as an option card does, first asks `worksInside(event.target, container)`, which
returns the control or widget inside it the press was aimed at, or `null` where the
container is the aim.

A control that shows only part of its word, with the whole in its `title`, carries the
class `HOLDS_WORD`. A finger held on it reads the word, and releasing presses it. While
the press is held the control has `data-lf-held-word`, and the package's CSS shows the
whole word in that state as it does under keyboard focus.

A widget the user drags calls `dragging(this, true)` as the drag starts and
`dragging(this, false)` as it ends, is cancelled, or the widget disconnects. While any
drag is held, the page takes no new revision and no undo, and a widget whose drag moves
its own nodes holds its drawing with `defer()` (`module-state.md`); other widgets go on
drawing new state. The image that follows the
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
