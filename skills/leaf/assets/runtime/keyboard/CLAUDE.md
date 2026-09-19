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

The way out is as deep as the way in, counted in the reader's presses. A press's whole
effect is one rung: a command that opens a container and stands the reader in it is
undone by one Escape, which closes the container and restores the place the press
displaced. Standing on a destination — a card in the list, an Ask or a heading on the
page — is one rung whatever put the reader there: letting go lands them on the floor of
the layer they are in, the panel's list or the page's body, and it is an inner step
because standing is the newest thing they did. A press that stood them there records a
frame, and a frame holds the standing unless it says `standing: false` because its
press stood the reader nowhere, so that frame answers in the stack's order instead; a
walk pushes one such frame for however many steps it takes. A keyboard press's way out
never lands the reader on a control they never stood on; a pointer's way out lands on
the control the pointer pressed. `layer-stack.js` carries the mechanism.

## Page grammar

Page scope contains commands whose subject is the page. Surface scopes contain commands
whose subject is that surface's contents. A page-level letter must remain useful across
every page; a visible control otherwise remains reachable through Tab, its native
activation, contextual Ask digits, or generated Go-to hints.

`page.js` is the canonical page vocabulary. Directional walks use lowercase to advance
and Shift to go back. A surface may reuse a page key for the same intent with a nearer
destination; other local commands belong to the widget scope. The exact rows, rather
than a copied key list, state the current bindings.

While the reader stands in an Ask, core projects its widget's ordered Decision commands
onto `1` through `9`. A widget's declared route wins while focus is in that widget;
undeclared digits continue to the Ask projection. The digit and every intrinsic widget
binding invoke the original command through its stable identity and source scope.

## Module ownership

- `bindings.js` owns spelling, parsing, row fields, routes, and declaration checks.
- `scopes.js` owns element scopes and the shared command sections derived from them;
  `register.js` holds core's registered scopes.
- `dispatch.js` owns precedence and platform-default handling; `controller.js` owns the
  physical input lifecycle; `text-entry.js` owns native editing claims.
- `layer-stack.js` owns the ordered layers standing over the page: the popovers and modal
  dialogs their openers declare, across the document and declared shadow roots, and the
  inverse of commands that enter temporary layers.
- `page.js` declares core's scopes and rows.
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
