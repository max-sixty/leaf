# Generated controls

Read with [module-authoring.md](module-authoring.md).

Build each control the widget injects, and each box of controls, with the control
constructors in the library's
[`controls.js`](../../../browser/runtime/lib/controls.js), whose header lists them.
Each builds the native element, so the browser keeps its activation, focus and
accessibility. Each also marks the element as Leaf-generated, which tells Leaf the
widget's apparatus from the author's words. A native control the module draws without
them still works, in the theme's look for its element, and its words read as the
page's. A press that looks like Leaf's own controls is built by its role, so
every control of one kind wears one face, and a press that shows a symbol names its
action (`module-reading.md`, "Icons"). A box whose presses join into one control, as
a toolbar's marks do, declares `data-lf-joined`, and states as `--lf-joined-r` the
rounding its first and last press take at the corners they share with the box. Use a symbol where a standard symbol for the
action exists, one readers know from other software, and words where none does. A
class of the widget's places the control; don't restyle its face. A box resizes the
symbol presses it holds by setting `--lf-icon-action-face`, the size of their face.
Where its own rules read such a press's width, `--lf-icon-action-hit`, which is the
face or the aim floor, the box states that width again from the face it set. Shared control styles (`page-layout.md`, "Page CSS and Leaf's
controls") apply to generated controls too.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so the library builds it as a focusable span with the control's role
rather than as a form control. With a button's role, Enter and Space press it, with
Leaf or without; for another role, such as a tab's, the widget declares its keys.
Printing drops every generated control, so build structure that isn't injected UI as
ordinary elements, which the library's
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

## Faces for a widget's parts

A press takes its face from its role. A module gives the other parts it draws one of
Leaf's faces by writing one of these classes, and the widget's sheet may select the
class to place the part. Any other `lf-` class Leaf draws with is Leaf's own and can
change in any update.

| Class             | The module writes it on                                     | It gives                                                                                 |
| ----------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `lf-ui`           | a box of controls built without the library's constructors  | the mark they write: the box's words are apparatus (`module-plain-elements.md`)          |
| `lf-label`        | a region's name                                             | the label font, in small capitals                                                        |
| `lf-label-hidden` | a Web Awesome form control                                  | a label that a screen reader says and the screen doesn't show                            |
| `lf-choice`       | a label holding a radio or checkbox                         | a choice's face, its mark and words one target, padded by `--lf-choice-pad` on each side |
| `lf-key-badge`    | a command's `bindingBadge` (`module-input.md`)              | a key's face, in a box `--lf-key-badge-size` high                                        |
| `lf-action-icon`  | a symbol drawn in a press with the library's icon templates | a symbol that passes the pointer to its press                                            |
| `lf-media-frame`  | a box that frames a picture                                 | the ring and lift a picture in markup wears                                              |
| `lf-error`        | a box that says a part of the widget failed                 | the face of the box the library's `failure.js` shows                                     |
| `lf-rows`         | a list whose rows are presses built in the `row` role       | one set of columns for every row                                                         |
| `lf-row-lead`     | a row's mark: a dot, a symbol, a number or a time           | the first column, muted                                                                  |
| `lf-row-main`     | a row's name                                                | the column that takes the width the others leave                                         |
| `lf-row-end`      | a row's status, time, key or arrow                          | the last column, muted, in the small font                                                |
| `lf-rows-head`    | the heading of a group of rows                              | the group heading's font                                                                 |
| `lf-rows-empty`   | the line a list shows while it has no rows                  | a muted line where the first row would stand                                             |

Every widget with a time axis draws it the same way, with the ticks the library's
[`time-axis.js`](../../../browser/runtime/lib/time-axis.js) works out. The axis is a
box as wide as the times it spans. Its ruler has the class `lf-axis-ruler` and holds
an `lf-axis-tick` at each tick's time. A layer over the drawing below the ruler,
`lf-axis-grid`, holds an `lf-axis-gridline` at each major tick. A mark, label or
playhead the widget places on the axis has the class `lf-on-axis`. Each tick, gridline
and `lf-on-axis` element states its time as `--lf-axis-at`, a fraction of the axis from
0 to 1, and Leaf stands it there, inside the margin the axis box states as
`--lf-axis-edge`. Leaf states the element's distance from the box's start as
`--lf-axis-x`, which a rule reads to fit a label to the room on either side of it.
