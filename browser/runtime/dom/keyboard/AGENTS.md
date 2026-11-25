# Keyboard runtime

The keyboard's modules are in three directories of the runtime. Each directory imports
only the ones listed before it:

- `dom/keyboard/`, this one: the register, its dispatch, the layer stack and the keys a
  control names. DOM, geometry and notice owners read it, such as `dom/geometry.js`,
  `dom/widget-elements.js` and `transport/notifications.js`, so it imports none of them and nothing
  that imports them.
- `readings/key-badges/`: the hint codes and binding badges painted on the page, and where they
  stand. The composer's target picker reads them, so they import nothing of the
  composer's.
- `panel/page-keys/`: the keys the page itself answers, such as a link's or a disclosure's,
  and the modules that join the register to the page's other features, the composer
  among them: the key listener, Go-to, the command reference, the status context and
  the touch rows.

This file holds the keyboard policy all three share; each module's header owns its own
contract, `bindings.js` the fields of a command row and `dispatch.js` which scope
answers a press.

## Ownership

A command is one capability, owned by the layer that implements its result. A binding
is a key that invokes it, and a scope says where the binding applies. Dispatch, the
floating panel's menu rows, the command reference, tooltips, announcements and
`aria-keyshortcuts` all read one register, so register a capability once and derive every presentation from
its row. A visible control names an existing command rather than copying its callback.

Core owns commands on the page, the chrome, navigation, comments and shared thread
state. A widget owns commands that read or change its content, and its scopes join the
register only while the widget exists. A package widget declares an element scope as
data, the element's `lfCommands`, which `scopes.js` reads when the element dispatches
`lf-commands`. Core declares one with `keys(element, …)`, or with `commandsOn(…)` in a
template, and both take a `commandScope(…)` value for a scope that stands in several
places. Core scopes over the
page use `pageScope`, `pageCommand` and `pageRung` in
`register.js`. A new scope, page command or Escape step also needs its place in
`register.js`'s `STACK`, `PAGE_COMMANDS` or `RUNG_LADDER`.

Every key in Leaf's runtime and its packages' widgets is declared, as
`test_the_register_is_the_only_way_a_key_enters_the_runtime`
(`tests/model/test_interact_layer.py`) pins. A page's own code may instead answer a key
itself, with a listener on its own element that prevents the key ("Scope resolution").
That key works while focus is in the element and reaches no Leaf command there, but it
gets none of what a declared row gets: a row in the command reference, a tooltip and
`aria-keyshortcuts`, forwarding from an obligation's margin entry or thread
(`contextKeys`), and a command in the interaction log. The command reference still lists
Leaf's own command for that key there, since nothing tells the register that the page
takes it.

## Scope resolution

A press goes to scopes from the focused element outward, ending at the page and then the
browser. A scope owns every binding it declares while the user is in it, so when its
command is unavailable the press reaches no other Leaf command. A text field keeps
characters, composition, caret movement and deletion, and a native control keeps its
activation press, ahead of any widget or page scope around it (`dispatch.js`). A key
other than typing or Escape, pressed while the user has scrolled the focused control out
of sight, lets go of it first, without closing what stands beside it, and then acts from
what they see, so no Leaf command, listener on the control or browser default acts on
what they can't see (`panel/page-keys/controller.js`). A key typed into one of Leaf's fields, a
`leaf-text` or a search box, stops at the field once the field and the dispatcher have
read it there (`base/field-keys.js`), so the page never hears it bubble, and any other Leaf
listener that needs keys typed into a field listens in capture. While Go-to or reactions
are armed, Leaf reads every key they answer in capture, before the page's listeners. It
also reads in capture a key aimed at `body` itself, with nothing focused: no element of
the page's has the user's focus to answer it, so Leaf's command runs first, and a page
listener hears only a key Leaf leaves. Leaf reads every other key, printed letters
included, on the root element: after the listeners on the focused control and on each
element around it, the page's own among them, and before the page's listeners on the
document and the window, which hear only a key Leaf leaves. A key aimed inside an
authored document, the page's `body` or a message's body, whose default is already
prevented there is its author's, and Leaf takes no step for it; the rest of Leaf's
chrome keeps its keys whatever a page listener prevents. A widget whose ARIA pattern
types ahead, such as a menu, a tree or a select-only combobox, keeps the letters and
digits typed while focus is in it, whether or not it prevents them, as a text field and
a select keep theirs (`text-entry.js`). A row that `waits`, as Escape letting go of a control in the
page, is read last, on the window, after every listener the page has, and only if none
prevented the key (`panel/page-keys/controller.js`).

## Escape

Escape closes one step of the current interaction and lands the user on that step's
parent. Both depend on what is open now, never on the route that opened it, so a
surface opened by pointer or Tab closes the same way as one opened by its key; only a
stance and a view of the floating panel are also ordered by which came last. The focused control's own step comes
first, then steps inside the focused surface, then the surface itself, then steps
outside it; `STACK` and `RUNG_LADDER` order siblings, and native modals and popovers
keep the browser's order. A close request, such as Android's back gesture, takes the
same step, through its row's `keep` where `run` would throw away unsent words
(`close-requests.js`).

- The document is the base. In a live sample, one more Escape returns focus to the
  containing page.
