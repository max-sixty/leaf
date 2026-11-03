// @ts-check
/* Bars in the margin beside a block: where the agent is at work, and what changed since
   the version the page is compared with; and the comparison's other paint, the outline
   round the change the user points at and the open change's card.

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
   base, each a hunk of the block diff, and this owner draws each changed block as a green
   bar beside it, nearer the block than the work's, so a block being reworked that has
   already changed shows both. A change that only took blocks out has no block to stand
   beside, and its bar is the same bar at zero blocks' length: a short one in the gap the
   blocks left, which the user asked for on 3 November so that nothing breaks where a
   change's new side reaches zero. A change's mark is an annotation, so hiding
   annotations (`o`) hides its bar. The bar marks the block, not its words: its change's
   Change entry opens which words went and came. The user chose the bar on 31 October
   over a wash of the block's own background, which hid whatever the block shades
   itself, an option's card and the chosen option's green among them, and over leaving
   the Change entry in the right margin as the only mark, which is hard to pick out at a
   glance. A widget names only which of its parts changed (its registry's `record`); how
   the change looks is this owner's, as it is for every annotation, so no widget
   describes its own.

   The change the user points at with its Change entry, under the pointer or focus
   (margin-projection.js, `refreshHighlight`), stands in one outline round all its blocks
   or its gap (`outlineChange`), which says how far the change reaches before the press.
   The open change's card (version.js, `changeRedline`) stands over the change, the
   width of its blocks, and reads the change in order: what it took out struck, the words
   a block that kept its id lost and gained, and a new block as inserted. It covers what
   follows the change while it stands, and the page under it never moves; a redline
   longer than the window scrolls inside it. Escape or the entry's press again closes it.
   It is read, so assistive technology reaches it as the entry's disclosure, where the
   bars and the outline are empty boxes it passes over.

   Each box is paint over the page (target-paint-geometry.js, `paintSet`), standing in
   the planes that carry its target, so a scroll moves it without a write and the
   target's own borders, shadows and display are left as authored. A widget drawn
   through `display: contents` stands where its parts do, and a table cell's bar stands
   at its table's edge rather than in the cell before it. Layout, resize and a change in
   the target's size place it again. */
import { effect, signal } from "/runtime/framework.js";
import {
  CHANGE_CARD,
  changeRedline,
  closeChangeCard,
  comparisonChanges,
  openedChange,
} from "./version.js";
import { paintSet } from "./target-paint-geometry.js";
import { el } from "./widget-elements.js";
import { LAYOUT } from "./widget-upgrade.js";
import { cancelRender, nextRender, sizeObserver } from "./rendering.js";
import { keeps, layoutPx } from "./keeps.js";
import { pageRung } from "./keyboard/register.js";

/** @typedef {import("./version.js").Change} Change
 * @typedef {import("./target-paint-geometry.js").Placement} Placement
 * @typedef {{left: number, top: number, right: number, bottom: number}} Box */

// The bar's width, and each kind's gap from the target's start edge, in CSS pixels.
const BAR = 3;
const KINDS = /** @type {const} */ ({
  change: { gap: 4, className: "lf-change-bar" },
  work: { gap: 10, className: "lf-at-work-bar" },
});
/** @typedef {keyof typeof KINDS} Kind */
// A gap's bar is as tall as the gap it stands in, within these bounds, so it shows
// between blocks set close and stays a mark between blocks set far apart.
const GAP_BAR = { min: 8, max: 20 };
// How far the outline stands round a change's blocks, clear of their bars, and how far
// the card's words stand in from its edge.
const OUTLINE = { x: 12, y: 6 };
const CARD_INSET = 13;

/** What the chrome mounts: the stands the bars stand in. */
export const marginBarLayer = el("div", "lf-ui lf-margin-bars");

const outlined = signal(/** @type {Change | null} */ (null));
/** Outline the change the user points at, or nothing.
 * @param {Change | null} change */
export function outlineChange(change) {
  outlined.value = change;
}

