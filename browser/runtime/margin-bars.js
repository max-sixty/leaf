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

   A change with blocks puts the keys on its first block (change-walk.js), but a gap
   holds no element to stand on, and the block beside it is unchanged, so each gap has a
   stand-in (control-faces.js, `proxy`) on the details shelf, named by what the change
   did, whose press opens the change's card as its entry's does. The walk lands on it
   (`removalProxy`), and the user's place while on it is the element the gap stands by
   (details-shelf.js). Its focus opens what folds the gap away, brings the gap into view
   and rings it, as a block's focus rings the block, rather than that element, which
   didn't change and may be a `details` the gap stands outside.

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
  changeSince,
  closeChangeCard,
  comparisonChanges,
  gapHolder,
  openedChange,
  toggleChangeCard,
} from "./version.js";
import { paintSet } from "./target-paint-geometry.js";
import { el, offerAction, reveal } from "./widget-elements.js";
import { shelve, unshelve } from "./details-shelf.js";
import { onCurrentLocation } from "./focus.js";
import { scrollIntoView } from "./landing-scroll.js";
import { scrollContainer } from "./geometry.js";
import { scrollBehavior } from "./motion.js";
import { retainUserIntent } from "./user-intent.js";
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
// the card's words stand in from its edge. A gap's outline stands round the gap alone.
const OUTLINE = { x: 12, y: 6 };
const CARD_INSET = 13;

/** What the chrome mounts: the stands the bars stand in. */
export const marginBarLayer = el("div", "lf-ui lf-margin-bars");

const outlined = signal(/** @type {Change | null} */ (null));
// Each gap's stand-in, by its change, and the change each stands in for.
/** @type {Map<Change, HTMLElement>} */
const proxies = new Map();
/** @type {WeakMap<Element, Change>} */
const proxied = new WeakMap();
/** Where the keys stand for a change that only took blocks out: its gap's stand-in.
 * @param {Change} change */
export const removalProxy = (change) => proxies.get(change) ?? null;
/** Outline the change the user points at, or nothing.
 * @param {Change | null} change */
export function outlineChange(change) {
  outlined.value = change;
}

