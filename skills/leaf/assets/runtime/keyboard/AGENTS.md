# Keyboard runtime

This file owns the contracts the modules here share; each module's header owns its
own. The parent `../../AGENTS.md` owns interactions with state, widgets, threads,
and chrome.

## Ownership

A command is one stable capability, owned by the layer that implements its
result. A binding is a chord that invokes it, and a scope says where the binding
applies. A contextual surface may add a binding to an existing command but never
copies its callback. One register supplies dispatch, the shortcut bar, the
command reference, control tooltips, announcements, and `aria-keyshortcuts`, so
register a capability once and derive every presentation from its row; a visible
control names the same command rather than creating a parallel action.

Core owns commands on Leaf's page, chrome, navigation, comments, and shared thread
state; a widget owns commands that interpret or change its content, and its
scopes join the register only while the instance exists. Owners declare their keys
during construction: element scopes through `keys(element, …)` and
`commandScope(…)` in `scopes.js`, core scopes through `pageScope`, `pageCommand`,
and `pageRung` in `register.js`. A new scope, page command, or Escape rung also
needs an entry in the register's ordering tables.

## Scope resolution

Bindings resolve from the focused element outward: an exact control or active
mode, native interaction, the nearest widget and its widget ancestors, Leaf's
contextual and page scopes, then the browser. An implemented declaration gets
first refusal while its scope stands; if its command is unavailable, the press
does not fall through to another Leaf meaning. Text entry keeps characters,
composition, caret movement, and deletion ahead of ancestor widgets, as radio,
slider, and open-select navigation do; an exact control may still claim Enter or
its own Escape step.

## Escape unwinds the hierarchy, not the history

Escape removes one layer of the current interaction and lands at its parent. The
canonical keyboard route into a state defines that parent, pointer and Tab entry
leave by the same route, and the runtime does not record how the user arrived.
Containment decides order: the focused control's own claim, then steps inside the
focused surface, then that surface, then steps outside it, with `STACK` and
`RUNG_LADDER` ranking siblings. Native modal and popover layers keep the
browser's order.

- The document is the base; a live specimen holding focus adds a final step back
  to its containing page.
- Draw and Design are page modes; surfaces opened within them close first.
- An auxiliary surface contains its own state, such as the Threads narrowing.
  Page-side selections, targets, clusters, and the page composer coexist beside
  it, and focus decides which answers first.
- A composer, reply box, or find box exits to its container; a reply box returns
  to its thread, then the whole panel, which clears narrowing before closing.
- Threads has two selection levels, the whole panel (`g T`) and one thread, and a
  title selects the same thread as its body. Enter or Space selects a closed
  title and keeps an open one selected; Comment enters the reply box even from a
  collapsed title.
- A selected destination (thread, Ask, heading) has a let-go step back to the
  document, through `letGo`, which lands on the visible block rather than an
  earlier chrome invoker.
- A thread in the margin card has the element it is about as its parent.

Bounded interactions (Go-to, target hints, page search, reactions, the command
reference) own the keyboard and their return while active and add no page mode.
Unwinding closes a surface even if it was open before entry. Closing by pointer
focuses the surviving reopening control. `register.js` exposes the innermost step
as one `navigation.back` command.

TODO: the page's `t` departs from this for threads that need the panel: it opens them
directly but exits through whole-panel selection. Keep that until a route
respects the hierarchy without making page threads harder to reach.

## Page grammar

Page scope holds commands whose subject is the page; surface scopes hold commands
about their contents. A page-level letter must stay useful on every page; any
other control stays reachable through Tab, native activation, Ask digits, or
Go-to hints. `register.js`'s `PAGE_COMMANDS` is the canonical page vocabulary in
shortcut-line order. Lowercase advances a walk and Shift goes back. A surface may
reuse a page key for the same intent with a nearer destination. While the user
stands in an Ask, core projects its widget's Decision commands onto `1`–`9`; a
widget's own binding wins while focus is inside it.

## Modules

`bindings.js` (spelling, parsing, declaration checks), `scopes.js` (element
scopes), `register.js` (scope order, page commands, the Escape ladder),
`dispatch.js` (precedence), `controller.js` (input lifecycle), `text-entry.js`
(native editing claims), `layer-stack.js` (popovers and dialogs over the page),
`page.js` (the page's own parts and the foot of the ladder), `control-keys.js`,
`presentation.js`, `shortcut-bar.js`, `command-reference.js`, `hints.js`,
`key-badge-placement.js`, and `disclosure.js`.

Test a changed binding inside and outside its scope and inside any native editor
the scope contains, and check entry and exit symmetry against the whole register.
