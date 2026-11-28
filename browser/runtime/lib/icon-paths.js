// Compiled from icon-paths.ts by build/typescript.mjs; edit that file.
/* Leaf's icons: one table of 16px strokes (`ICONS`, keyed by icon name), the actions
   that show them (`ACTIONS`, keyed by action name, each with its symbol and the words
   its press says), and a plain DOM drawing of one. It imports nothing, so a pure model
   such as the margin's names a symbol without loading Lit; icons.js adds their Lit
   templates. A press that shows a symbol names its action rather than an icon
   (`offerAction` and `nameAction`, controls.js), so each action looks the same
   wherever it is offered; an icon an action doesn't name marks what something is or
   holds, such as a kind or a state. */

// Built-in margin entry faces use one stroked, currentColor icon vocabulary. Reactions
// are authored content, each its emoji; structural Leaf faces keep their line
// weight and baseline stable across systems.
const SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';

const ICONS = {
  activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
  add: '<path d="M8 3v10M3 8h10"/>',
  change:
    '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
  check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
  comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
  // The common copy glyph: the front sheet at the bottom right. Mirrored, with the front
  // sheet at the bottom left, two squares read as a window's Restore button.
  copy: '<rect x="6" y="6" width="7" height="7" rx="1.25"/><path d="M10 6V4.25C10 3.56 9.44 3 8.75 3h-4.5C3.56 3 3 3.56 3 4.25v4.5C3 9.44 3.56 10 4.25 10H6"/>',
  cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
  // A bin with its lid: what a rewrite emptied of words does to its message.
  delete:
    '<path d="M3 4.5h10M6.25 4.5V3h3.5v1.5M4.5 4.5l.6 7.85c.05.65.6 1.15 1.25 1.15h3.3c.65 0 1.2-.5 1.25-1.15l.6-7.85M6.75 7v4M9.25 7v4"/>',
  dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  down: '<path d="m4 6.25 4 4 4-4"/>',
  edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
  expand: '<path d="M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75"/>',
  collapse:
    '<path d="M13 3 9.25 6.75M9.25 3.25v3.5h3.5M3 13l3.75-3.75M3.25 9.25h3.5v3.5"/>',
  fit: '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
  // Leaf's own mark, which a package may replace (`/icon.svg`): the square is filled
  // in the text's colour and the stylesheet masks it with the mark (chrome.css).
  leaf: '<rect width="16" height="16" fill="currentColor" stroke="none"/>',
  // A drag handle's six dots, the grip a reader knows from lists they reorder.
  grip: '<g fill="currentColor" stroke="none"><circle cx="6" cy="4" r="1.1"/><circle cx="10" cy="4" r="1.1"/><circle cx="6" cy="8" r="1.1"/><circle cx="10" cy="8" r="1.1"/><circle cx="6" cy="12" r="1.1"/><circle cx="10" cy="12" r="1.1"/></g>',
  fold: '<path d="M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5"/>',
  more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
  // What waits on the user, an inbox's tray: a tab's On Me mark. The question mark
  // stays with an obligation and with help (`?`).
  inbox:
    '<path d="M2.75 9.25h2.9l1 1.6h2.7l1-1.6h2.9M2.75 9.25 4.4 4h7.2l1.65 5.25v2.75H2.75z"/>',
  link: '<path d="M6.67 8.67a3.33 3.33 0 0 0 5.03.36l2-2a3.33 3.33 0 0 0-4.71-4.71l-1.15 1.14M9.33 7.33a3.33 3.33 0 0 0-5.03-.36l-2 2a3.33 3.33 0 0 0 4.71 4.71l1.14-1.14"/>',
  // A map's locate mark, for the way from a thread to where its words stand.
  locate:
    '<circle cx="8" cy="8" r="4"/><path d="M8 1.75v2.5M8 11.75v2.5M1.75 8h2.5M11.75 8h2.5"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/>',
  microphone:
    '<rect x="6" y="2" width="4" height="7" rx="2"/><path d="M4 7.5v.75a4 4 0 0 0 8 0V7.5M8 12.25V14M6 14h4"/><path class="lf-mic-slash" d="M2.5 2.5l11 11"/>',
  next: '<path d="m6 3.5 4.5 4.5L6 12.5"/>',
  pause: '<path d="M5 3v10M11 3v10"/>',
  play: '<path d="m5 3 7 5-7 5z"/>',
  previous: '<path d="m10 3.5-4.5 4.5 4.5 4.5"/>',
  // How a list is arranged: its lines, shortening, the choosers' symbol.
  arrange: '<path d="M3 4.5h10M3 8h7M3 11.5h4"/>',
  all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
  pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
  question:
    '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
  reaction:
    '<circle cx="6.5" cy="8.25" r="4.25"/><circle cx="5" cy="7.25" r=".55" fill="currentColor" stroke="none"/><circle cx="8" cy="7.25" r=".55" fill="currentColor" stroke="none"/><path d="M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4"/>',
  retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
  save: '<path d="M3 4.25A1.25 1.25 0 0 1 4.25 3h6.5L13 5.25v6.5A1.25 1.25 0 0 1 11.75 13h-7.5A1.25 1.25 0 0 1 3 11.75zM5.5 3v2.5h4V3"/>',
  search: '<circle cx="7" cy="7" r="3.75"/><path d="m10 10 3 3"/>',
  send: SEND,
  sent: SEND,
  start: '<path d="M3.5 3v10M12.5 3.5 6 8l6.5 4.5z"/>',
  subtract: '<path d="M3 8h10"/>',
  unfold: '<path d="M3 8h10M5.5 5.25 8 2.75l2.5 2.5M5.5 10.75 8 13.25l2.5-2.5"/>',
  // A U-turn back to the left, as Apple's and Lucide's undo draw it (the user's pick).
  // Rejected: a left arrow whose tail turns down, which is Lucide's
  // and VS Code's reply and reads as Reply beside a message; and the arc Material's
  // undo draws.
  undo: '<path d="M5.5 2.75 2.75 5.5l2.75 2.75M3 5.5h6.25a3.5 3.5 0 0 1 0 7H6.5"/>',
  up: '<path d="m4 9.75 4-4 4 4"/>',
  waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>',
};

