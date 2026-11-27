/* A block Leaf bounds (`bound`, or data-bound on an occurrence, painted as
   data-lf-bound) holds its own height and scrolls inside it. The theme bounds the box;
   this module makes the box a reading region and keeps an `end` bound's place.

   Every bounded block is a registered reading region (`reading-regions.js`), so every
   question that names the box scrolling a node gets the block rather than the page:
   where a send lands its thread and which box holds a control still, where anchor
   travel reveals a passage, which margin lane clips a marker, and whose place
   continuity records and restores. A scroller page CSS makes is none of these: Leaf
   keeps no place in it, and `page check` advises bounding the block instead.

   A block names its own region (reading-regions.js, `regionId`): one of the page's own
   document with an id keeps its place across a revision, and any other keeps it while
   it stands.

   A block bounded at its end follows its newest entry: it opens at the end, and what
   arrives there stays in view while the user is at the end. A user who scrolls back
   stays where they stopped, since a log that pulls them down while they are reading an
   earlier line is a log they cannot read; returning to the end resumes following. The
   end keeper every box that follows its end shares does the following
   (dom/scrolling.js, `followEnd`); this module opens the box at its end once it is drawn. The
   place continuity records for a following block is its end (`followingItsEnd`), so a
   revision that restores places leaves it following rather than on the line that was
   at its top.

   The box that scrolls is the bounded element, unless its widget's theme moves the
   bound to a box inside it and names that box with a `--lf-bound-box` selector on
   the bounded element — a captured document scrolls its listing under a caption
   that stays put. The first matching box outside nested bounds is the region's body.

   A block is held while it stands in the page, whoever painted its bound: delivery
   paints a page's, and a revision patched in arrives painted the same way, while
   `markDeclared` paints a message's markup as the thread renders it. So one watch
   (`holdArrivingBounds` on dom/arrivals.js, started at boot) holds what the page opens
   with, every block added since in the document or a declared shadow root, and any
   element whose bound is painted or taken away in place, and lets go of a block that
   leaves. Each held block is then watched on its own, for what it holds, its size,
   and its own hidden state. What is registered is what stands in the page.

   A block in content the browser skips, a hidden tab's panel or a shut disclosure, is
   left as it stands until it is drawn (lib/shadow-tree.js, `skipped`). Finding its scroller
   reads the bounded element's style, and finding its end reads layout, and either
   question makes the browser style and lay out the hidden subtree first; Chromium has
   left style elsewhere on the page stale after that forced pass. A block first seen
   hidden stands as its own scroller meanwhile. Each skipped sync renews the block's
   size observation, whose first delivery comes once the block is drawn and asks again.
   A bound panel can keep the same box while its hidden attribute changes, so that
   change also asks again. A log that grew while hidden then opens on its newest entry.

   The watch starts before presentation because the first read it takes is the one the
   user sees: an `end` log opens at its end, and a pin taken after the page presents
   would show it at its top and then jump. */
import { skipped } from "../lib/shadow-tree.js";
import { sizeObserver } from "../lib/frame-pass.js";
import { followEnd, scrollToEnd } from "../dom/scrolling.js";
import { watchArrivals } from "../dom/arrivals.js";
import { regionId, registerReadingRegion } from "./reading-regions.js";
import { marks } from "../state/kernel-facts.js";
import type { EndKeeper } from "../dom/scrolling.js";

// The bound's attribute (`$marks`), read from the generated table rather than the registry,
// since the watch starts at boot, before any registry has loaded.
const BOUND = marks.bound.attribute;
const BOUNDED = `[${BOUND}]`;
const FOLLOWING = `[${BOUND}="end"]`;
type BoundHold = {
  bounded: Element;
  id: string;
  bound: string | null;
  box: Element | null;
  follow: EndKeeper | null;
  sync: () => void;
};

// Each block's hold, for the element's life, and the holds registered now.
const holds = new WeakMap<Element, BoundHold>();
const registered = new Set<BoundHold>();
const byBox = new WeakMap<Element, BoundHold>();

