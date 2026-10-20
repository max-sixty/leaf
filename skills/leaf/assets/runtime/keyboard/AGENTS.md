# Keyboard runtime

This file holds the rules the modules here share; each module's header owns its own.

## Ownership

A command is one capability, owned by the layer that implements its result. A binding
is a key that invokes it, and a scope says where the binding applies. Dispatch, the
floating panel's menu rows, the command reference, tooltips, announcements and
`aria-keyshortcuts` all read one register, so register a capability once and derive every presentation from
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
  Page-side selections, targets, clusters and the page composer coexist beside a view
  the floating panel opens, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, and a find box to its panel.
  A layer opened from the floating panel's menu returns to the panel.
- After Send, a reply or a thread's first comment leaves focus on the thread's card or
  title, never on the page. The panel's field keeps focus after Send for the next turn.
  A box that stays open for more messages, such as a widget's thread box
  (`x-thread-seat`), keeps focus in the box.
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
reachable by Tab, native activation, obligation digits or Go-to hints. `PAGE_COMMANDS` lists
the page commands in the order the menu and the reference list them. A lowercase letter steps a walk forward and
Shift steps it back, wrapping at either end. A surface may reuse a page key for the same
intent with a nearer destination. While the user is on an obligation, or its margin or thread
representative, core forwards only the widget's declared `contextKeys`; widgets assign their own `1`–`9`.

## Touch routes

Every page capability that a key reaches and no direct gesture does has a row among
the page's controls (`page-controls.js`), for a finger and a mouse alike. The row names
that control in `touch`, and `touch-controls.js` builds it from the same row the key
uses: a page command's control is a row of the floating panel's menu. A page scope's
rows take no words. What a gesture does next, a finger does on what the gesture acts
on: a search's arrows walk its matches from its box and a press on the marked match
selects it, a drawing's composer undoes its stroke, lifting a capture's drag attaches
it, and the page's field comments on selected words. So each row of a page scope that
runs a press says `touch: false`, or is its stance's way out. A stance a finger can
enter, such as page search, the target picker or Draw mode, marks its way out `exit`:
while it is the innermost stance standing, the panel says the scope's title and offers
that row as one ✕ at the row's end, beside the counts. The ✕ runs that row, which leaves the stance,
even where Escape would first close something inside it; the picker's, while a typed
hint prefix stands, takes back a letter, as its title says. The register refuses a
page command without `touch` and a scope row with a `run` that is neither `exit` nor
`touch: false`; `false` says a finger reaches the result directly, as it does for
walks and Go-to by scrolling and tapping, or through a control of the row's own beside
what it changes.

The comment field has one primary action, Dictate while empty and Send once it has
words; Suggest and reactions open by Tab from the field. The field deliberately has no
ellipsis menu, on phones too; change that only with the user, through a rendered design
comparison.

A command that should leave the user where they are declares `retainStanding`: the
floating panel saves focus, caret and selection as the user steps into it, and the
row's press restores them before running the command.

## Modules

`bindings.js` (key spelling and declaration checks), `scopes.js` (element scopes),
`register.js` (scope order, page commands, the Escape ladder), `dispatch.js`
(precedence), `controller.js` (input lifecycle), `text-entry.js` (native editing and
activation), `layer-stack.js` (popovers and dialogs over the page), `page.js` (the
page's own scope and the last Escape step), `go-to-sequence.js` (the `g` keys),
`hints.js` and `command-hints.js` (hint chips), `chip-seats.js` and
`key-badge-placement.js` (where chips sit), `touch-controls.js` (a finger's controls
for the keys), `status-context.js` (what the panel says of a walk, a Go-to filter or a stance),
and `control-keys.js`, `key-sequence.js`, `command-reference.js`, `disclosure.js`.

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
