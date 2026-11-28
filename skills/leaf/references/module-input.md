# Commands, focus, and text entry

Read with [module-authoring.md](module-authoring.md).

## Commands and keyboard routes

A widget declares its commands as data on the element they apply in: the element's
`lfCommands` is the scope, which a component states with `declare` from a Mount
(`module-widgets.md`, "`lf-commands`"), and other code sets before it dispatches an
`lf-commands` event on the element. The scope holds `title`,
the heading the command reference lists it under, and `rows` ("Command rows"). It may
also hold `when`, whether the page has the scope at all, which gates the reference as a
row's own `when` gates its press; `ready` (`module-authoring.md`, "Startup and
presentation"); and `escape: "inner"`, for a scope whose own Escape step comes before
every step outside it.

Leaf reads the declaration when it hears the event, binds its keys, lists them in
the command reference and hints, and writes their `aria-keyshortcuts`. A page
without Leaf reads nothing, so a widget that also runs there (`module-authoring.md`, "A
widget that also runs off Leaf") binds no key. Declare as the view first draws.

Declaring a new object, or assigning one to `lfCommands` and dispatching the event,
replaces the scope, and Leaf checks the new rows then, reporting a malformed one as the
element's failure. `null` withdraws the scope. Leaf checks an object once, the first
time it is given. Saying the event with that object again, standing or given back after
`null`, only has Leaf read its rows' titles and availability again, so a row or title
edited in place goes unchecked; give a new object to change them.

```javascript
declare(node, {
  lfCommands: {
    title: "On a code block",
    rows: [{ id: "code.wrap", keys: ["w"], title: "wrap lines", run: toggleWrap }],
  },
});
```

One object is one scope wherever it is given. Where the same commands apply in several
elements, such as a widget and the editor it opens, set the one object as the
`lfCommands` of each and dispatch the event on each, and Leaf lists and runs the
commands once. For a control Leaf draws, such as a margin entry, put the same object on
the entry's `scope` (`module-annotations.md`, "Margin contributions"):

```javascript
const actions = {
  title: "In a classifier",
  rows: [
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
  ],
};
classifier.lfCommands = actions;
classifier.dispatchEvent(
  new CustomEvent("lf-commands", { bubbles: true, composed: true }),
);
```

A node a component's view draws takes a scope of its own from a Mount on that node,
which sets the node's `lfCommands` and says `lf-commands` on it as the Mount starts and
on each change of what the rows read (the Mount's `changes`).

### Command rows

A row's `id` is a stable, lowercase dotted name such as `draft.save`; keep it when keys
or words change. `title` names the command and may be a function where state changes
it, and `label` replaces the keycap. `description` is the command reference's tooltip
for it and the line under its title where a touch menu or an On Me card offers it. A
`decision: true` row answers an obligation, `recommended: true` marks the answer
the page advises, which an On Me card names, and `commits: true` marks the press that
commits an answer the user composed, such as an `lf-options`' Done, which an On Me
card draws as that commit rather than as one more answer.

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
where a press takes the user, such as a step list's arrow to the new step's row, after
Leaf runs the row for a key, a command-reference pick or a click on its `control`: Leaf
calls it right after the run, so it reads the state the
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

Leaf re-evaluates a `when` or a computed field when the page readings it uses change,
such as the threads. For any other state a row reads, such as the widget's `state`,
the widget says `lf-commands` again after the change (`module-widgets.md`,
"`lf-commands`").

### How scopes compose

A key reaches listeners on the focused element and around it before Leaf's scopes: the
focused control's, the widgets' around it, then the page's. A listener keeps a key,
even a page key, by preventing its default. Listeners on the document and the window
hear only keys Leaf leaves, and Escape lets go of a focused control after them unless
one prevented it. Leaf hears first only while Go-to or reactions are armed, with
nothing focused, and while focus is scrolled out of sight, where a key other than
typing or Escape lets go of it.

Among scopes, a key pressed inside an outlet Leaf fills with a Thread
(`module-annotations.md`, "Widget-local Thread placement" and "Page annotation
presentation") skips the widgets around the outlet: it goes to the scopes inside the
outlet and on it, then to the page. A scope takes only keys whose rows make a press, by
a `run` or by naming a `control` Leaf clicks, so other keys pass outward. A row keeps
its key while unavailable, so the key never falls through to a different meaning further
out; an unavailable Escape, though, passes on to the next Escape. Text fields keep their
editing keys ahead of every widget scope.

Leaf holds some keys for a widget's own layer with nothing declared. While focus is in
a menu, or another widget whose ARIA pattern types ahead (`page-behavior.md` names the
roles), letters and digits reach no scope around it. Escape pressed in an open popover
goes no further than the popover. In a modal dialog no key but the command reference's
reaches the page.

Give a native button's row both `control` and `run`, and Leaf runs `run` for its click
and its key alike. Don't add a click listener, and don't call the button's own `click()`
from `run`. Put every condition in `when`: Leaf shows the button disabled with
`aria-disabled` and refuses the press while keeping focus there. Native inputs keep
their own activation and editing.

A disclosure needs no row. On every `details > summary` and every button with
`aria-expanded` on the page, a widget's included, Leaf answers Enter, Space and the
arrow that opens or closes it, and lists the press in the command reference as open or
close. In a thread's message only Enter and Space work one. The library's
[`keys.js`](../../../browser/runtime/lib/keys.js) names the keys that press a button and
the arrows along a row in its text direction. Leaf spells and says keys itself: a
preview takes each press it adds as bindings (`module-previews.md`), and an
announcement takes the rows whose keys it names (`module-scroll-and-motion.md`,
"Notices and spoken words").

A flex or grid summary draws no native marker. Give it, or an `aria-expanded` button,
the `lf-disclosure-marker` class, and it shows the arrow Leaf's own disclosures show, as
its `::before`, turning with its state; the widget's own rules place it.

### Decisions and forwarded keys

`keys` work inside the widget. `contextKeys` work there too, and Leaf also forwards them
from its margin controls and threads. Number
a widget's choices by the choice, not by what is available: a classifier declares Pass
as `1` and Keep as `2`, and disabling `1` must not turn `2` into something else. The
page keeps `m` and `Shift+m` for moving through On Me.

`decision: true`, which needs a `control`, marks a command that starts, advances,
answers or revises the obligation holding it; it forwards no keys by itself. A forwarded
key runs the original row, if available, so register each command once, not on every
nearby button.

### Inline shortcut hints

To show a command's key on the page, set `bindingBadge` on its row or route: an empty
element the widget positions over its control, or beside it over a box that holds the
element, or `null` for a badge at the control's corner. Where anything else stands at the
element's place, the key shows as a chip there instead. Leaf gives the element the class
`lf-binding-seat`, which positions it
absolutely and has it take no pointer, so a press where it stands lands on what is under
it. Leaf writes the key into it while the key works, and the widget gives it the class
`lf-key-badge`, a key's face (`module-controls.md`, "Faces for a widget's parts"). `leaf package check
--render` reports a command with `contextKeys` and no badge (`shows-context-keys`,
[packages.md, "Seeing it"](packages.md#seeing-it)).

### Walks

A list of focusable rows gets its arrow keys from `rowWalk({id, noun, plural, rows})`,
whose two returned rows go into the list's scope: ArrowUp and ArrowDown step, Home and
End reach the ends, and a step shows its position in Leaf's panel, such as `Entry 3 of
7`, where the list runs past the window. `rows()` returns the list at each press, `landed(row)`
runs after a move, and `scroll: false` keeps the page still. `position: () => null`
shows no position, for a list whose rows name their places to a screen reader
themselves, as a menu's do, and `steps` names the four steps in place of
`["previous", "next", "first", "last"]`.

A row whose press carries the user along a list of its own declares `lands(from)`
("Command rows") rather than moving focus in its `run`.

A widget that steps through something itself, such as a diff's hunks, says where each
step landed with an `lf-walk` event on the stop. The step's `run`
dispatches it, before or after focus moves to the stop:

```javascript
hunk.dispatchEvent(
  new CustomEvent("lf-walk", {
    bubbles: true,
    composed: true,
    detail: { noun: "Hunk", position: 3, total: 7, list: [firstHunk, lastHunk] },
  }),
);
```

`noun` names one stop, and `position` counts from 1. Leaf's panel says the place,
`Hunk 3 of 7`, for a few seconds after the step. `list` gives the elements of the
list's first and last stops. At a step taken while both stand in view the panel says
nothing, since the focus ring shows where the step landed among stops the user sees;
without `list` it says every step. The place goes sooner if focus leaves the stop, once
the stop or something inside it has held focus. It also goes if the element it was said
on leaves the page, as when a redraw replaces it, so a widget whose stops are not
elements of their own dispatches on the part of its drawing that holds the stop. Leaf
hears an element leave the page or a shadow stage it builds (`shadowStage`), not a
shadow root the widget attaches itself, where the place stays its few seconds. A widget
whose stops take no focus, as a chart's points take none, tells Leaf when its user
leaves a stop without stepping, as when the chart's pointer takes its reader to another
point. It dispatches `lf-walk` with no `detail` on the element the place was said on,
and the place goes at once. The panel shows the
place and says nothing aloud: the widget announces it, with what else a listener
should hear of the stop (`module-scroll-and-motion.md`, "Notices and spoken words").
Off Leaf, nothing hears the event.

### Go-to targets

Every visible button, checkbox, radio or selectable control a widget builds with the
library's control constructors (`module-controls.md`) is a target the `g` key reaches,
with nothing more to declare.

## Focus and layers

Move focus with `focusDestination(element, cause)`. The cause tells Leaf why focus
moved:

- `"move"`: a route taking the user somewhere, such as to the next row, whose landing
  previews nothing (`module-previews.md`);
- `"return"`: putting them back, as a widget's Escape does, or a redraw handing them to
  the control that replaced theirs;
- `"step"`: the widget's own Tab loop, whose landing previews as Tab's does;
- `"press"`: landing on a control to press it for them.

A return marked as a move looks like the user arriving, and can release held news or
open options they never went to. An element that isn't a control gets a Tab stop while
it has focus. `{caret: [start, end, direction]}` places a text field's caret. Moving
focus never scrolls; reveal the destination with `scrollIntoView`
(`module-scroll-and-motion.md`, "Scrolling to a destination").

A component's view keeps the user's place by itself where a draw keeps their node:
Effect UI patches that node, so focus, a field's typed words and its caret stay, and a
keyed node moved among its parent's children keeps them too, though a contenteditable's
selection collapses. A keyed node moved to another parent is a new node there, unless
the view writes it as a keep-alive child (`h.keepAlive`, which takes a keyed child
component), whose nodes move with it and keep their words. Around each draw a set of
`state`, an input or a member starts, the element `defineWidget` defines holds the
user's place by the `data-lf-datum` key of the datum they are in (`module-state.md`,
"Marking drawn data"), and puts them back only where the draw lost their focus: where
they last stood, if that is drawn again; else on their own node where it survived the
draw; else on the widget's datum now carrying that key, else on the nearest one still
drawn, on the datum itself rather than a control in it; and last, as where a removal
empties the list, on the widget's own element. After a draw the component's own
messages start, which has no such hold, a user whose node it removed or moved to
another parent lands on the body.

Before code outside a view hides or replaces nodes the user may be in, as a Mount's own
redraw that rebuilds or deletes a row does, call `const restore = holdFocus(scope)`, and
call `restore?.(...standIns)` after; `holdFocus` returns `null` when the user is outside
`scope`. Moving nodes needs no hold (`module-authoring.md`, "Retained nodes"). Unless
the user has gone elsewhere since, `restore` puts them back on the same node, or else on
the first stand-in that can take focus. For a keyed list, `holdFocus(list, { key })`
names the attribute holding each item's key. `restore` then tries the same item, then
the nearest item that survived, and lands on the control there like the one the user was
on, such as its Remove. It tries the stand-ins last, so a Remove that empties the list
can hand the user to the list's Add button. A command row whose `run` redraws the user's
own place holds focus this way, and leaves `lands` to a press that takes the user
somewhere else.

A live revision moves focus from a generated control to its replacement by a
`data-lf-carry` key, unique within the control's nearest authored ancestor with an id.
For a control in a widget's shadow root, that ancestor is the widget.

Ask the browser what is focused: the `activeElement` of the tree a node stands in,
`document`, the widget's own `shadowRoot`, or `element.getRootNode()` for a widget that
may stand inside another's shadow tree. A shadow host stands for focus inside its tree.
It keeps naming the element while the window is in the background, as when a revision
arrives, where `:focus` and `:focus-within` stop matching. A command row may read it:
Leaf reads a scope's rows again whenever focus moves into, out of or within the scope.

`placeOf(node)` returns the page node a place stands for,
so focus on a margin entry or in a thread card reads as being at its passage or
obligation; a module asks it whether the user is on its content from either.
`onPressAway(away, dismiss)` hears each primary press that begins and
ends where `away(path)` is true of its composed path, as an open editor that a tap
elsewhere should save does, and calls `dismiss(path, from)` before the press's click; it
ignores a touch scroll the browser cancels, and returns its unsubscribe function. A set
of controls the user moves through with arrow keys offers one Tab stop, which the
library's [`roving.js`](../../../browser/runtime/lib/roving.js) sets.

`onPress(begin)` follows the primary pointer's press through its native compatibility
events. `begin(pointerdown, path)`, a passive listener, may return
`end(event, completed)`: release calls it with `completed: true`; cancellation, a
native context menu, or leaving the document calls it with `false`. The function `end`
returns runs when that press is over, after any compatibility mouseup and click it
owes. Register inside `whileConnected`; the returned unsubscribe stops new presses, and
the connection's abort signal ends work still running when the widget disconnects.

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

Leaf rings the obligation the user is in, and draws no ring round it while visible
focus is inside it, so a widget's own focus ring is the one that shows.

### Layers

A widget's own layer, such as a list over its contents, is a native popover or dialog,
opened and closed with the browser's own methods (`showPopover`, `hidePopover`,
`showModal`, `close`) or with `popovertarget` in markup. Closing a dialog, or an auto
popover (`popover="auto"`) opened while no other was showing, returns the user to where
they stood as it opened, but only while focus is inside it, and a pointer press in
Safari or Firefox on macOS leaves the button it pressed unfocused. So a widget that
closes its own layer from a choice in it, or closes any other popover, puts the user
back on its opener with `focusDestination(opener, "return")`. A manual popover's Escape
is an ordinary command row.

A control that opens a popover, such as a menu of choices, names it with
`popovertarget`, or passes itself as the popover's source, `showPopover({source})`.
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

### Pointer presses

A handler that takes over a click, such as a link that opens a source line, acts only on
the primary button with no modifier held, so a modified click keeps its usual meaning.

A container that takes a click anywhere on it, as an option card does, asks
`aimedAt(event, container)` what the click was for. The answer is the container itself;
or what the click landed on that has a use of its own, such as a control or a widget
inside the container or a link around it; or null where the click belongs to a
selection of the container's words, one a drag across them ends or one the press
landed in. The container acts where the answer is itself or a control its own module
put inside it, such as an option's pick mark, and leaves the click to anything else
the answer names. A click made with Enter or Space never belongs to a selection.

A click on words a thread marks opens that thread, unless the click landed on a control
or a handler took it. So a handler that acts on a click on anything but a control, such
as a card, a mark or a phrase, calls `event.preventDefault()`.

While the user drags, grabs or scrubs something in the widget, say so with an
`lf-hold` event (`module-widgets.md`, "`lf-hold`"). A component draws the gesture's
progress from its Model rather than moving its own nodes (`module-widgets.md`,
"`lf-defer`").

A surface that must stop moving before Leaf handles a gesture, such as a playing
animation, subscribes with `onUserInput(callback)`, which runs before Leaf handles each
press, key, input, wheel or touch on the page, or the window losing focus. Act only on
events whose target is in the surface; the callback doesn't consume the event. Call the
returned function when the surface disconnects.

Before a drawing stroke reads its coordinates, Leaf dispatches `lf-inspect` on the
element drawn on; a moving visual listens for it and freezes what it shows.

## Text entry and drafts

A widget's own text box is Leaf's Markdown editor, which behaves like a textarea and
fires `input` only for the user's edits. Build it as a generated control
(`module-controls.md`) whose tag is `leaf-text`. The field matches `:state(ready)` once
it draws its words; where it replaces text the user was reading, leave that text in
place until then, so the scroller doesn't shrink. Under a finger Leaf sets a field's
type no smaller than `--lf-entry-floor`, so a widget that shows words and then opens a
field on them sets those words' `font-size` to `max(var(--lf-entry-floor), 1em)`, and
the two sizes agree.

Wire the box with `wireInput(box, options)`. Enter sends on a physical keyboard,
Shift+Enter writes a newline, and Mod+Enter sends anywhere; on a touch screen the
visible control sends. A box for one line, such as a name, carries the boolean
attribute `one-line` before it is wired: Enter then sends from every keyboard, a
phone's included, Shift+Enter writes nothing, and a pasted line break becomes a space.
The options are `sendClass`, placement classes for the generated send control (default
empty); `sends`, its action in words; `hint`, the placeholder, after which a focused box on a physical keyboard names its send key and, where Enter sends a box that holds lines, the key for a new line; `save(value)`, called with the whole draft on each
edit; `send(text, raw, owns)`, called on send with the trimmed and raw draft; `busy()`
and `hasContent(raw)`, which hold sending back. Write `.value` only to seed the box
before wiring it.

`wireInput` returns `sync`, which reads or sets the whole draft, a pasted image
included: `sync.value()` reads it, `sync.load(value)` replaces it, and `sync()` repaints
after the box's state changes. `sync.button` is the generated send control.

`wireInput` stands the box in a frame, `.lf-compose-field`, with its send control and,
while a send is refused, the reason, `.lf-compose-error`. The box's hint is
`.lf-compose-placeholder`. A widget that seats the box in a row of its own places
those parts from its sheet, and sets the frame's padding on `.lf-compose-field` as
`--lf-compose-pad-block` and `--lf-compose-pad-inline-start`. Leaf sets
`--lf-field-end-room` on the box, the room its words leave at their end for the send
control, and a widget that moves the control sets it again.

Drafts survive a reload, a new version and a closed tab, and every tab and device
showing the page shares them, since the page's server keeps them. `draft(ctx)` returns
the draft kept under `ctx`, a string unique on the page such as `option:` and its id:

- `read()` returns the stored draft record, or `null`. Seed the box with
  `read()?.text ?? ""`; its `payload` holds the saved send data.
- `save(text, payload)` records an edit, from `wireInput`'s `save`, with any `payload`
  the send needs.
- `watch(callback, {input: box})` calls `callback(text, payload)` when the draft
  changes other than by typing in this box: another tab or device, a send emptying it,
  or a refusal returning the words. Put them in the box with `sync.load(text ?? "")`,
  and register the watch in `whileConnected`.
- `send(owns, deliver)`, called from `wireInput`'s `send`, calls
  `deliver(attempt, payload)` if the box still shows the stored draft and `owns()` is
  true, and resolves to what `deliver` returns. One `attempt` stands for one version of
  the words, so a resend after a reload reuses it.
- `clear()` drops the draft, as a box closed with nothing changed does.
- `discard()` drops the draft as Discard and Escape do: ⌘Z, the press of the notice
  "Edit discarded", puts its words back in the draft and opens the box on them through
  `watch`'s `resume`. Call it only where the box's words differ from what its subject
  already says.

`lf-options`' box for adding an option (`lf-options-addition.js`) is the worked example.

For a CodeMirror editor, construct the class `leafEditorView(codemirror)` returns in
place of `EditorView`, so focus and reveals go through Leaf. Pass the namespace of the
CodeMirror 6 bundle your package ships (`import * as codemirror from
"/vendor/<bundle>.js"`), which exports `Compartment`, `Direction`, `EditorState`,
`EditorView` and `StateEffect`.