function scrollerOf(bounded: Element) {
  const selector = getComputedStyle(bounded).getPropertyValue("--lf-bound-box").trim();
  if (!selector) return bounded;
  // A bound nested inside this one owns its own scroller, so the search stops at it.
  for (const box of bounded.querySelectorAll(selector))
    if (box.closest(BOUNDED) === bounded) return box;
  return bounded;
}

const heldBy = (box: Element) => {
  const hold = byBox.get(box);
  return hold?.box === box && registered.has(hold) ? hold : null;
};

// Whether the box's bounded block follows its end and the user is there.
export const followingItsEnd = (box: Element) =>
  Boolean(heldBy(box)?.follow?.standsAtEnd());

// The bounded block a registered region body scrolls, or null for any other box.
export const boundedBlockOf = (box: Element) => heldBy(box)?.bounded ?? null;

function holdBlock(bounded: Element) {
  const hold: BoundHold = {
    bounded,
    id: regionId(bounded, "bound", bounded),
    bound: null,
    box: null,
    follow: null,
    sync: () => sync(false),
  };
  let stopRegion: (() => void) | null = null;
  const stopFollowing = () => {
    hold.follow?.stop();
    hold.follow = null;
  };
  const letGo = () => {
    stopFollowing();
    if (hold.box && hold.box !== bounded) resize.unobserve(hold.box);
    stopRegion?.();
    stopRegion = null;
    hold.box = null;
    registered.delete(hold);
  };
  const adopt = (box: Element) => {
    if (box === hold.box) return;
    letGo();
    resize.observe(box);
    byBox.set(box, hold);
    hold.box = box;
    stopRegion = registerReadingRegion({ id: hold.id, host: bounded, body: box });
    registered.add(hold);
  };
  // `observed` when the block's own size observer asks, which cannot take a fresh
  // observation of the block: the same delivery would never reach it (dom/reach.js).
  const sync = (observed: boolean) => {
    hold.bound = bounded.getAttribute(BOUND);
    if (!bounded.isConnected || hold.bound === null) return letGo();
    if (bounded.hasAttribute("hidden") || skipped(bounded)) {
      if (!hold.box) adopt(bounded);
      if (!observed) {
        resize.unobserve(bounded);
        resize.observe(bounded);
      }
      return;
    }
    const box = scrollerOf(bounded);
    adopt(box);
    if (!bounded.matches(FOLLOWING)) return stopFollowing();
    // What the log holds changed, or its size: the keeper reads it at once.
    if (hold.follow) return hold.follow.check();
    // A box under a `display: none` ancestor has no end to open at, so it opens once
    // drawn, when its size observation next asks.
    if (!box.checkVisibility()) return;
    scrollToEnd(box);
    hold.follow = followEnd(box);
  };
  const resize = sizeObserver(() => sync(true));
  resize.observe(bounded);
  new MutationObserver((records) => {
    if (
      records.some(
        (record) => record.type !== "attributes" || record.target === bounded,
      )
    )
      hold.sync();
  }).observe(bounded, {
    attributes: true,
    attributeFilter: ["hidden"],
    childList: true,
    characterData: true,
    subtree: true,
  });
  return hold;
}

// Hold every bounded block while it stands in the page (dom/arrivals.js); `sync` answers
// both ways, registering a block that stands and letting go of one that has left or lost
// its bound. What a registered block holds is its own observer's to follow, so a block
// offered again with its bound unchanged (its children or siblings moved) costs nothing.
export function holdArrivingBounds() {
  watchArrivals(BOUNDED, [BOUND], {
    arrive: (el) => {
      let hold = holds.get(el);
      if (!hold) {
        hold = holdBlock(el);
        holds.set(el, hold);
      }
      if (!registered.has(hold) || hold.bound !== el.getAttribute(BOUND)) hold.sync();
    },
    leave: (el) => holds.get(el)?.sync(),
  });
}
