# Keyboard runtime

This file owns contracts shared by the modules in this directory. Each module's header
owns its data and behavior. The parent runtime guidance owns interactions with browser
state, widgets, conversations, and chrome.

## Ownership

A command is one stable capability. The layer that implements the command's semantic
result owns it. A binding is a route to that command, and a scope defines where the route
applies. Contextual surfaces may add routes to an existing command; they do not copy its
callback or become another command owner.

One register supplies dispatch, the shortcut bar, the command reference, control
tooltips, announcements, and `aria-keyshortcuts`. Register a capability once and derive
every route and presentation from that row. A visible control names the same command
rather than creating a parallel keyboard action.

Core owns commands that act on Leaf's page, chrome, navigation, comments, and shared
conversation state. A widget owns commands that interpret or change its content. Widget
scopes join the register only while their instance exists.

Owners declare their keys during construction, before the first scope read. Element
scopes use `keys(element, …)` and `commandScope(…)` from `scopes.js`. Core scopes use
`pageScope`, `pageCommand`, and `pageRung` from `register.js`. Adding a command to an
existing scope stays with its owner; a new scope, page command, or Escape rung also needs
an entry in the register's ordering tables.

## Scope resolution

Ordinary bindings resolve from the focused element outward: an exact control or active
mode, native interaction, the nearest widget and its widget ancestors, Leaf's contextual
and page scopes, then the browser. An implemented declaration receives first refusal
while its scope stands. If its command is unavailable, the press does not fall through
to another Leaf meaning. A declaration without a Leaf invocation presents native or
shared behavior and does not shadow an outer handler.

Text entry keeps characters, composition, caret movement, deletion, and other editing
keys ahead of ancestor widget scopes. An exact control may still declare Enter to
submit or its own Escape step. Radio and slider navigation likewise belongs to
the focused control before ancestor widgets, and a focused select option retains
typeahead while its list is open.

## Escape unwinds the hierarchy, not the history

Escape removes one layer of the current interaction and lands at its parent. The
canonical keyboard route into a state defines that parent; pointer and Tab entry use the
same route out. The runtime does not record how the user arrived. The current `t`
shortcut departs from entry/exit symmetry as described below.

Containment decides which layer closes first. An inner claim from the focused control
or active interaction answers first, followed by steps inside the focused surface, then
that surface, then steps outside it. `STACK` and `RUNG_LADDER` rank siblings. A selection
left on the page therefore waits while the user is inside Threads and answers first
when focus is on the page. Native modal and popover boundaries keep their browser order.

These states have distinct parents:

- The document is the base. A live specimen holding focus adds a final Escape back to
  its containing page after its own unwind finishes.
- Draw and Design are page modes. Surfaces opened within them close before the mode.
- Auxiliary surfaces contain their own state, such as the Threads narrowing. Page-side
  selections, captured targets, expanded margin clusters, and the page composer can
  coexist beside an auxiliary surface; focus determines which answers first.
- A composer, reply box, or find box exits to its container. A native layer such as a
  margin card, versions menu, or modal dialog owns its dismissal.
- A selected page destination, such as a conversation, Ask, or heading, has a let-go step
  back to the document. Page-side state added there closes before that step.

Bounded interactions — Go-to, target hints, page search, reactions, and the command
reference — own the keyboard and their return while active. They do not add persistent
page modes to the ladder.

A landing in the document uses the block visible after closing the surface, through
`letGo`: focus establishes the starting point for the next Tab, then blur returns Space
and PageDown to page scrolling. It does not restore an earlier chrome invoker. A step
whose parent is a control lands there instead: a reply box returns to its thread, and an
expanded margin cluster returns to its entry.

The Threads panel has two selection levels: the whole panel, reached by `g T`, and
one thread, reached by the semantic thread walk or focus inside that thread. Escape
from a reply box returns to its thread, then to the whole panel, preserving disclosures
and drafts. At the whole-panel level, Escape removes narrowing, then closes the panel.
A title and its conversation select the same thread. Native focus order runs from the
title through its open conversation; Enter/Space selects a closed title, leaves an open
one selected, and Comment enters the reply box even from a collapsed title.

