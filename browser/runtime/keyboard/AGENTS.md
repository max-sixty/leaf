# Keyboard runtime

This file holds the keyboard policy the modules here share; each module's header owns
its own contract, `bindings.js` the fields of a command row and `dispatch.js` which
scope answers a press.

## Ownership

A command is one capability, owned by the layer that implements its result. A binding
is a key that invokes it, and a scope says where the binding applies. Dispatch, the
floating panel's menu rows, the command reference, tooltips, announcements and
`aria-keyshortcuts` all read one register, so register a capability once and derive every presentation from
its row. A visible control names an existing command rather than copying its callback.

Core owns commands on the page, the chrome, navigation, comments and shared thread
state. A widget owns commands that read or change its content, and its scopes join the
register only while the widget exists. A package widget declares an element scope as
data, the element's `lfCommands`, which `scopes.js` reads when the widget calls
`commandsChanged`; core declares one with `keys(element, …)`, and both take a
`commandScope(…)` value, as a template's `commandsOn(…)` does. Core scopes over the
page use `pageScope`, `pageCommand` and `pageRung` in
`register.js`. A new scope, page command or Escape step also needs its place in
`register.js`'s `STACK`, `PAGE_COMMANDS` or `RUNG_LADDER`.

## Scope resolution

A press goes to scopes from the focused element outward, ending at the page and then
the browser. A scope owns every binding it declares while the user is in it, so when its
command is unavailable the press reaches no other Leaf command. A text field keeps
characters, composition, caret movement and deletion, and a native control keeps its
activation press, ahead of any widget or page scope around it (`dispatch.js`). A key
other than typing or Escape, pressed while the user has scrolled the focused control
out of sight, lets go of it first, without closing what stands beside it, and then
acts from what they see, so no Leaf command, listener on the control or browser
default acts on what they can't see (`controller.js`). A key
typed into one of Leaf's fields, a `leaf-text` or a search box, stops at the field once
the field and the dispatcher have read it there (`field-keys.js`), so the page never
hears it bubble, and any other Leaf listener that needs keys typed into a field listens
in capture. Leaf reads printed letters before the page's listeners, and other keys when
they reach its listener on `document`. A key aimed inside `body` whose default is
already prevented by then is the page's, and Leaf takes no step for it
(`controller.js`).

## Escape

Escape closes one step of the current interaction and lands the user on that step's
parent. Both depend only on what is open now, so a surface opened by pointer or Tab
closes the same way as one opened by its key. The focused control's own step comes
first, then steps inside the focused surface, then the surface itself, then steps
outside it; `STACK` and `RUNG_LADDER` order siblings, and native modals and popovers
keep the browser's order. A close request, such as Android's back gesture, takes the
same step, through its row's `keep` where `run` would throw away unsent words
(`close-requests.js`).

- The document is the base. In a live sample, one more Escape returns focus to the
  containing page.
- A preview standing over the page is the first step, by pointer or by focus: Escape
  puts it away and does nothing else, and the next Escape takes the step it stood in
  front of (`preview.js`). Any other key puts a pointer's preview away and does its own
  work. A focus preview stands only where focus was moved by Tab or a placement
  standing in for one (`step`), the cause its mover gives `focusDestination`, so a
  command's landing, as a walk's (`move`), focus a surface places as it opens, and
  focus handed back as it closes or as Escape backs the user out (`return`), costs no
  Escape, and one put away stays away until the user aims again, whatever a widget
  declares meanwhile.
- Draw and Design are page modes; surfaces opened inside them close first.
- A surface's own state, such as Threads' search, clears before the surface closes.
  Page-side selections, targets, margin clusters and the page composer coexist beside a view the
  floating panel opens, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, a find box to its panel. A layer
  opened from the floating panel's menu returns to the panel.
- After Send, a reply box keeps the caret for the next message, in a card, a seat and
  the panel's field alike (`thread/replies.js`), and so does a box that stays open for
  more messages such as a widget's thread box (`x-thread-seat`). A thread's first
  comment leaves focus on the thread's card or title, never on the page.
- A selected destination (a thread, an obligation, a heading) steps back to the document
  through `letGo` (`focus.js`), landing beside it while it is in view, else on the
  visible block, rather than on the control that opened it, so Tab carries on from it.
  Page Map returns focus to whatever opened it. Leaving a walk's stop leaves the user
  at it rather than on it, so the walk's next press returns there
  (`current-target.js`).

Go-to, target hints, page search, reactions and the command reference own the keyboard
while active and handle their own exit. Escape closes a surface even if it was open
before the interaction began, and closing one with the pointer focuses the control that
reopens it.

## Page grammar

Page scope holds commands about the page; a surface's scope holds commands about its
contents. A page-level letter must be useful on every page; any other control is
reachable by Tab, native activation, obligation digits or Go-to hints. A lowercase
letter steps a walk forward and Shift steps it back, wrapping at either end. A page
walk with nothing to step through says so in the panel (`notice`, such as “No open
threads”) rather than doing nothing, so its letter is live on every page. A walk over
a list the server's reading brings says instead that the list can't be had while the
server is offline. A walk, a
scroll, Go-to and any other command that takes the user somewhere declares `travels`
on its row; every other command leaves the control it was pressed on where it stood on
screen (`bindings.js`). A surface
may reuse a page key for the same intent with a nearer destination. While the user is
on an obligation, or its margin or thread representative, core forwards only the
widget's declared `contextKeys`, and widgets assign their own `1`–`9`.

## Touch routes

Every page capability available through a key but not a direct gesture has a row among
the page's controls (`page-controls.js`). It supports both touch and mouse input and
comes from the same command row as the key (`touch-controls.js`). Actions within a
scope have controls beside the content they act on: a search box has arrows to move
between matches, a drawing's composer can undo a stroke, and the page's field can
comment on selected words. Page scope rows therefore have no touch labels: each row
that runs a press declares `touch: false` or is the `exit` of a stance accessible by
touch. Examples include page search, the target picker and Draw mode. The panel
offers the innermost active stance's exit as Close at its field's end, or one ✕ while
the field says something else. Either leaves the stance even where Escape would first
close something inside it or take back a typed hint letter. The register
refuses a page command without `touch` and a scope row whose `run` is neither `exit`
nor `touch: false`.
`false` means the result is directly accessible by scrolling and tapping or through
the row's own control beside the content it changes.

Words owe a finger the same reach. A `title` shows only to a pointer resting on its
element, so it can't be the only place a state's reason or the rest of a cut word is
said. A state says its word on the surface that holds it (`quoteReading`), a panel
row's cut words stand whole where no pointer can hover (`floating-panel.css`), and
whatever previews, a control's word and keys among it, shows its preview to a finger
holding it. The hold reads and its release presses nothing, while a tap still presses;
until 5 November 2026 the release pressed, so a finger couldn't read without acting
short of sliding off, which on touch often scrolls instead (`preview.js`).

The comment field has one primary action, Send. Suggest and reactions share an anchored
Other responses picker, reached by the ⋯ beside Send while the field is empty, Tab from the field outside a list item
(in one, Tab nests the item, `nestItems` in `composing/field-editor.js`), or the
contextual reaction command. Opening the picker
keeps the field in place on desktop and touch surfaces alike.

A command that should leave the user where they are declares `retainCurrentLocation`: the
row's press restores the focus, caret and selection the floating panel saved as the
user stepped into it, then runs the command.

## Testing a binding

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