// Where a bar stands: `gap` from the start edge of the target's column, which is its
// right in right-to-left text, and a table's edge for a cell, so the bar stands in the
// margin rather than in the cell before it.
/** @param {Element} target @param {Box} rect @param {number} gap */
function barLeft(target, rect, gap) {
  const edge = (target.closest("table") ?? target).getBoundingClientRect();
  return target.matches(":dir(rtl)")
    ? Math.max(rect.right, edge.right) + gap
    : Math.min(rect.left, edge.left) - gap - BAR;
}
// The gap a change that only took blocks out stands in: between the block it stands
// before and the one ahead of it, or after the page's last block.
/** @param {Change} change @param {Box} rect */
function gapOf({ at, after }, rect) {
  const other = (
    after ? at.nextElementSibling : at.previousElementSibling
  )?.getBoundingClientRect();
  return after
    ? {
        top: rect.bottom,
        bottom:
          other && other.top > rect.bottom ? other.top : rect.bottom + GAP_BAR.max,
      }
    : {
        top: other && other.bottom < rect.top ? other.bottom : rect.top - GAP_BAR.max,
        bottom: rect.top,
      };
}
// What a change covers on the page: its blocks' boxes together, or its gap the width of
// the block it stands by. `rect` is that block's, as its placement read it.
/** @param {Change} change @param {Box} rect @returns {Box} */
function extentOf(change, rect) {
  if (!change.blocks.length)
    return { left: rect.left, right: rect.right, ...gapOf(change, rect) };
  const boxes = [
    rect,
    ...change.blocks.slice(1).map((block) => block.getBoundingClientRect()),
  ].filter((box) => box.right > box.left || box.bottom > box.top);
  return {
    left: Math.min(...boxes.map((box) => box.left)),
    top: Math.min(...boxes.map((box) => box.top)),
    right: Math.max(...boxes.map((box) => box.right)),
    bottom: Math.max(...boxes.map((box) => box.bottom)),
  };
}

// The open change's card: a head saying what the change did between which versions,
// then one line a block.
/** @param {Change} change */
function cardFor(change) {
  const redline = changeRedline(change);
  if (!redline) return null;
  const card = el("div", "lf-ui lf-change-card");
  card.id = CHANGE_CARD;
  card.setAttribute("role", "group");
  card.setAttribute("aria-label", redline.account);
  card.append(
    el("p", "lf-change-card-head", `${redline.account} · ${redline.versions}`),
  );
  for (const block of redline.blocks) {
    const line = el("p", "lf-change-card-block");
    line.dataset.kind = block.kind;
    for (const run of block.runs)
      line.append(
        run.kind === "same"
          ? run.text
          : el(run.kind === "delete" ? "del" : "ins", "", run.text),
      );
    card.append(line);
  }
  return card;
}

