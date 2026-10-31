/* The layer's icons: one table of 16px strokes, the actions that show them, and a
   plain DOM drawing of one. It imports nothing, so delivery templates and browser
   renderers share the same symbols; icons.js adds their Lit templates. */

// Built-in margin entry faces use one stroked, currentColor icon vocabulary. Reaction tokens
// are authored content and may supply emoji; structural Leaf faces keep their line
// weight and baseline stable across systems.
const SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';

const ICONS = {
  activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
  add: '<path d="M8 3v10M3 8h10"/>',
  change:
    '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
  check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
  // A task app's ticked circle, for the to-do the user ends: a bare check is Resolve's,
  // and a to-do on a thread stands under its thread's Resolve.
  checked: '<circle cx="8" cy="8" r="5.5"/><path d="m5.6 8.15 1.7 1.7 3.1-3.3"/>',
  comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
  // The common copy glyph: the front sheet at the bottom right. Mirrored, with the front
  // sheet at the bottom left, two squares read as a window's Restore button.
  copy: '<rect x="6" y="6" width="7" height="7" rx="1.25"/><path d="M10 6V4.25C10 3.56 9.44 3 8.75 3h-4.5C3.56 3 3 3.56 3 4.25v4.5C3 9.44 3.56 10 4.25 10H6"/>',
  cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
  dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  down: '<path d="m4 6.25 4 4 4-4"/>',
  edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
  expand: '<path d="M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75"/>',
  collapse:
    '<path d="M13 3 9.25 6.75M9.25 3.25v3.5h3.5M3 13l3.75-3.75M3.25 9.25h3.5v3.5"/>',
  fit: '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
  fold: '<path d="M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5"/>',
  more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
  // What waits on the user, an inbox's tray: the On me mark. The question mark stays
  // with an obligation and with help (`?`).
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
  // The arc an editor's Undo draws, bending back to a corner head, as Material's and
  // Lucide's undo do. Rejected: a left arrow whose tail turns down, which is Lucide's
  // and VS Code's reply and reads as Reply beside a message.
  undo: '<path d="M2.5 4.75v3.75h3.75M13.5 11a5.5 5.5 0 0 0-5.5-5.5 5.5 5.5 0 0 0-3.75 1.45L2.5 8.5"/>',
  up: '<path d="m4 9.75 4-4 4 4"/>',
  waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>',
};

const SVG = "http://www.w3.org/2000/svg";