- A preview standing over the page is the first step, by pointer or by focus: Escape
  puts it away and does nothing else, and the next Escape takes the step it stood in
  front of (`annotations/preview.js`). Any other key puts a pointer's preview away and does its own
  work. A focus preview stands only where focus was moved by Tab or a placement
  standing in for one (`step`), the cause its mover gives `focusDestination`, so a
  command's landing, as a walk's (`move`), focus a surface places as it opens, and
  focus handed back as it closes or as Escape backs the user out (`return`), costs no
  Escape, and one put away stays away until the user aims again, whatever a widget
  declares meanwhile.
- Draw and Design are page modes; surfaces opened inside them close first, and a
  stance entered over a view of the floating panel ends before the view closes, so
  Escape takes whichever of the two came last.
- A surface's own state, such as Threads' search, clears before the surface closes.
  Page-side selections, targets, margin clusters and the page composer coexist beside a view the
  floating panel opens, and focus decides which answers first.
- A composer, reply box or find box returns to its container: an element comment's
  composer to its element, a reply box to its thread, a find box to its panel. A layer
  opened from the floating panel's menu returns to the panel.
- Send leaves a reply box or a first comment's box for its thread, as Escape from the
  box does, and so does a rewrite's Save: the thread's card, seat or panel view, never
  the box and never the page (`records/thread/landing.js`, `landSent`). `c` or Enter on the
  thread opens the box again.
- A selected destination (a thread, an obligation, a heading) steps back to the document
  through `letGo` (`dom/focus.js`), landing beside it while it is in view, else on the
  visible block, rather than on the control that opened it, so Tab carries on from it.
  Page Map returns focus to whatever opened it. Leaving a walk's stop leaves the user
  at it rather than on it, so the walk's next press returns there
  (`records/current-target.js`).

Go-to, target hints, page search, reactions and the command reference own the keyboard
while active and handle their own exit. Escape closes a surface even if it was open
before the interaction began, and closing one with the pointer focuses the control that
reopens it.

## Page grammar

Page scope holds commands about the page; a surface's scope holds commands about its
contents. A page-level letter must be useful on every page; any other control is
reachable by Tab, native activation, obligation digits or Go-to hints. A lowercase
letter steps a walk forward and Shift steps it back, wrapping at either end. A page
walk with nothing to step through says so in the panel (`notice`, such as “No open
threads”) rather than doing nothing, so its letter is live on every page. A walk over
a list the server's reading brings says instead that the list can't be had while the
server is offline. A walk, a
scroll, Go-to and any other command that takes the user somewhere declares `travels`
on its row; every other command leaves the control it was pressed on where it stood on
screen (`bindings.js`). A surface
may reuse a page key for the same intent with a nearer destination. While the user is
on an obligation, or its margin or thread representative, core forwards only the
widget's declared `contextKeys`, and widgets assign their own `1`–`9`. A thread's
view represents the question still open that the agent's latest message in it asks,
before the one the thread is about (`records/current-target.js`, `questionAsked`).

## Touch routes

Every page capability available through a key but not a direct gesture has a row among
the page's controls (`base/page-controls.js`). It supports both touch and mouse input and
comes from the same command row as the key (`panel/page-keys/touch-controls.js`). Actions within a
scope have controls beside the content they act on: a search box has arrows to move
between matches, a drawing's composer can undo a stroke, and the page's field can
comment on selected words. Page scope rows therefore have no touch labels: each row
that runs a press declares `touch: false` or is the `exit` of a stance accessible by
touch. Examples include page search, the target picker and Draw mode. The panel
offers the innermost active stance's exit as one ✕ before its leaf, named beside it,
and as Close with `esc` at its field's end while Escape would take the stance off. The ✕
leaves the stance even where Escape would first
close something inside it or take back a typed hint letter. The register
refuses a page command without `touch` and a scope row whose `run` is neither `exit`
nor `touch: false`.
`false` means the result is directly accessible by scrolling and tapping or through
the row's own control beside the content it changes.

Words owe a finger the same reach. A `title` shows only to a pointer resting on its
element, so it can't be the only place a state's reason or the rest of a cut word is
said. A state says its word on the surface that holds it (`quoteReading`), a panel
row's cut words stand whole where no pointer can hover (`floating-panel.css`), and
whatever previews, a control's word and keys among it, shows its preview to a finger
holding it. The hold reads and its release presses nothing, while a tap still presses,
so a finger reads without acting and without sliding off, which on touch often scrolls
instead (`annotations/preview.js`).

The comment field has one primary action, Dictate while empty and Send once it has
words. Suggest and reactions share an anchored Other responses picker, reached by the
⋯ beside Dictate while the field is empty, Tab from the field outside a list item
(in one, Tab nests the item, `nestItems` in `annotations/composing/field-editor.js`), or the
contextual reaction command. Opening the picker
keeps the field in place on desktop and touch surfaces alike.

A comment box that offers a second send, as one standing in a widget's outlet whose
`lfHold` names it does (`annotations/composing/surface.js`, `fabHoldAt`), leaves Tab its native
order and opens no picker by it. The second send is a press of its own beside the
primary action, and Tab is its keyboard route: from the field it reaches the primary
action, then the ⋯ while the field is empty, then the second send. The ⋯ still opens
the picker there.

A command that should leave the user where they are declares `retainCurrentLocation`: the
row's press restores the focus, caret and selection the floating panel saved as the
user stepped into it, then runs the command.

## Testing a binding

Test a changed binding inside and outside its scope and inside any native editor the
scope contains, and check that every way in has a matching way out across the register.
