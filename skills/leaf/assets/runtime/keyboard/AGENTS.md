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
page scopes, then the browser. An implemented declaration gets first refusal while its scope applies
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
  Page-side selections, targets, clusters, and the page composer coexist beside
  it, and focus decides which answers first.
- A composer, reply box, or find box exits to its container. An element comment
  composer returns to the subject its anchor resolves, or that subject's declared
  response proxy; an Ask remains a separate step before the document. A reply box
  returns to its thread, and the thread to the panel's rungs, which clear narrowing
  before closing.
- A reply, or the first comment that starts a thread, leaves the user standing on
  the thread's card or title once sent, including in the margin. Send never returns
  focus to the page; Escape follows the card's usual route back to its target.
  The page comment card also stays open and focused after Send; `c` writes again,
  and Escape closes it and returns to the control it hangs from.
  A box that stays open for more messages, such as a seat's
  or the Threads panel's general box, keeps the user in it.
- Threads selects one thread whenever it shows any, and focus on the list is focus
  on that thread's title: `g T`, and an Escape from the general box, land there.
  The list stands alone only while it shows no thread. A title selects the same
  thread as its body, and the user's move onto a title selects its thread, by any
  route, so the focused thread is always the open one and its reply box is the one
  `c` names. The runtime putting them back on a title chooses nothing: it returns them
  to the title they had chosen, or to the open one the list stands in with when a
  change took theirs away, and a hold put back after the choice moved under it, which
  leaves them on a closed title, is the one place the two part. Enter or Space keeps it
  selected.
- The versions menu opens from inside More, so More is its parent whichever route
  opened it (`g V` included), and Escape steps back to the version picker there.
- A selected destination (thread, Ask, heading) has a let-go step back to the
  document, through `letGo`, which lands on the visible block rather than an
  earlier chrome invoker.
- Cancelling Page Map with Escape or its Close control returns to the opening
  focus, or to the prior reading position when there is no opener. Activating a
  selected destination navigates there instead of taking that cancellation route.
- A thread in the margin card has the element it is about as its parent.

Bounded interactions (Go-to, target hints, page search, reactions, the command
reference) own the keyboard and their return while active and add no page mode.
Unwinding closes a surface even if it was open before entry, and closing one by pointer
focuses the control that reopens it. `register.js` exposes the innermost step as one
`navigation.back` command.

## Page grammar

Page scope holds commands whose subject is the page; surface scopes hold commands
about their contents. A page-level letter must stay useful on every page; any
other control stays reachable through Tab, native activation, Ask digits, or
Go-to hints. `register.js`'s `PAGE_COMMANDS` is the canonical page vocabulary in
shortcut-line order. Lowercase advances a walk and Shift goes back. A surface may
reuse a page key for the same intent with a nearer destination. While the user
stands in an Ask or its associated margin/thread representative, core forwards only
the widget's explicit `contextKeys`. Widgets own `1`–`9` assignments; Decision is a
semantic role, not an allocator. Ordinary local keys take precedence over context
aliases in the same attachment, and every context alias follows native editing.

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
says a finger reaches the result directly. Walks, paging, scrolling, and Go-to move the
reader, which a finger does by scrolling and by tapping the Threads list, the Questions panel,
or the Page Map. `n` walks a search that has closed, which a finger searches again from
More. Choosing a match is the soft keyboard's Enter, or selecting the marked words.
The ⌥ aim names a target, which a finger does by selecting words or through Select
element. `c` and `e` act on a selection, the item the user stands on, or the page: a
selection's Comment on selection step, a thread's own controls, and Comment on the page
in More all take a tap. One gap is accepted for now: the response bar's other responses, Suggest
and the reactions on a selection or item, open only by key, since the bar shows no
ellipsis (`composing/selection.js`; `TODO.md` asks whether to restore a route). Ask
digits duplicate the Decision's own control. The command reference and caret browsing
describe or extend the keyboard itself.

A command that preserves the reader's current context declares `retainStanding`.
More holds a transient focus, caret and selection checkpoint before borrowing focus;
its derived control restores that checkpoint before checking and invoking the row.
Closing More or standing outside it retires the checkpoint.

## Modules

`bindings.js` (spelling, parsing, declaration checks), `scopes.js` (element
scopes), `register.js` (scope order, page commands, the Escape ladder),
`dispatch.js` (precedence), `controller.js` (input lifecycle), `text-entry.js`
(native editing claims), `layer-stack.js` (popovers and dialogs over the page),
`page.js` (the page's own parts and the foot of the ladder), `go-to-sequence.js`
(the `g` grammar), `control-keys.js`,
`presentation.js`, `shortcut-bar.js`, `command-reference.js`, `hints.js`,
`command-hints.js` (inline hints from reachable command bindings),
`key-badge-placement.js`, `chip-seats.js` (where key chips stand), `disclosure.js`,
and `touch-controls.js` (a finger's stand-ins for the keys).

Test a changed binding inside and outside its scope and inside any native editor
the scope contains, and check entry and exit symmetry against the whole register.