export const iconMarkup = (icon) => {
  const markup = ICONS[icon];
  if (!markup) throw new TypeError(`Unknown Leaf icon: ${icon}`);
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
// Leaf offers it (browser/AGENTS.md, "Visual grammar"). A press names its action and
// never an icon, so one action can't show two symbols. Two actions may share one
// symbol, as Undo and Discard share the undo arc, and a press may say more than the
// action's name, as "Retry source inspection" does. The icons above that no action
// names mark a kind or a state, not a press.
//
// Discard throws an editor's unsaved words away, so it wears Undo's arc rather than
// Close's ✕, which keeps them: closing a card leaves an open rewrite's words in its
// draft, and a draft's other ways out save. A rewrite's Discard also stood two seats
// from its card's Close. A reaction's removal took undo over ✕ for the same reading
// (the user's choice, 23 October 2026, anchor-controls.js).
export const ACTIONS = {
  accept: { name: "Accept", icon: "check" },
  add: { name: "Add", icon: "add" },
  arrange: { name: "Arrange", icon: "arrange" },
  cancel: { name: "Cancel", icon: "cross" },
  close: { name: "Close", icon: "cross" },
  collapse: { name: "Collapse", icon: "collapse" },
  comment: { name: "Comment", icon: "comment" },
  copy: { name: "Copy", icon: "copy" },
  "copy-link": { name: "Copy link", icon: "link" },
  dictate: { name: "Dictate", icon: "microphone" },
  discard: { name: "Discard", icon: "undo" },
  done: { name: "Done", icon: "checked" },
  edit: { name: "Edit", icon: "edit" },
  expand: { name: "Expand", icon: "expand" },
  find: { name: "Find", icon: "search" },
  "collapse-all": { name: "Collapse all", icon: "fold" },
  "expand-all": { name: "Expand all", icon: "unfold" },
  fit: { name: "Fit", icon: "fit" },
  minimize: { name: "Minimize", icon: "subtract" },
  more: { name: "More options", icon: "more" },
  next: { name: "Next", icon: "next" },
  // A find bar's steps run up and down its matches, as a browser's do.
  "next-match": { name: "Next match", icon: "down" },
  "on-me": { name: "On me", icon: "inbox" },
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

/** The symbol `action` shows. */
export const actionIcon = (action) => {
  const named = ACTIONS[action];
  if (!named) throw new TypeError(`Unknown Leaf action: ${action}`);
  return named.icon;
};

/** The name `action` says as its press's tooltip and accessible name. */
export const actionName = (action) => {
  actionIcon(action);
  return ACTIONS[action].name;
};

/** The element that draws `action`'s symbol. */
export const actionElement = (action, className) =>
  iconElement(actionIcon(action), className);

const SYMBOLIC = new Set(["symbol", "mark"]);

// The name a control of `role` says. A symbol or mark shows its action's symbol and
// says its name unless `label` says more. Whether a page's own press is a word or a
// symbol stays its author's call, so a page's "Done" may stay a word.
function actionFace(role, label, action) {
  if (!SYMBOLIC.has(role)) {
    if (action !== undefined)
      throw new TypeError(`A ${role} says its label and shows no action's symbol`);
    return label;
  }
  if (action === undefined) throw new TypeError(`A ${role} names the action it shows`);
  const name = actionName(action);
  return label ?? name;
}

/**
 * Draws `action`'s symbol as `control`'s first child, and leaves one that already
 * shows it, so a template's later renders write nothing and a control whose action
 * follows its state, as Expand all turns to Collapse all, swaps only the symbol.
 * @param {Element} control @param {string} action @param {string} [className]
 */
export function showAction(control, action, className = "lf-action-icon") {
  const icon = actionIcon(action);
  const drawn = control.querySelector(":scope > svg[data-lf-icon]");
  if (drawn?.getAttribute("data-lf-icon") === icon) return;
  const symbol = iconElement(icon, className);
  if (drawn) drawn.replaceWith(symbol);
  else control.prepend(symbol);
}

const drawAction = (node, role, action) =>
  showAction(node, action, role === "mark" ? "lf-mark-icon" : "lf-action-icon");

/**
 * The role constructors (`control-faces.js`, `ACTION_FACES`) with each symbol and mark
 * drawn from its action: `offerAction(role, className, label, {title, action})`, and
 * `offerActionElement(node, …)` for a template's element. The runtime builds its own
 * from these (widget-elements.js).
 * @param {{offerAction: (...args: any[]) => HTMLButtonElement; offerActionElement: <T extends Element>(node: T, ...args: any[]) => T}} base
 */
export function actionOffers(base) {
  const titled = (title) => (title === undefined ? undefined : { title });
  return {
    /**
     * @param {LeafActionRole} role @param {string} [className] @param {string} [label]
     * @param {{title?: string, action?: string}} [options]
     */
    offerAction(role, className, label, { title, action } = {}) {
      const node = base.offerAction(
        role,
        className,
        actionFace(role, label, action),
        titled(title),
      );
      if (SYMBOLIC.has(role)) drawAction(node, role, action);
      return node;
    },
    /**
     * @template {Element} T
     * @param {T} node @param {LeafActionRole} role @param {string} [className]
     * @param {string} [label] @param {{title?: string, action?: string}} [options]
     */
    offerActionElement(node, role, className, label, { title, action } = {}) {
      base.offerActionElement(
        node,
        role,
        className,
        actionFace(role, label, action),
        titled(title),
      );
      if (SYMBOLIC.has(role)) drawAction(node, role, action);
      return node;
    },
  };
}