const SVG = "http://www.w3.org/2000/svg";

export const iconMarkup = (icon) => {
  const markup = ICONS[icon];
  if (!markup)
    throw new TypeError(
      `Unknown Leaf icon: ${icon}. Leaf's icons are ${Object.keys(ICONS).sort().join(", ")}`,
    );
  return markup;
};

export function iconElement(icon, className = "lf-margin-entry-icon") {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", className);
  svg.dataset.lfIcon = icon;
  svg.innerHTML = iconMarkup(icon);
  return svg;
}

// Each action a press can show as a symbol, and the symbol and name it shows wherever
// Leaf offers it (browser/AGENTS.md, "Controls are few and quiet"). A press names its action and
// never an icon, so one action can't show two symbols. Two actions may share one
// symbol, as Undo and Discard share the U-turn, and a press may say more than the
// action's name, as "Retry source inspection" does. The icons above that no action
// names mark a kind or a state, not a press.
//
// Discard throws an editor's unsaved words away, so it wears Undo's U-turn rather than
// Close's ✕, which keeps them: closing a card leaves an open rewrite's words in its
// draft, and a draft's other ways out save.
export const ACTIONS = {
  accept: { name: "Accept", icon: "check" },
  add: { name: "Add", icon: "add" },
  arrange: { name: "Arrange", icon: "arrange" },
  back: { name: "Back", icon: "previous" },
  cancel: { name: "Cancel", icon: "cross" },
  close: { name: "Close", icon: "cross" },
  collapse: { name: "Collapse", icon: "collapse" },
  comment: { name: "Comment", icon: "comment" },
  copy: { name: "Copy", icon: "copy" },
  "copy-link": { name: "Copy link", icon: "link" },
  delete: { name: "Delete", icon: "delete" },
  dictate: { name: "Dictate", icon: "microphone" },
  discard: { name: "Discard", icon: "undo" },
  edit: { name: "Edit", icon: "edit" },
  expand: { name: "Expand", icon: "expand" },
  find: { name: "Find", icon: "search" },
  // A thread's jumps over its messages (records/thread/thread-card.js, `#jumps`).
  "first-message": { name: "Go to the first message", icon: "up" },
  "latest-message": { name: "Go to the latest message", icon: "down" },
  "collapse-all": { name: "Collapse all", icon: "fold" },
  "expand-all": { name: "Expand all", icon: "unfold" },
  fit: { name: "Fit", icon: "fit" },
  minimize: { name: "Minimize", icon: "subtract" },
  // The leaf: the page's menu, under Leaf's own mark in the page's status tone.
  menu: { name: "Page menu", icon: "leaf" },
  more: { name: "More options", icon: "more" },
  move: { name: "Move", icon: "grip" },
  next: { name: "Next", icon: "next" },
  // A find bar's steps run up and down its matches, as a browser's do.
  "next-match": { name: "Next match", icon: "down" },
  // The presses the floating panel's field offers at its end, a notice's or the page's
  // own (panel/floating-panel.js, `pressReading`), in the title case the user asked for.
  "next-on-me": { name: "Next On Me", icon: "inbox" },
  "next-thread": { name: "Next thread", icon: "next" },
  // A thread's way between Leaf's two places for it, its card beside the passage and the
  // floating panel (records/thread/threads-in-panel.js).
  "open-in-panel": { name: "Open in panel", icon: "expand" },
  "open-latest": { name: "Open latest", icon: "next" },
  "resume-writing": { name: "Resume writing", icon: "edit" },
  "show-annotations": { name: "Show annotations", icon: "locate" },
  "show-changes": { name: "Show changes", icon: "locate" },
  "show-on-page": { name: "Show on page", icon: "locate" },
  "on-me": { name: "On Me", icon: "inbox" },
  pause: { name: "Pause", icon: "pause" },
  play: { name: "Play", icon: "play" },
  previous: { name: "Previous", icon: "previous" },
  "previous-match": { name: "Previous match", icon: "up" },
  react: { name: "Add reaction", icon: "reaction" },
  remove: { name: "Remove", icon: "cross" },
  reject: { name: "Reject", icon: "cross" },
  reopen: { name: "Reopen", icon: "check" },
  reset: { name: "Reset", icon: "retry" },
  resolve: { name: "Resolve", icon: "check" },
  retry: { name: "Retry", icon: "retry" },
  save: { name: "Save", icon: "save" },
  send: { name: "Send", icon: "send" },
  show: { name: "Show", icon: "locate" },
  start: { name: "Start", icon: "start" },
  suggest: { name: "Suggest", icon: "edit" },
  undo: { name: "Undo", icon: "undo" },
  "zoom-in": { name: "Zoom in", icon: "add" },
  "zoom-out": { name: "Zoom out", icon: "subtract" },
};

const namedAction = (action) => {
  const named = ACTIONS[action];
  if (!named)
    throw new TypeError(
      `Unknown Leaf action: ${action}. Leaf's actions are ${Object.keys(ACTIONS).sort().join(", ")}`,
    );
  return named;
};
/** The symbol `action` shows. */
export const actionIcon = (action) => namedAction(action).icon;
/** The name `action` says as its press's tooltip and accessible name. */
export const actionName = (action) => namedAction(action).name;

/** The element that draws `action`'s symbol. */
export const actionElement = (action, className) =>
  iconElement(actionIcon(action), className);

/** Draws `action`'s symbol as `control`'s first child, and leaves one that already
 * shows it, so a template's later renders write nothing and a control whose action
 * follows its state, as Expand all turns to Collapse all, swaps only the symbol. */
export function showAction(control, action, className = "lf-action-icon") {
  const icon = actionIcon(action);
  const drawn = control.querySelector(":scope > svg[data-lf-icon]");
  if (drawn?.getAttribute("data-lf-icon") === icon) return;
  const symbol = iconElement(icon, className);
  if (drawn) drawn.replaceWith(symbol);
  else control.prepend(symbol);
}
