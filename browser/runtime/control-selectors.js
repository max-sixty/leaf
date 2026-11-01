/* The selectors that distinguish controls from informational text.

   These platform and Leaf field declarations have one home for gesture routing,
   focus traversal and layout evidence. Informational ARIA groups and live regions do not
   imply a control. The prepaint owns the text-field vocabulary because early key
   holding needs it before modules load; this module exposes it with the other
   control selectors and installs no behavior. */

// The runtime's text field (`composing/text-field.js`): every box the runtime builds
// for the user to write in is one. Code that looks for such a box names it by this, and
// code asking whether something takes typed paragraphs asks `TEXT_BOX`, since a native
// textarea on an author's page still does. One spelling of each lets the field's
// element change without a lookup somewhere silently finding nothing.
export const TEXT_FIELD = window.lfInputs.textField;

// The same modifiers as the platform's own keydowns: what `ev.key` says when a modifier
// goes down alone, ahead of the key it modifies. The dispatcher's sequence asks this to tell
// half a press from a key of its own, and a label press keeps its hold through one.
export const MODIFIER_KEYS = ["Shift", "Alt", "Control", "Meta"];
// The keys that move a caret through text, and with Shift extend the selection from it:
// what a text box keeps from its ancestors' bindings, and what tells a reader of the
// caret or the selection that the keyboard has moved it.
export const CARET_KEYS = [
  "ArrowLeft",
  "ArrowRight",
  "ArrowUp",
  "ArrowDown",
  "Home",
  "End",
  "PageUp",
  "PageDown",
];
// Select All under either platform's modifier. With Shift also held the key reads "A".
/** @param {KeyboardEvent} event */
export const selectsAll = (event) =>
  event.key.toLowerCase() === "a" && (event.metaKey || event.ctrlKey);
export const TEXT_BOX = window.lfInputs.textBox;

// What the platform puts in the tab order without being asked, which is what a layout
// keeps clear of and what "does this box already hold a stop" asks about. A disclosure's
// `summary` is one, and so is an editable region.
export const TAB_STOP = `a[href], button, input, select, ${TEXT_BOX}, summary, [contenteditable]:not([contenteditable="false"]), [tabindex]:not([tabindex="-1"])`;

// What a page's own markup works: a link to follow, a control to set, a disclosure to
// open, a player to start. Browser-native interactive content, the ARIA widget roles,
// and the platform's explicit focus/edit/drag markers are one boundary shared by every
// gesture owner. `summary` stands for `details`, because only the summary is the press and
// the body under it is prose the user may point at like any other. Nothing embedded
// (`iframe`, `embed`, `object`): a click inside one never crosses into this document, so
// listing them would guard a gesture no listener out here can see.
// Two kinds, read apart where the question is whether a picture is a control's
// rendering. A press is one control whose whole box is the gesture: what it holds, an
// icon or a thumbnail, is how the control looks. A region is somewhere a gesture can
// land that holds content of its own: a tab stop focus rests on, a composite widget
// whose items are the presses, an editing surface, a drag source.
const PRESS_SELECTORS = [
  "a[href]",
  "audio[controls]",
  "button",
  "img[usemap]",
  "input:not([type='hidden'])",
  "label",
  "select",
  "summary",
  TEXT_BOX,
  "video[controls]",
  // A recording whose browser controls the runtime has traded for its own
  // (video-controls.js).
  "video[data-lf-player]",
  "[role='button']",
  "[role='checkbox']",
  "[role='combobox']",
  "[role='link']",
  "[role='menuitem']",
  "[role='menuitemcheckbox']",
  "[role='menuitemradio']",
  "[role='option']",
  "[role='radio']",
  "[role='scrollbar']",
  "[role='searchbox']",
  "[role='separator'][tabindex]",
  "[role='slider']",
  "[role='spinbutton']",
  "[role='switch']",
  "[role='tab']",
  "[role='textbox']",
  "[role='treeitem']",
];
// Reach lends a mechanical tab stop to overflowing prose. That stop does not
// turn its content into an authored interactive region.
export const LENT_REACH_STOP = "data-lf-lent-reach-stop";
const REGION_SELECTORS = [
  // A tab panel's stop lets the reader reach and scroll its contents; the panel
  // itself has no press to protect from a thread mark inside those contents.
  `[tabindex]:not([tabindex='-1']):not([${LENT_REACH_STOP}]):not([role='tabpanel'])`,
  "[contenteditable]:not([contenteditable='false'])",
  "[draggable='true']",
  "[role='application']",
  "[role='grid']",
  "[role='gridcell']",
  "[role='listbox']",
  "[role='menu']",
  "[role='menubar']",
  "[role='radiogroup']",
  "[role='tablist']",
  "[role='tree']",
  "[role='treegrid']",
];
export const PRESSES = PRESS_SELECTORS.join(",");
export const WORKS = [...PRESS_SELECTORS, ...REGION_SELECTORS].join(",");