/** @param {ReturnType<typeof import("./annotation-inventory.js").createAnnotationInventory>} inventory */
export function createMarginBars(inventory) {
  const bars = paintSet(marginBarLayer);
  /** @type {Record<Kind, Map<Element, HTMLElement>>} */
  const drawn = { change: new Map(), work: new Map() };
  // The gaps of the changes that only took blocks out, by the change.
  /** @type {Map<Change, HTMLElement>} */
  const gaps = new Map();
  const outline = el("span", "lf-change-outline");
  /** @type {{change: Change, node: HTMLElement} | null} */
  let card = null;
  /** @type {Change | null} */
  let pointed = null;
  let frame = 0;

  /** @returns {{node: HTMLElement, target: Element, rect: (placed: Placement) => Box | {left: number, top: number}}[]} */
  function items() {
    /** @param {Kind} kind */
    const barsOf = (kind) =>
      [...drawn[kind]].map(([target, node]) => ({
        node,
        target,
        rect: (/** @type {Placement} */ { rect }) => {
          const left = barLeft(target, rect, KINDS[kind].gap);
          return { left, right: left + BAR, top: rect.top, bottom: rect.bottom };
        },
      }));
    const gapBars = [...gaps].map(([change, node]) => ({
      node,
      target: change.at,
      rect: (/** @type {Placement} */ { rect }) => {
        const { top, bottom } = gapOf(change, rect);
        const tall = Math.min(Math.max(bottom - top, GAP_BAR.min), GAP_BAR.max);
        const middle = (top + bottom) / 2;
        const left = barLeft(change.at, rect, KINDS.change.gap);
        return {
          left,
          right: left + BAR,
          top: middle - tall / 2,
          bottom: middle + tall / 2,
        };
      },
    }));
    const reach = pointed;
    const round = reach
      ? [
          {
            node: outline,
            target: reach.at,
            rect: (/** @type {Placement} */ { rect }) => {
              const box = extentOf(reach, rect);
              return {
                left: box.left - OUTLINE.x,
                right: box.right + OUTLINE.x,
                top: box.top - OUTLINE.y,
                bottom: box.bottom + OUTLINE.y,
              };
            },
          },
        ]
      : [];
    const open = card;
    const over = open
      ? [
          {
            node: open.node,
            target: open.change.at,
            // A point: the card keeps the size its words give it, at its blocks' width,
            // over the change's blocks, or hung from its gap over what follows.
            rect: (/** @type {Placement} */ { rect }) => {
              const box = extentOf(open.change, rect);
              const top = open.change.blocks.length ? box.top - CARD_INSET : box.top;
              return { left: box.left - CARD_INSET, top };
            },
          },
        ]
      : [];
    return [...barsOf("work"), ...barsOf("change"), ...gapBars, ...round, ...over];
  }

  function place() {
    frame = 0;
    // The card's width is its blocks', read and written before the set reads its
    // boxes, so their reading meets no write.
    if (card) {
      const rect = card.change.at.getBoundingClientRect();
      const box = extentOf(card.change, rect);
      card.node.style.inlineSize = layoutPx(box.right - box.left + 2 * CARD_INSET);
    }
    // Outside its target, so no scroller around the target cuts it; it hides with its
    // target's anchor instead.
    bars.place(items().map((item) => ({ ...item, cut: false })));
  }
  const schedule = () => {
    if (!frame) frame = nextRender(place);
  };
  // A target whose size changes, as a revision rewording it does, is placed again.
  const sizes = sizeObserver(schedule, { counted: false });
  /** @type {Set<Element>} */
  let observed = new Set();
  // Every target the boxes read, watched for its size; and nothing drawn clears the set.
  function redraw() {
    const targets = new Set(items().flatMap(({ target }) => target));
    for (const target of card?.change.blocks ?? []) targets.add(target);
    for (const target of pointed?.blocks ?? []) targets.add(target);
    for (const target of observed) if (!targets.has(target)) sizes.unobserve(target);
    for (const target of targets) if (!observed.has(target)) sizes.observe(target);
    observed = targets;
    if (targets.size) schedule();
    else {
      cancelRender(frame);
      frame = 0;
      bars.clear();
    }
  }

  /** @param {Kind} kind @param {Set<Element>} places */
  function show(kind, places) {
    const targets = drawn[kind];
    let changed = false;
    for (const target of targets.keys())
      if (!places.has(target)) {
        targets.delete(target);
        changed = true;
      }
    for (const target of places)
      if (!targets.has(target)) {
        const node = el("span", KINDS[kind].className);
        keeps(node, "data-for", target.id || null);
        targets.set(target, node);
        changed = true;
      }
    if (changed) redraw();
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
  effect(() => {
    const changes = comparisonChanges();
    show("change", new Set(changes.flatMap((change) => change.blocks)));
    const empty = new Set(changes.filter((change) => !change.blocks.length));
    let changed = false;
    for (const change of gaps.keys())
      if (!empty.has(change)) {
        gaps.delete(change);
        changed = true;
      }
    for (const change of empty)
      if (!gaps.has(change)) {
        const node = el("span", "lf-change-bar");
        keeps(node, "data-for", change.at.id || null);
        node.dataset.gap = change.after ? "after" : "before";
        gaps.set(change, node);
        changed = true;
      }
    if (changed) redraw();
  });
  effect(() => {
    pointed = outlined.value;
    redraw();
  });
  effect(() => {
    const change = openedChange();
    if (card?.change === change) return;
    const node = change ? cardFor(change) : null;
    card = change && node ? { change, node } : null;
    redraw();
  });
  // The card is a step Escape takes back (keyboard/AGENTS.md, "Escape").
  pageRung("change card", () =>
    card ? { title: "close the change", out: closeChangeCard } : null,
  );
  document.addEventListener(LAYOUT, schedule);
  addEventListener("resize", schedule, { passive: true });
}
