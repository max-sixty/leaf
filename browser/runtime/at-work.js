// @ts-check
/* Where on the page the agent is at work.

   The server says what the agent has in hand: each workflow at `working` or
   `replying` on an update the user handed over, and each to-do with a start running on
   it. The annotation inventory places that work on the page, where the update or to-do
   is about (a thread's passage, the widget a user's action was on, the element a to-do
   names), and says of each target whether the agent is at work there and not stalled
   (its entry's `atWork`: `progressFace` reads "working", or a to-do's start runs). This
   owner draws that reading as a bar in the margin beside the target, so "on it" reads
   as a place on the page, as a collaborator's cursor does.

   It claims no more than the server knows. The agent is at work on what the user said
   about this place, which is often a rewrite of it and sometimes only an answer; the
   bar says where the work is, not that the words beside it are changing. Work with no
   place on the page, such as a to-do on the whole page or a turn the agent spends on
   its own, draws nothing here and stays in the floating panel's status. When the work
   lands as a revision, the blocks it changed take the install's tint (version.js), and
   the bar leaves once the work is answered or stalls.

   The bar is paint over the page (target-paint-geometry.js, `paintSet`), standing in the
   planes that carry its target, so a scroll moves it without a write and the target's
   own borders, shadows and display are left as authored. A widget drawn through
   `display: contents` stands where its parts do, and a table cell's bar stands at its
   table's edge rather than in the cell before it. Layout, resize and a change in the
   target's size place it again. */
import { paintSet } from "./target-paint-geometry.js";
import { el, LAYOUT } from "./widget-elements.js";
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { keeps } from "./keeps.js";

// The bar's width and its gap from the target's start edge, in CSS pixels.
const BAR = 3;
const GAP = 10;

/** What the chrome mounts: the stands the bars stand in. */
export const atWorkLayer = el("div", "lf-ui lf-at-work");

/** @param {{ watch: (watcher: (entries: readonly any[]) => void) => () => void, targetFor: (entry: any) => Element | null }} inventory */
export function createAtWork(inventory) {
  const bars = paintSet(atWorkLayer);
  /** @type {Map<Element, HTMLElement>} */
  const drawn = new Map();
  let frame = 0;

  function place() {
    frame = 0;
    bars.place(
      [...drawn].map(([target, node]) => ({
        node,
        target,
        // Outside its target, so no scroller around the target cuts it; it hides with
        // its target's anchor instead.
        cut: false,
        // At the start edge of the target's column, which is its right in
        // right-to-left text: a table's edge for a cell, so the bar stands in the
        // margin rather than in the cell before it.
        rect: (/** @type {{rect: DOMRectReadOnly}} */ { rect }) => {
          const edge = (target.closest("table") ?? target).getBoundingClientRect();
          const left = target.matches(":dir(rtl)")
            ? Math.max(rect.right, edge.right) + GAP
            : Math.min(rect.left, edge.left) - GAP - BAR;
          return { left, right: left + BAR, top: rect.top, bottom: rect.bottom };
        },
      })),
    );
  }
  const schedule = () => {
    if (drawn.size && !frame) frame = nextRender(place);
  };
  // A target whose size changes, as a revision rewording it does, is placed again.
  const sizes = sizeObserver(schedule, { counted: false });

  inventory.watch((entries) => {
    /** @type {Set<Element>} */
    const places = new Set();
    for (const entry of entries) {
      const target = entry.atWork ? inventory.targetFor(entry) : null;
      if (target?.isConnected) places.add(target);
    }
    let changed = false;
    for (const target of drawn.keys())
      if (!places.has(target)) {
        drawn.delete(target);
        sizes.unobserve(target);
        changed = true;
      }
    for (const target of places)
      if (!drawn.has(target)) {
        const node = el("span", "lf-at-work-bar");
        keeps(node, "data-for", target.id || null);
        drawn.set(target, node);
        sizes.observe(target);
        changed = true;
      }
    if (!changed) return;
    if (drawn.size) schedule();
    else {
      cancelRender(frame);
      frame = 0;
      bars.clear();
    }
  });
  document.addEventListener(LAYOUT, schedule);
  addEventListener("resize", schedule, { passive: true });
}
