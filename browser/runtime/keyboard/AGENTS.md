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
activation press, ahead of any widget or page scope around it (`dispatch.js`).

## Escape

Escape closes one step of the current interaction and lands the user on that step's
parent. Both depend only on what is open now, so a surface opened by pointer or Tab
closes the same way as one opened by its key. A step that only moves focus is open
only while the focus ring shows it, as painted before the press (`shownFocus`,
`focus.js`): a click leaves focus in a thread card without its ring, so Escape there
closes the card, where after `t` it first steps out onto the passage. The focused
control's own step comes first, then steps inside the focused surface, then the
surface itself, then steps outside it; `STACK` and `RUNG_LADDER` order siblings, and
native modals and popovers keep the browser's order. A close request, such as
Android's back gesture, takes the same step, through its row's `keep` where `run`
would throw away unsent words (`close-requests.js`).

- The document is the base. In a live sample, one more Escape returns focus to the
  containing page.
- Draw and Design are page modes; surfaces opened inside them close first.
- A surface's own state, such as Threads' search, clears before the surface closes.
  Page-side selections, targets, margin clusters and the page composer coexist beside a view the
  floating panel opens, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, a find box to its panel. A layer
  opened from the floating panel's menu returns to the panel.
- After Send, a reply or a thread's first comment leaves focus on the thread's card or
  title, never on the page. The panel's field, and a box that stays open for more
  messages such as a widget's thread box (`x-thread-seat`), keep focus.
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
letter steps a walk forward and Shift steps it back, wrapping at either end. A walk, a
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
touch. Examples include page search, the target picker, Draw mode and the user's
current to-do, whose exit is Done. The panel shows the innermost active stance's exit
as one ✕, or the symbol of the action the row names (the to-do's check). It leaves the stance even
where Escape would first close something inside it. The picker's ✕ is the exception:
while typed hint letters remain, it removes one (`target-picker.js`). The register
refuses a page command without `touch` and a scope row whose `run` is neither `exit`
nor `touch: false`.
`false` means the result is directly accessible by scrolling and tapping or through
the row's own control beside the content it changes.

The comment field has one primary action, Dictate while empty and Send once it has
words. Suggest and reactions share an anchored Other responses picker, reached by the
⋯ beside Dictate while the field is empty, Tab from the field, or the contextual
reaction command. Opening the picker
keeps the field in place on desktop and touch surfaces alike.

A command that should leave the user where they are declares `retainCurrentLocation`: the
row's press restores the focus, caret and selection the floating panel saved as the
user stepped into it, then runs the command.

## Testing a binding

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
