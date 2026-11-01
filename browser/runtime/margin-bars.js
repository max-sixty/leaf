// @ts-check
/* Bars in the margin beside a block: where the agent is at work, and what changed since
   the version the page is compared with.

   The server says what the agent has in hand: each workflow at `working` or
   `replying` on an update the user handed over, and each to-do with a start running on
   it. The annotation inventory places that work on the page, where the update or to-do
   is about (a thread's passage, the widget a user's action was on, the element a to-do
   names), and says of each target whether the agent is at work there and not stalled
   (its entry's `atWork`: `progressFace` reads "working", or a to-do's start runs). This
   owner draws that reading as an accent bar beside the target, so "on it" reads as a
   place on the page, as a collaborator's cursor does. It claims no more than the server
   knows. The agent is at work on what the user said about this place, which is often a
   rewrite of it and sometimes only an answer; the bar says where the work is, not that
   the words beside it are changing. Work with no place on the page, such as a to-do on
   the whole page or a turn the agent spends on its own, draws nothing here and stays in
   the floating panel's status. The bar leaves once the work is answered or stalls.

   The version comparison (version.js, `comparisonChanges`) names the changes since its
   base, each a run of changed blocks, and this owner draws each block as a green bar
   beside it, nearer the block than the work's, so a block being reworked that has
   already changed shows both. A change's mark is an annotation, so hiding annotations
   (`o`) hides its bar. The bar marks the block, not its words: its change's Change entry
   opens which words went and came. The
   user chose the bar on 31 October over a wash of the block's own background, which hid
   whatever the block shades itself, an option's card and the chosen option's green among
   them, and over leaving the Change entry in the right margin as the only mark, which
   is hard to pick out at a glance. A widget names only which of its parts changed
   (its registry's `record`); how the change looks is this owner's, as it is for every
   annotation, so no widget describes its own.

   Each bar is paint over the page (target-paint-geometry.js, `paintSet`), standing in the
   planes that carry its target, so a scroll moves it without a write and the target's
   own borders, shadows and display are left as authored. A widget drawn through
   `display: contents` stands where its parts do, and a table cell's bar stands at its
   table's edge rather than in the cell before it. Layout, resize and a change in the
   target's size place it again. */
import { effect } from "/runtime/framework.js";
import { comparisonChanges } from "./version.js";
import { paintSet } from "./target-paint-geometry.js";
import { el } from "./widget-elements.js";
import { LAYOUT } from "./widget-upgrade.js";
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { keeps } from "./keeps.js";

// The bar's width, and each kind's gap from the target's start edge, in CSS pixels.
const BAR = 3;
const KINDS = /** @type {const} */ ({
  change: { gap: 4, className: "lf-change-bar" },
  work: { gap: 10, className: "lf-at-work-bar" },
});
/** @typedef {keyof typeof KINDS} Kind */

/** What the chrome mounts: the stands the bars stand in. */
export const marginBarLayer = el("div", "lf-ui lf-margin-bars");

/** @param {ReturnType<typeof import("./annotation-inventory.js").createAnnotationInventory>} inventory */
export function createMarginBars(inventory) {
  const bars = paintSet(marginBarLayer);
  /** @type {Record<Kind, Map<Element, HTMLElement>>} */
  const drawn = { change: new Map(), work: new Map() };
  const all = () =>
    /** @type {[Kind, Map<Element, HTMLElement>][]} */ (Object.entries(drawn)).flatMap(
      ([kind, targets]) =>
        [...targets].map(([target, node]) => ({ kind, target, node })),
    );
  let frame = 0;

  function place() {
    frame = 0;
    bars.place(
      all().map(({ kind, target, node }) => ({
        node,
        target,
        // Outside its target, so no scroller around the target cuts it; it hides with
        // its target's anchor instead.
        cut: false,
        // At the start edge of the target's column, which is its right in
        // right-to-left text: a table's edge for a cell, so the bar stands in the
        // margin rather than in the cell before it.
        rect: (
          /** @type {import("./target-paint-geometry.js").Placement} */ { rect },
        ) => {
          const { gap } = KINDS[kind];
          const edge = (target.closest("table") ?? target).getBoundingClientRect();
          const left = target.matches(":dir(rtl)")
            ? Math.max(rect.right, edge.right) + gap
            : Math.min(rect.left, edge.left) - gap - BAR;
          return { left, right: left + BAR, top: rect.top, bottom: rect.bottom };
        },
      })),
    );
  }
  const schedule = () => {
    if (!frame && all().length) frame = nextRender(place);
  };
  // A target whose size changes, as a revision rewording it does, is placed again.
  const sizes = sizeObserver(schedule, { counted: false });

  /** @param {Kind} kind @param {Set<Element>} places */
  function show(kind, places) {
    const targets = drawn[kind];
    let changed = false;
    for (const target of targets.keys())
      if (!places.has(target)) {
        targets.delete(target);
        if (!all().some((bar) => bar.target === target)) sizes.unobserve(target);
        changed = true;
      }
    for (const target of places)
      if (!targets.has(target)) {
        const node = el("span", KINDS[kind].className);
        keeps(node, "data-for", target.id || null);
        targets.set(target, node);
        sizes.observe(target);
        changed = true;
      }
    if (!changed) return;
    if (all().length) schedule();
    else {
      cancelRender(frame);
      frame = 0;
      bars.clear();
    }
  }

  inventory.watch((entries) => {
    /** @type {Set<Element>} */
    const places = new Set();
    for (const entry of entries) {
      const target = entry.atWork ? inventory.targetFor(entry) : null;
      if (target?.isConnected) places.add(target);
    }
    show("work", places);
  });
  effect(() => show("change", new Set(comparisonChanges().flat())));
  document.addEventListener(LAYOUT, schedule);
  addEventListener("resize", schedule, { passive: true });
}
