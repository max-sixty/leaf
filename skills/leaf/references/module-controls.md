# Generated controls

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

Build each control the widget injects, and each box of controls, with the library's
control constructors (`module-authoring.md`, "Shared web code"). They build the native
element, so the browser keeps its activation, focus and accessibility, and mark it as
Leaf-generated, which Leaf reads to tell the widget's apparatus from the author's
words. A press that looks like Leaf's own controls is built by its role, so every
control of one kind wears one face, and a press that shows a symbol names its action
(`module-reading.md`, "Icons"). A class of the widget's places the control; don't
restyle its face. Shared control styles (`page-layout.md`, "Page CSS and Leaf's
controls") apply to generated controls too.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so the library builds it as a focusable span with the control's role
rather than as a form control. With a button's role, Enter and Space press it, with
Leaf or without; for another role, such as a tab's, the widget declares its keys.
Printing drops every generated control, so build structure that isn't injected UI with
`el(tag, className, text)`.

Words a module writes into the page need no marking: setting an element's
`textContent`, appending a paragraph or rendering a template leaves them the page's
words, which the user can comment on. A version comparison reads each version's source
rather than the page, so they never read as a change. To set apart words the widget
writes, such as a count after an authored sentence or a generated control's label, mark
their element with `generatedElement(node, {says})`. Set `says: true` where the words
are the page speaking, as a pick mark reading "selected" does, `false` for an action
word, and `"echo"` for a copy of words the page shows elsewhere, such as a worker's
name; in a template, write `<h2 ${generated({ says: true })}>`. `named()` then
leaves them out, and a comment's quote doesn't run across them into the author's words. Don't write the
`data-lf-gen`, `data-lf-said` or `data-lf-echo` attributes yourself.

A widget can upgrade inside a shut panel where every box measures zero, so take
measurements inside `measure(element, take)`, which runs `take` once the element has a
box. After a view swap that rearranges a widget's contents without resizing it, call
`layoutChanged(element)`, which dispatches `lf-layout` to the widgets and runtime readers
that measure what they hold, so they read again.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

On a plain host, load `/vendor/webawesome.esm.js` to upgrade a search field's editor.
