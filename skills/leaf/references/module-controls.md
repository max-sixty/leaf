# Generated controls

Read with [module-authoring.md](module-authoring.md), which holds what every behavior
module owes.

Build each control the widget injects, and each box of controls, with the library's
control constructors (`module-authoring.md`, "Shared web code"). Each builds the native
element, so the browser keeps its activation, focus and accessibility. Each also marks
the element as Leaf-generated, which tells Leaf the widget's apparatus from the
author's words. A press that looks like Leaf's own controls is built by its role, so
every control of one kind wears one face, and a press that shows a symbol names its
action (`module-reading.md`, "Icons"). Use a symbol where a standard symbol for the
action exists, one readers know from other software, and words where none does. A
class of the widget's places the control; don't restyle its face. Shared control styles (`page-layout.md`, "Page CSS and Leaf's
controls") apply to generated controls too.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so the library builds it as a focusable span with the control's role
rather than as a form control. With a button's role, Enter and Space press it, with
Leaf or without; for another role, such as a tab's, the widget declares its keys.
Printing drops every generated control, so build structure that isn't injected UI as
plain elements, which the library's
[`elements.js`](../../../browser/runtime/lib/elements.js) makes in one call.

Words a module writes into the page are the page's words unless it marks them apart
(`module-plain-elements.md`, "Words it writes").

A widget can upgrade inside a shut panel where every box measures zero, so take a
measurement only once the element shows a box, which the library's
[`shown-box.js`](../../../browser/runtime/lib/shown-box.js) waits for. After a view swap
that rearranges a widget's contents without resizing it, dispatch an `lf-layout` event
on the element (`module-plain-elements.md`, "`lf-layout`"); a widget that measures
what it holds listens for the event and reads again.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

On a plain host, load `/vendor/webawesome.esm.js` to upgrade a search field's editor.
