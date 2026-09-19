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

Every owner declares its own keys where its code is, through one of two doors, and no
module enumerates another's capabilities to do it. A widget or a generated control uses
the element register — `keys(element, …)` and `commandScope(…)` in `scopes.js` — which
applies while focus is inside that element. A core owner whose condition is the page's
rather than the reader's position uses `register.js`: `pageScope(name, …)` for a scope of
its own, `pageCommand(row)` for a row of the page's own scope, and `pageRung(name, …)`
for a step of Escape's fallback ladder. Contribution runs as
the owner is constructed, so a row closes over that owner's state and the register never
holds a capability. Adding a command to a surface a feature already declares costs
nothing outside that feature; a new page-level letter, or a new scope, takes its rank in
the two orders `register.js` holds.

## Scope resolution

Ordinary bindings resolve from the focused element outward: an exact control or active
mode, native interaction, the nearest widget and its widget ancestors, Leaf's contextual
and page scopes, then the browser. An implemented declaration receives first refusal
while its scope stands. If its command is unavailable, the press does not fall through
to another Leaf meaning. A declaration without a Leaf invocation presents native or
shared behavior and does not shadow an outer handler.

Text entry keeps characters, composition, caret movement, deletion, and other editing
keys ahead of ancestor widget scopes. An exact control may still declare a sequence such
as Mod+Enter or its own Escape step.

Escape follows semantic unwind order instead of ordinary reservation. The focused
control or active mode may consume one inner step, followed by the latest eligible return
frame and then containing fallbacks. Browser modal and popover boundaries remain outside
that order. One press closes one layer.

Those fallbacks are the ladder at the foot of the stack, for state the reader reached
without a registered keyboard entry: a captured target, a pointer-opened tray or panel,
ordinary focus traversal. Each step is contributed through `pageRung` by the owner of
the state it takes off and says what that press would take; `register.js` orders them
and resolves the innermost into the one command every surface reads, rooted at the
surface that step is inside. One command rather than one per step, because a reference
listing each step whose own condition holds would promise presses the innermost step has
already taken, and because being the fallback is a fact about the ladder rather than
about any step: no step answers while a commanded entry stands.

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

While the reader stands in an Ask, core projects its widget's ordered Decision commands
onto `1` through `9`. A widget's declared route wins while focus is in that widget;
undeclared digits continue to the Ask projection. The digit and every intrinsic widget
binding invoke the original command through its stable identity and source scope.

## Module ownership

- `bindings.js` owns spelling, parsing, row fields, routes, and declaration checks.
- `scopes.js` owns element scopes and the shared command sections derived from them.
- `register.js` owns the page's keyboard: the order core's scopes shadow one another in,
  the rank of the page's own commands, Escape's fallback ladder and the one command it
  resolves to, the three doors owners contribute through, and the auxiliary-layer
  readings the dispatcher reads without an edge to their owner.
- `dispatch.js` owns precedence and platform-default handling; `controller.js` owns the
  physical input lifecycle; `text-entry.js` owns native editing claims.
- `layer-stack.js` owns the ordered layers standing over the page: the popovers and modal
  dialogs their openers declare, across the document and declared shadow roots, and the
  inverse of commands that enter temporary layers.
- `page.js` declares the page's own parts — a link, a disclosure, caret browsing, and the
  two ends of the Escape ladder — and exports nothing.
- `control-keys.js` paints the shortcut a visible control advertises, from the row that
  reaches it.
- `presentation.js` projects immutable key-sequence readings through the shared Lit
  template. `shortcut-bar.js` and `command-reference.js` synchronously derive and
  Lit-render their complete persistent surfaces from evaluated command readings; their
  controllers retain native focus, disclosure, fitting, and dispatch mechanics.
- `hints.js` owns the generated-hint session: the route codes, the no-drop placement
  pass, and the arming, prefix, audible walk, scroll freeze, and keyed Lit paint over
  them. `go-to-sequence.js` and `composing/target-chooser.js` each declare one scene,
  chip, and activation over that session and hold nothing of the interaction themselves.
  `key-badge-placement.js` owns what the reader can see of a target — the room the banner
  leaves, and the hit test that catches a member covered without being clipped — and the
  reserved placement Ask binding badges use. Both maps admit and seat members by that one
  reading, so "visible" means the same thing wherever the reader is offered a letter.
  Chrome at the foot is deliberately outside it: the bar states the armed map's own keys,
  so a map that read it would lose members as it armed. A chip that would land there is
  moved by the placement pass instead. A page-search mark is drawn where it stands rather
  than moved, so it alone reads a box with that chrome taken out (`clearPart`).
- `disclosure.js` owns the shared native disclosure reading and bindings.

Before changing a binding, inspect the complete register for conflicting meanings,
native behavior, entry and exit symmetry, focus restoration, and every projection that
will advertise it. Test the press both inside and outside its scope and inside any native
editor the scope may contain.
