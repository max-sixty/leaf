/* The layer's icons: one table of 16px strokes, and the element that draws one. A base
   module: composing/selection.js builds its response button with an icon as it
   evaluates. */

// Built-in Button faces use one stroked, currentColor icon vocabulary. Reaction tokens
// are authored content and may supply emoji; structural Leaf faces keep their line
// weight and baseline stable across systems.
const SEND = '<path d="M2.75 3.25 13.25 8 2.75 12.75l1.2-4L9 8 3.95 7.25z"/>';

const ICONS = {
  activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
  add: '<path d="M8 3v10M3 8h10"/>',
  change:
    '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
  check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
  comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
  "compare-before":
    '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5a5.5 5.5 0 0 0 0 11Z" fill="currentColor" stroke="none"/>',
  "compare-after":
    '<circle cx="8" cy="8" r="5.5"/><path d="M8 2.5a5.5 5.5 0 0 1 0 11Z" fill="currentColor" stroke="none"/>',
  cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
  dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
  edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
  more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
  all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
  pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
  question:
    '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
  reaction:
    '<circle cx="6.5" cy="8.25" r="4.25"/><circle cx="5" cy="7.25" r=".55" fill="currentColor" stroke="none"/><circle cx="8" cy="7.25" r=".55" fill="currentColor" stroke="none"/><path d="M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4"/>',
  retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
  send: SEND,
  sent: SEND,
  undo: '<path d="M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1"/>',
  waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>',
};

export function iconElement(icon, className = "lf-margin-button-icon") {
  if (!ICONS[icon]) throw new TypeError(`Unknown Leaf icon: ${icon}`);
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("focusable", "false");
  svg.setAttribute("aria-hidden", "true");
  svg.classList.add(className);
  svg.dataset.lfIcon = icon;
  svg.innerHTML = ICONS[icon];
  return svg;
}
