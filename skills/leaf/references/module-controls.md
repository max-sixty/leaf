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
action (`module-reading.md`, "Icons"). Use a symbol where a standard symbol for the
action exists, one readers know from other software, and words where none does. A
class of the widget's places the control; don't restyle its face. Shared control styles (`page-layout.md`, "Page CSS and Leaf's
controls") apply to generated controls too.

A box resizes the symbol presses it holds by setting `--lf-icon-action-face`, the size
of their face. Where the box's own rules read such a press's width,
`--lf-icon-action-hit`, the larger of the face and the aim floor, the box states that
width again from the face it set. A box whose direct children are word, commit or mark
presses that join into one control, as a toolbar's marks do, declares `data-lf-joined`.
The first and last press are square unless the box states, as `--lf-joined-r`, the
rounding they take at the corners they share with it.

A control whose label is the page's own words, such as a tab's name, must stay
selectable, so the library builds it as a focusable span with the control's role
rather than as a form control. With a button's role, Enter and Space press it, with
Leaf or without; for another role, such as a tab's, the widget declares its keys.
Printing drops every generated control, so build structure that isn't injected UI as
ordinary elements, which the library's
[`elements.js`](../../../browser/runtime/lib/elements.js) makes in one call.

Words a module writes into the page are the page's words unless it marks them apart
(`module-widgets.md`, "Words it writes").

A widget can upgrade inside a shut panel where every box measures zero, so take a
measurement only once the element shows a box, which the library's
[`shown-box.js`](../../../browser/runtime/lib/shown-box.js) waits for. After a view swap
that rearranges a widget's contents without resizing it, dispatch an `lf-layout` event
on the element (`module-widgets.md`, "`lf-layout`"); a widget that measures
what it holds listens for the event and reads again.

`searchField(className, {name, label, placeholder})` builds a search or filter field
with Leaf's frame, label, editor and Clear button; the widget owns the query and
results, and can put a match count in its `end` slot.

On a plain host, load `/vendor/webawesome.esm.js` to upgrade a search field's editor.

## Faces for a widget's parts

A press takes its face from its role. A module gives the other parts it draws one of
Leaf's faces by writing one of these classes, and the widget's sheet may select the
class to place the part. A class of Leaf's that no reference names is Leaf's own and
can change in any update.

| Class              | The module writes it on                                                                    | It gives                                                                                                                                  |
| ------------------ | ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `.lf-ui`           | a box of apparatus the module builds itself                                                | words that are apparatus and take no comment; the library's constructors write it, with the marks that also keep a box off a printed page |
| `.lf-label`        | a region's name, in the document                                                           | the label font, in small capitals                                                                                                         |
| `.lf-label-hidden` | a Web Awesome form control                                                                 | a label that a screen reader says and the screen doesn't show                                                                             |
| `.lf-choice`       | a label that holds a radio or checkbox before its words                                    | a choice's face, its mark and words one target; a rule on the label reads its padding as `--lf-choice-pad`                                |
| `.lf-key-badge`    | a command's `bindingBadge` (`module-input.md`)                                             | a key's face, in a box `--lf-key-badge-size` high                                                                                         |
| `.lf-action-icon`  | a press's symbol, which `offerActionElement` draws from a Mount on the press the view drew | a symbol that passes the pointer to its press                                                                                             |
| `.lf-media-frame`  | a box that frames a picture                                                                | the ring and lift a picture in markup wears                                                                                               |
| `.lf-error`        | a box that says a part of the widget failed; the `lf-error` event draws none               | the face of the box the library's `failure.js` shows                                                                                      |
| `.lf-rows`         | a list whose rows are presses built in the `row` role                                      | one set of columns for every row                                                                                                          |
| `.lf-row-lead`     | a child of a row that marks it: a dot, a symbol, a number or a time                        | the first column, muted                                                                                                                   |
| `.lf-row-main`     | a child of a row that names it                                                             | the column that takes the width the others leave                                                                                          |
| `.lf-row-end`      | a child of a row that holds its status, time, key or arrow                                 | the last column, muted, in the small font                                                                                                 |
| `.lf-rows-head`    | the heading of a group of rows                                                             | the group heading's font                                                                                                                  |
| `.lf-rows-empty`   | the line a list shows while it has no rows                                                 | a muted line where the first row would stand                                                                                              |

## A time axis

A widget with a time axis uses `axisMarks`, from the library's
[`time-axis.js`](../../../browser/runtime/lib/time-axis.js), for the ruler ticks and
gridlines, as `lf-timeline` does. The widget draws its own marks, labels and playhead.
Each of them has the class `lf-on-axis` and states its time as `--lf-axis-at`, a
fraction of the axis from 0 to 1. Leaf stands the element at that time in the nearest
positioned box, which the widget makes as wide as the axis. The axis starts and ends a
margin inside that box, the library's `AXIS_EDGE` in pixels, and the widget states the
margin as `--lf-axis-edge` on a box that holds the whole drawing. Leaf also states the
element's distance from the start of its box as `--lf-axis-x`, a share of the box's
width, which a rule for the element reads in its own `max-inline-size` to fit a label to
the room on either side.
