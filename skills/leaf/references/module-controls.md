# Generated controls

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

`offer(tag, className, label, inputType, pressable)` makes a native control, or a box of
controls, marked as Leaf-generated; the browser keeps its activation, focus and
accessibility. `inputType` is for an `input`. Pass `pressable: true` for a custom element
whose host implements `focus()` and `click()`. In a template, `<div
${offered("my-tools")}>` does the same, with an input's `type` binding placed before
`offered`. `offerElement(node, className, pressable)` marks an existing node.

A button that looks like Leaf's own controls is built by its role, so every control of
one kind wears one face: `offerAction(role, className, label, {title, action})`, or
`<button ${offeredAction(role, className, label, {action})}></button>` in a template.
There `label` is a symbol's or mark's accessible name, and the template writes any other
role's words.
`offerActionElement(node, role, className, label, {title, action})` applies the same
face, symbol and name to an existing node. The roles are:

- `"symbol"`, a press showing the symbol of its `action`, one of Leaf's actions
  (`module-reading.md`, "Icons"). Its tooltip and accessible name are the action's
  name, or `label` where that says more; `title` replaces the tooltip where it says
  more still, such as the key that does the same.
- `"word"`, a press whose words, `label`, say what it does; a toggle adds
  `aria-pressed`.
- `"commit"`, the one press on a surface that commits the user's work.
- `"mark"`, a small symbol at a corner of the thing it acts on, naming its `action`.
- `"inline"`, a press read as part of its line of words, such as a quote's "Full
  quote", drawn in the accent; one saying a warning takes `data-lf-tone="warn"`.
- `"row"`, one row of a list or menu, washed under the pointer or the keys; the row the
  list stands on, such as a timeline's step, takes `aria-current`, drawn in the accent.
- `"answer"`, one of a question's answers; the chosen one takes `aria-pressed="true"`.
- `"entry"`, a margin entry, which Leaf builds.
- `"reaction"`, a message's reaction, `aria-pressed="true"` in force.
- `"response"`, a response bar's choice, which Leaf builds.
- `"gutter"`, a code line's number that takes a comment.
- `"picture"`, a picture that opens in the media viewer.
- `"fold"`, the line a folded group stands as, which opens it (`aria-expanded`).
- `"proxy"`, a hidden keyboard stand-in for something the pointer takes by itself, such
  as a phrase that explains; give that thing the ring its focus draws.

`className` places the control; don't restyle its face. Use a symbol where a standard
symbol for the action exists, one readers know from other software, and words where
none does.
Shared control styles (`page-layout.md`, "Page CSS and Leaf's controls") apply to
generated controls too.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so build it with `selectableOffer(role, className, label)`, a focusable
span, or `<span ${selectableOffered(role, className)}>${label}</span>`. With the role
`"button"`, Enter and Space press it, with Leaf or without, and like any press it
names its role last: `selectableOffer("button", className, label, "row")`. For
another role, such as `"tab"`, the widget declares its keys. Printing drops every
offer, so build structure that isn't injected UI with `el(tag, className, text)`.

Words a module writes into the page are the page's words unless it marks them apart
(`module-plain-elements.md`, "Words it writes").

A widget can upgrade inside a shut panel where every box measures zero, so take
measurements inside `measure(element, take)`, which runs `take` once the element has a
box. After a view swap that rearranges a widget's contents without resizing it, call
`layoutChanged(element)`, which dispatches `lf-layout` to the widgets and runtime readers
that measure what they hold, so they read again.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

On a plain host, load `/vendor/webawesome.esm.js` to upgrade a search field's editor.
