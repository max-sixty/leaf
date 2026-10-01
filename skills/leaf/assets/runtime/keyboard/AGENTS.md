# Keyboard runtime

This file owns the contracts the modules here share; each module's header owns its
own.

## Ownership

A command is one capability, owned by the layer that implements its result. A binding
is a chord that invokes it, and a scope says where the binding applies. One register
supplies dispatch, the shortcut bar, the command reference, control tooltips,
announcements, and `aria-keyshortcuts`, so register a capability once and derive every
presentation from its row. A contextual surface or visible control names an existing
command rather than copying its callback.

Core owns commands on the page, chrome, navigation, comments, and shared thread state;
a widget owns commands that interpret or change its content, and its scopes join the
register only while the instance exists. Element scopes declare through `keys(element,
…)` and `commandScope(…)` in `scopes.js`, core scopes through `pageScope`,
`pageCommand`, and `pageRung` in `register.js`. A new scope, page command, or Escape
rung also needs its place in `STACK`, `PAGE_COMMANDS`, or `RUNG_LADDER`.

## Scope resolution

Bindings resolve from the focused element outward: an exact control or active mode,
native interaction, the nearest widget and its widget ancestors, Leaf's contextual and
page scopes, then the browser. A declaration gets first refusal while its scope applies
(`dispatch.js`'s `standing`: the user is in it and the page has it); if its command is
unavailable, the press does not fall through to another Leaf meaning. Text entry keeps
characters, composition, caret movement, and deletion ahead of ancestor widgets; an
exact control may still claim Enter or its own Escape step.

## Escape

Escape removes one layer of the current interaction and lands at its parent. The
canonical keyboard route into a state defines that parent; pointer and Tab entry leave
by the same route, and the runtime does not record how the user arrived. Containment
decides order: the focused control's own claim, then steps inside the focused surface,
then that surface, then steps outside it, with `STACK` and `RUNG_LADDER` ranking
siblings. Native modal and popover layers keep the browser's order.

- The document is the base; a live sample holding focus adds a final step back to its
  containing page.
- Draw and Design are page modes; surfaces opened within them close first.
- An auxiliary surface contains its own state, such as the Threads narrowing.
  Page-side selections, targets, clusters, and the page composer coexist beside it, and
  focus decides which answers first.
- A composer, reply box, or find box exits to its container; a reply box returns to its
  thread, then the whole panel, which clears narrowing before closing.
- A sent reply, or the first comment of a thread, leaves the user on the thread. A
  thread in the margin card leaves them on the element it is about, with the card up,
  so one Escape takes the card down and moving elsewhere needs none. A box that stays
  open for more messages, such as a seat's or the Threads panel's general box, keeps the
  user in it.
- Threads has two selection levels, the whole panel (`g T`) and one thread, and a title
  selects the same thread as its body. Enter or Space selects a closed title and keeps
  an open one selected; Comment enters the reply box even from a collapsed title.
- The versions menu's parent is More, however it opened (`g V` included), so Escape
  steps back to the version picker there.
- A selected destination (thread, Ask, heading) lets go back to the document through
  `letGo`, which lands on the visible block rather than an earlier chrome invoker.

Bounded interactions (Go-to, target hints, page search, reactions, the command
reference) own the keyboard and their return while active and add no page mode.
Unwinding closes a surface even if it was open before entry, and closing one by pointer
focuses the control that reopens it. `register.js` exposes the innermost step as one
`navigation.back` command.

TODO: the page's `t` opens threads that need the panel directly but exits through
whole-panel selection. Keep that until a route respects the hierarchy without making
page threads harder to reach.

## Page grammar

Page scope holds commands whose subject is the page; surface scopes hold commands about
their contents. A page-level letter must be useful on every page; any other control
stays reachable through Tab, native activation, Ask digits, or Go-to hints.
`register.js`'s `PAGE_COMMANDS` is the page vocabulary in shortcut-line order. Lowercase
advances a walk and Shift goes back. A surface may reuse a page key for the same intent
with a nearer destination. While the user stands in an Ask, core projects its widget's
Decision commands onto `1`–`9`; a widget's own binding wins while focus is inside it.

## Touch routes

Under a coarse pointer, every page capability that a key reaches and no direct gesture
does has a banner control. A row declares the control's words as `touch`, or a routed
row declares them on each route that needs its own control; `touch-controls.js` builds
the control from the row the key uses.

- A page command's control is an entry in the banner's More.
- A page-scope row's control is a step on the banner's row while its scope is the
  innermost applying scope with steps, since a phone's row fits one interaction's. A
  mode or bounded interaction a finger can enter declares its way out, and anything else
  inside it a finger cannot otherwise do, such as walking search matches.

Every page command declares `touch`, and the register refuses one that does not; `false`
says a finger reaches the result directly. The existing `false` rows rest on these
routes:

- walks, paging, scrolling, and Go-to: scrolling, and tapping the Threads list, the
  Asks drawer, or the Page Map;
- `n` on a closed search: searching again from More;
- the ⌥ aim: selecting words, or Select element;
- `c` and `e`: the selection's Comment on selection step and response options, a
  thread's own controls, and the Threads box;
- Ask digits: the Decision's own control;
- the command reference and caret browsing, which describe or extend the keyboard
  itself and have no finger equivalent to need.

## Testing

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check entry and exit symmetry against the whole register.
