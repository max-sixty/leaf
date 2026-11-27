// Compiled from keys.ts by build/typescript.mjs; edit that file.
/* The keys a control answers, read from the control: what activates a button, the
   press a control claims for itself, and the arrows that step back and ahead along a
   row of controls in its text direction. */

// What activates a focused button, stated once because it is the platform's fact and not
// any one row's. A link is the case that keeps this honest: Enter follows an <a> and
// Space scrolls the page, so a row over links names Enter alone. The shared fact is what
// a button answers, not what every control does.
export const PRESS = ["Enter", " "];

// Whether a press is the plain one a control or link claims for itself: the primary
// button with no modifier held. Every modifier asks the platform for something else —
// Cmd- or Ctrl-click opens a link elsewhere and Ctrl-click is the Mac's context menu,
// Shift extends a selection or opens a window, Alt downloads or aims at the item — so a
// handler that takes over a press leaves a modified one to the browser.
export const plainPress = (event) =>
  event.button === 0 &&
  !event.altKey &&
  !event.ctrlKey &&
  !event.metaKey &&
  !event.shiftKey;

// The arrows that step back and ahead along a row of controls, as `[back, ahead]`. Back
// is the side the row's words run from: left in left-to-right text and right in
// right-to-left text, where the first item stands at the right, as the ARIA tabs,
// toolbar and slider patterns ask. Read from the directionality of the node the row
// lays out in (`:dir()`), which the `dir` attributes around it decide, as the theme's
// direction rules read it; a `direction` set in CSS alone moves neither. Key
// availability asks this of every disclosure on the page, in the frame's pass after
// other work has written to the document, so reading the computed `direction` made it
// recalculate style for those writes, several times a comment on a page of diffs.
export const rowArrows = (node) =>
  node.matches(":dir(rtl)") ? ["ArrowRight", "ArrowLeft"] : ["ArrowLeft", "ArrowRight"];
