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
register only while the widget exists. Element scopes are declared with
`keys(element, …)`, a template's `commandsOn(…)` or `commandScope(…)` in
`scopes.js`, and core scopes with `pageScope`, `pageCommand` and `pageRung` in
`register.js`. A new scope, page command or Escape step also needs its place in
`register.js`'s `STACK`, `PAGE_COMMANDS` or `RUNG_LADDER`.

## Scope resolution

A press goes to scopes from the focused element outward, ending at the page and then
the browser. A scope owns every binding it declares while the user is in it, so when its
command is unavailable the press reaches no other Leaf command. A text field keeps
characters, composition, caret movement and deletion, and a native control keeps its
activation press, ahead of any widget or page scope around it (`dispatch.js`).

## Escape

Escape closes one step of the current interaction and lands the user on that step's
parent. Both depend only on what is open now, so a surface opened by pointer or Tab
closes the same way as one opened by its key. The focused control's own step comes
first, then steps inside the focused surface, then the surface itself, then steps
outside it; `STACK` and `RUNG_LADDER` order siblings, and native modals and popovers
keep the browser's order.

- The document is the base. In a live sample, one more Escape returns focus to the
  containing page.
- Draw and Design are page modes; surfaces opened inside them close first.
- A surface's own state, such as a Threads filter, clears before the surface closes.
  Page-side selections, targets, margin clusters and the page composer coexist beside a view the
  floating panel opens, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, a find box to its panel. A layer
  opened from the floating panel's menu returns to the panel.
- After Send, a reply or a thread's first comment leaves focus on the thread's card or
  title, never on the page. The panel's field, and a box that stays open for more
  messages such as a widget's thread box (`x-thread-seat`), keep focus.
- A selected destination (a thread, an obligation, a heading) steps back to the document
  through `letGo` (`focus.js`), landing on the visible block rather than on the control
  that opened it. Page Map returns focus to whatever opened it.

Go-to, target hints, page search, reactions and the command reference own the keyboard
while active and handle their own exit. Escape closes a surface even if it was open
before the interaction began, and closing one with the pointer focuses the control that
reopens it.

## Page grammar

Page scope holds commands about the page; a surface's scope holds commands about its
contents. A page-level letter must be useful on every page; any other control is
reachable by Tab, native activation, obligation digits or Go-to hints. A lowercase
letter steps a walk forward and Shift steps it back, wrapping at either end. A walk, a
scroll, Go-to and any other command that takes the user somewhere declares `travels`
on its row; every other command leaves the control it was pressed on where it stood on
screen (`bindings.js`). A surface
may reuse a page key for the same intent with a nearer destination. While the user is
on an obligation, or its margin or thread representative, core forwards only the
widget's declared `contextKeys`, and widgets assign their own `1`–`9`.

## Touch routes

Every page capability that a key reaches and no direct gesture does has a row among the
page's controls (`page-controls.js`), which serves a finger and a mouse alike and is
built from the same row the key uses (`touch-controls.js`). What a gesture does next, a
finger does on what the gesture acts on: a search's arrows walk its matches from its
box, a drawing's composer undoes its stroke, and the page's field comments on selected
words. So a page scope's rows take no words: each that runs a press says
`touch: false` or is the `exit` of a stance a finger can enter, such as page search,
the target picker or Draw mode, or a to-do on the user that they stand on, whose exit is
its Done. While that stance is the innermost one standing, the panel offers its exit as
one ✕, or the icon the row names (the to-do's check), which leaves the stance even
where Escape would first close something inside it. The picker's ✕ is the exception: while typed hint letters
stand, it takes back one (`target-picker.js`). The register refuses a page command
without `touch` and a scope row whose `run` is neither `exit` nor `touch: false`.
`false` says a finger reaches the result directly, by scrolling and tapping or through
a control of the row's own beside what it changes.

The comment field has one primary action, Dictate while empty and Send once it has
words. Suggest and reactions share an anchored Other responses picker, reached by its
button, Tab from the field, or the contextual reaction command. Opening the picker
keeps the field in place on desktop and touch surfaces alike.

A command that should leave the user where they are declares `retainCurrentLocation`: the
row's press restores the focus, caret and selection the floating panel saved as the
user stepped into it, then runs the command.

## Testing a binding

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
