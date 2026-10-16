# Keyboard runtime

This file holds the rules the modules here share; each module's header owns its own.

## Ownership

A command is one capability, owned by the layer that implements its result. A binding
is a key that invokes it, and a scope says where the binding applies. Dispatch, the
shortcut bar, the command reference, tooltips, announcements and `aria-keyshortcuts`
all read one register, so register a capability once and derive every presentation from
its row. A visible control names an existing command rather than copying its callback.

Core owns commands on the page, the chrome, navigation, comments and shared thread
state. A widget owns commands that read or change its content, and its scopes join the
register only while the widget exists. Element scopes are declared with
`keys(element, …)`, a template's `commandsOn(…)`, or `commandScope(…)` in
`scopes.js`; core scopes with `pageScope`, `pageCommand` and `pageRung` in
`register.js`. A new scope, page command or Escape step also needs its place in
`register.js`'s `STACK`, `PAGE_COMMANDS` or `RUNG_LADDER`.

## Scope resolution

A key press goes to scopes from the focused element outward: the exact control or an
active mode, native editing and activation, the nearest widget and the widgets around
it, Leaf's contextual and page scopes, and last the browser. A scope owns every binding
it declares while the user is in it and the page has it (`standing` in `dispatch.js`),
so when its command is unavailable the press reaches no other Leaf command.

A text field keeps characters, composition, caret movement and deletion ahead of any
widget around it, though the field's own scope may still bind Enter or Escape. A native
control keeps its activation press, such as Enter on a link: no widget or page scope
around it runs another command on that press, though a mode that owns the keyboard
still does.

## Escape

Escape closes one step of the current interaction and lands the user on that step's
parent. Both depend only on what is open now, never on how the user got there, so a
surface opened by pointer or Tab closes the same way as one opened by its key. The
focused control's own step comes first, then steps inside the focused surface, then the
surface itself, then steps outside it; `STACK` and `RUNG_LADDER` order siblings, and
native modals and popovers keep the browser's order. `register.js` exposes the
innermost step as one `navigation.back` command.

- The document is the base. In a live sample, one more Escape returns focus to the
  containing page.
- Draw and Design are page modes; surfaces opened inside them close first.
- A surface's own state, such as a Threads filter, clears before the surface closes.
  Page-side selections, targets, clusters and the page composer coexist beside an
  auxiliary surface, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, and a find box to its panel.
  A layer opened from a banner control returns to that control.
- After Send, a reply or a thread's first comment leaves focus on the thread's card or
  title, never on the page. The page comment card closes after Send and returns focus
  to its banner control. A box that stays open for more messages, such as a widget's
  thread box (`x-thread-seat`), keeps focus in the box.
- **Threads.** The Threads panel has one thread selected whenever it shows any, and
  focus on the list goes to that thread's title: `g T` and Escape from the panel's find
  box both land there. Moving onto a title by any route selects its thread, so the
  focused thread is the open one and `c` replies to it. When the runtime returns focus
  to a title, it selects nothing: it goes back to the title the user chose, or to the
  open thread's title if a change removed theirs. A `holdFocus` restore that runs after
  the selection moved is the one case that leaves focus on a closed title
  (`thread/thread-list-view.js`).
- A selected destination (a thread, an ask, a heading) steps back to the document
  through `letGo` (`focus.js`), landing on the visible block rather than on the control
  that opened it. Page Map returns focus to whatever opened it.

Go-to, target hints, page search, reactions and the command reference own the keyboard
while active and handle their own exit. Escape closes a surface even if it was open
before the interaction began, and closing one with the pointer focuses the control that
reopens it.

## Page grammar

Page scope holds commands about the page; a surface's scope holds commands about its
contents. A page-level letter must be useful on every page; any other control is
reachable by Tab, native activation, ask digits or Go-to hints. `PAGE_COMMANDS` lists
the page commands in shortcut-bar order. A lowercase letter steps a walk forward and
Shift steps it back, wrapping at either end. A surface may reuse a page key for the same
intent with a nearer destination. While the user is on an ask, or its margin or thread
representative, core forwards only the widget's declared `contextKeys`; widgets assign their own `1`–`9`.

## Touch routes

Every page capability that a key reaches and no direct gesture does has a banner
control, for a finger and a mouse alike. The row names that control in `touch`, and
`touch-controls.js` builds it from the same row the key uses: a page command's control
is an entry in More, and a page-scope row's control appears on the banner's row while
its scope is the innermost one offering steps. A mode a finger can enter declares its
way out. The register refuses a page command without `touch`; `false` says a finger
reaches the result directly, as it does for walks and Go-to by scrolling and tapping.

The comment field has one primary action, Dictate while empty and Send once it has
words; Suggest and reactions open by Tab from the field. The field deliberately has no
ellipsis menu, on phones too; change that only with the user, through a rendered design
comparison.

A command that should leave the user where they are declares `retainStanding`: More
saves focus, caret and selection before taking focus, and its control restores them
before running the row.

## Modules

`bindings.js` (key spelling and declaration checks), `scopes.js` (element scopes),
`register.js` (scope order, page commands, the Escape ladder), `dispatch.js`
(precedence), `controller.js` (input lifecycle), `text-entry.js` (native editing and
activation), `layer-stack.js` (popovers and dialogs over the page), `page.js` (the
page's own scope and the last Escape step), `go-to-sequence.js` (the `g` keys),
`hints.js` and `command-hints.js` (hint chips), `chip-seats.js` and
`key-badge-placement.js` (where chips sit), `touch-controls.js` (a finger's controls
for the keys), and `control-keys.js`, `key-sequence.js`, `shortcut-bar.js`,
`command-reference.js`, `disclosure.js`.

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
