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

Every owner declares its own keys where its code is, and no module enumerates another's
capabilities to do it. A widget or a generated control uses
the element register — `keys(element, …)` and `commandScope(…)` in `scopes.js` — which
applies while focus is inside that element. A core owner whose condition is the page's
rather than the reader's position uses `register.js`: `pageScope(name, …)` for a scope of
its own, `pageCommand(row)` for a row of the page's own scope, and `pageRung(name, …)`
for a step of Escape's fallback ladder. Contribution runs as
the owner is constructed, so a row closes over that owner's state and the register never
holds a capability. Adding a command to a surface a feature already declares costs
nothing outside that feature; a new page-level letter, a new scope, or a new step of the
Escape ladder takes its rank in the orders `register.js` holds.

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
control or active mode may consume one inner step; then the surface holding focus, with
whatever the reader has put on inside it; then every step rooted outside that surface,
in the register's order. Browser modal and popover boundaries remain outside that order.
One press closes one layer.

## Escape unwinds the hierarchy, not the history

**The canonical keyboard route down to a state is matched, step for step, by the Escape
route back out of it.** That is what Leaf guarantees a reader, and the sentence that
decides any case.

It is stated over what stands in front of the reader rather than over how they got
there. Nothing records a press, so one state has one way out however it was reached, and
a pointer press or a Tab is an arbitrary jump into the hierarchy rather than a descent
through it: it gets the same unwind, and is owed no return to the control it landed on.

The levels, outermost in:

1. **The document** — the reader's position in the authored page, and the destinations
   they can stand on. This is the floor; Escape's job ends here.
2. **Page-side state** put on without entering chrome: a selection, a captured target,
   an unfolded margin cluster, the page composer.
3. **Auxiliary surfaces**: the Threads panel, the trays.
4. **Layers of a surface**: the panel's narrowing, a widget's filter.
5. **Native layers**: a margin card, the versions menu, a modal dialog.
6. **Boxes**: a composer, a reply box, a find box, which their surface contains.

A bounded interaction — the Go-to sequence, the target chooser, page search, reactions,
the command reference, draw and design mode — owns the keyboard while it stands and
unwinds itself. It is not a level, and it hands the reader back itself.

Levels alone do not order two steps standing at once, because a reader inside the panel
may have left a selection on the page behind them. **Containment comes before kind**: a
step rooted inside the surface holding focus answers before that surface, and a step
rooted outside it answers after. The register's orders — `STACK` and `RUNG_LADDER` —
rank siblings, which is the only order they can state.

Each step lands the reader at the parent of what it closed: a box at its container, a
standing at its floor, a surface at the document. **A landing in the document is the
block the reader is reading**, focused and then blurred (`letGo`), read off the current
scroll rather than remembered from before the press: a surface closing moves the page
under them, and what they can see once it has gone is the answer. The focus moves the
browser's sequential focus navigation starting point there, so their next Tab carries on
from what they are reading; the blur hands Space and PageDown back to the page's own
scroll box. A chrome control — the Threads toggle, a margin marker, a mark's note, a tray
row — is never the landing for a step whose parent is the document. A step whose parent
really is a control does land there: a reply box hands back to its thread, an unfolded
margin cluster to the entry it hangs from.

Standing on a destination — a card in the list, an Ask or a heading on the page — is one
step of its own, whatever put the reader there: letting go lands them on the floor of the
layer they are in, the panel's list or the page, and it is an inner step because standing
is the newest thing they did.

What this gives up, each a rule the reader can learn: a surface they already had open
closes on the way out, because no state distinguishes one this press opened from one it
found; `g A` from Threads leaves Threads shut; a press that opens a container only to
hold its content costs two Escapes, so `c` from the page leaves the box and then the
panel; a walk is not rewound, and the reader lands in the document where they now are; a
control reached by Tab or by click is not returned to.

A close by pointer — the view's ×, the panel's Close — is not an Escape and takes the
layer off without a landing: the pointer is already on the surface that is closing, so
focus lands on the surviving control that reopens it.

Those steps are contributed through `pageRung` by the owner of the state each one takes
off; `register.js` orders them and resolves the innermost into the one `navigation.back`
command every surface reads, rooted at the surface that step is inside. One command
rather than one per step, because a reference listing each step whose own condition holds
would promise presses the innermost step has already taken. `layer-stack.js` holds only
the native layers the browser is standing, in the order they opened, because that is the
one fact about the scene its own DOM cannot be asked for in order.

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