// Where a bar stands: `gap` from the start edge of the target's column, which is its
// right in right-to-left text, and a table's edge for a cell, so the bar stands in the
// margin rather than in the cell before it. A target with no room before it, such as a
// site header standing at the window's edge beside `main`, keeps its bar inside the
// window, over its own edge.
/** @param {Element} target @param {Box} rect @param {number} gap */
function barLeft(target, rect, gap) {
  const edge = (target.closest("table") ?? target).getBoundingClientRect();
  return target.matches(":dir(rtl)")
    ? Math.min(
        Math.max(rect.right, edge.right) + gap,
        document.documentElement.clientWidth - BAR,
      )
    : Math.max(Math.min(rect.left, edge.left) - gap - BAR, 0);
}
// The gap a change that only took blocks out stands in: from the element it stands by to
// the nearest box across the gap, the next shown sibling, else its parent's own edge
// where the parent leaves room, as at the foot of a `details`, else the parent's own
// sibling and so up; no further than a bar's length from a parent's edge. A gap in an
// element is that element's box.
/** @param {Change} change @param {Box} rect */
function gapOf({ at, gap }, rect) {
  if (gap === "in")
    return { top: rect.top, bottom: Math.max(rect.bottom, rect.top + GAP_BAR.min) };
  const after = gap === "after";
  const reach = after ? rect.bottom + GAP_BAR.max : rect.top - GAP_BAR.max;
  const across = (/** @type {number} */ edge) =>
    after ? edge > rect.bottom : edge < rect.top;
  let far = reach;
  for (let box = at; box.parentElement && box !== document.body;) {
    let sibling = after ? box.nextElementSibling : box.previousElementSibling;
    while (sibling && !sibling.getClientRects().length)
      sibling = after ? sibling.nextElementSibling : sibling.previousElementSibling;
    if (sibling) {
      const edge = sibling.getBoundingClientRect()[after ? "top" : "bottom"];
      if (across(edge)) far = edge;
      break;
    }
    box = box.parentElement;
    const own = box.getBoundingClientRect()[after ? "bottom" : "top"];
    if (across(own)) {
      far = after ? Math.min(own, reach) : Math.max(own, reach);
      break;
    }
  }
  return after ? { top: rect.bottom, bottom: far } : { top: far, bottom: rect.top };
}
// Where a scroll finds a gap: from the last words before it to the first after it, so
// the gap shows with a line either side, and within the scroller holding it, so that
// scroller is the one that moves; or the element a gap is in.
/** @param {Change} change @returns {Element | Range} */
function gapRange(change) {
  const { at, gap } = change;
  if (gap === "in") return at;
  let within = gapHolder(change);
  while (within !== document.body && !scrollContainer(within) && within.parentElement)
    within = within.parentElement;
  const words = document.createTreeWalker(within, NodeFilter.SHOW_TEXT, {
    acceptNode: (node) =>
      /\S/.test(node.nodeValue ?? "")
        ? NodeFilter.FILTER_ACCEPT
        : NodeFilter.FILTER_SKIP,
  });
  // Where the gap meets `at`: `at` itself for a gap before it, and its last descendant
  // for a gap after it, from which the words either side are found.
  let edge = /** @type {Node} */ (at);
  if (gap === "after") while (edge.lastChild) edge = edge.lastChild;
  words.currentNode = edge;
  const before =
    gap === "after" && edge instanceof Text && /\S/.test(edge.data)
      ? edge
      : words.previousNode();
  words.currentNode = edge;
  const after = words.nextNode();
  const range = document.createRange();
  if (before instanceof Text) range.setStart(before, before.length);
  else range.setStartBefore(at);
  if (after instanceof Text) range.setEnd(after, 0);
  else range.setEndAfter(at);
  return range;
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
    line.dataset.lfKind = block.kind;
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
  const ring = el("span", "lf-change-outline lf-change-ring");
  /** @type {{change: Change, node: HTMLElement} | null} */
  let card = null;
  /** @type {Change | null} */
  let pointed = null;
  // The change whose gap's stand-in holds focus.
  /** @type {Change | null} */
  let ringed = null;
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
    // The ring gives way to its change's card, as the outline does (margin-projection.js).
    /** @type {[Change | null, HTMLElement][]} */
    const rounds = [
      [pointed, outline],
      [ringed === card?.change ? null : ringed, ring],
    ];
    const round = rounds.flatMap(([reach, node]) =>
      reach
        ? [
            {
              node,
              target: reach.at,
              rect: (/** @type {Placement} */ { rect }) => {
                const box = extentOf(reach, rect);
                // A gap's outline keeps to the gap, clear of the words on either side.
                const y = reach.blocks.length ? OUTLINE.y : 0;
                return {
                  left: box.left - OUTLINE.x,
                  right: box.right + OUTLINE.x,
                  top: box.top - y,
                  bottom: box.bottom + y,
                };
              },
            },
          ]
        : [],
    );
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
    if (ringed) targets.add(ringed.at);
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
        keeps(node, "data-lf-for", target.id || null);
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
        const proxy = proxies.get(change);
        if (proxy) unshelve(change.at, proxy);
        proxies.delete(change);
        changed = true;
      }
    for (const change of empty)
      if (!gaps.has(change)) {
        const node = el("span", "lf-change-bar");
        keeps(node, "data-lf-for", change.at.id || null);
        node.dataset.lfGap = change.gap ?? "";
        gaps.set(change, node);
        const proxy = offerAction("proxy", "lf-change-gap", changeSince(change));
        proxy.tabIndex = -1;
        keeps(proxy, "aria-controls", CHANGE_CARD);
        keeps(proxy, "aria-expanded", "false");
        proxy.addEventListener("click", () => toggleChangeCard(change));
        shelve(change.at, proxy, () => null, { presents: false });
        proxies.set(change, proxy);
        proxied.set(proxy, change);
        changed = true;
      }
    if (changed) redraw();
  });
  // Focus on a gap's stand-in opens what folds the gap away, brings the gap into view
  // and rings it.
  onCurrentLocation((node) => {
    const change = (node && proxied.get(node)) ?? null;
    if (change) {
      reveal(gapHolder(change), retainUserIntent());
      scrollIntoView(gapRange(change), {
        behavior: scrollBehavior(),
        block: "nearest",
      });
    }
    if (change === ringed) return;
    ringed = change;
    redraw();
  });
  effect(() => {
    pointed = outlined.value;
    redraw();
  });
  effect(() => {
    const change = openedChange();
    for (const [each, proxy] of proxies)
      keeps(proxy, "aria-expanded", String(each === change));
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