TODO(2026-09-22): Reconcile the page's `t` shortcut with this hierarchy. It jumps directly
to a page thread, bypassing panel selection. A thread that requires the panel also opens
directly with `t`, but exits through whole-panel selection. Preserve this behavior until
there is a route that respects the hierarchy without making page threads harder to reach.

Unwinding closes a surface even if it was already open before entry. Thus `g A` from
Threads leaves Threads closed, and `c` from the page needs one Escape from the box and
another from the panel. Walks do not rewind; document landings use the current position.

Closing by pointer uses the surviving reopening control for focus rather than Escape's
parent landing. Each state owner contributes its Escape step through `pageRung`;
`register.js` exposes the innermost available step as one `navigation.back` command.
`layer-stack.js` records open native layers in opening order.

## Page grammar

Page scope contains commands whose subject is the page. Surface scopes contain commands
whose subject is that surface's contents. A page-level letter must remain useful across
every page; a visible control otherwise remains reachable through Tab, its native
activation, contextual Ask digits, or generated Go-to hints.

`register.js`'s `PAGE_COMMANDS` is the canonical page vocabulary, in the order the
shortcut line ranks it; each row is declared by the owner that implements it. Directional
walks use lowercase to advance and Shift to go back. A surface may reuse a page key for
the same intent with a nearer destination; other local commands belong to the widget
scope. The exact rows, rather than a copied key list, state the current bindings.

While the user stands in an Ask, core projects its widget's ordered Decision commands
onto `1` through `9`. A widget's declared route wins while focus is in that widget;
undeclared digits continue to the Ask projection. The digit and every intrinsic widget
binding invoke the original command through its stable identity and source scope.

## Module ownership

- `bindings.js` owns spelling, parsing, row fields, routes, and declaration checks.
- `scopes.js` owns element scopes and the shared command sections derived from them.
- `register.js` owns the page's keyboard: the order core's scopes shadow one another in,
  the rank of the page's own commands, Escape's ladder and the one command it
  resolves to, the doors owners contribute through, and the auxiliary-layer readings the
  dispatcher reads without an edge to their owner.
- `dispatch.js` owns precedence and platform-default handling; `controller.js` owns the
  physical input lifecycle; `text-entry.js` owns native editing claims.
- `layer-stack.js` owns the ordered layers standing over the page: the popovers and modal
  dialogs their openers declare, across the document and declared shadow roots.
- `page.js` declares the page's own parts — a link, a disclosure, caret browsing, the
  standing scope's let-go, and the foot of the Escape ladder. Its one export is
  `declareStanding`, which the boot entry calls with the readings the let-go consults.
  `focus.js` owns the landing itself (`letGo`), against the reading the boot entry
  declares with `declareReading`.
- `control-keys.js` paints the shortcut a visible control advertises, from the row that
  reaches it.
- `presentation.js` projects immutable key-sequence readings through the shared Lit
  template. `shortcut-bar.js` and `command-reference.js` synchronously derive and
  Lit-render their complete persistent surfaces from evaluated command readings; their
  controllers retain native focus, disclosure, fitting, and dispatch mechanics.
- `hints.js` owns generated-hint sessions. `go-to-sequence.js` and
  `composing/target-chooser.js` supply their scenes and activation commands.
  `key-badge-placement.js` supplies visibility and reserved placement for hints and Ask
  badges. Its visibility reading excludes the shortcut bar, whose changing armed-map
  commands must not change map membership. Hint chips avoid that bar during placement;
  page-search marks stay at their targets and use `clearPart` to exclude its box.
- `disclosure.js` owns the shared native disclosure reading and bindings.

Before changing a binding, inspect the complete register for conflicting meanings,
native behavior, entry and exit symmetry, focus restoration, and every projection that
will advertise it. Test the press both inside and outside its scope and inside any native
editor the scope may contain.
