/* The reader's place in a scroller, and the band of it they can see.

   The folds (which candidate holds the place, how far a correction scrolls, what a cover
   takes off a band) are asked directly. The hold itself is asked once over boxes this
   file states, since happy-dom lays nothing out: a node the render replaced hands the
   place to the node now rendered under its identity. */

import assert from "node:assert/strict";
import test from "node:test";

import { insetBand, visibleBand } from "/runtime/geometry.js";
import {
  placeCandidates,
  placeCorrection,
  placeKeeper,
} from "/runtime/reader-place.js";

test("the place goes to the pointer, then focus, then the visible from the lead down", () => {
  const visible = ["a", "b", "c", "d"];
  assert.deepEqual(
    placeCandidates({ inherited: null, pointer: "c", focus: "a", visible }),
    ["c", "a", "d", "b"],
  );
  assert.deepEqual(
    placeCandidates({ inherited: null, pointer: null, focus: null, visible }),
    ["a", "b", "c", "d"],
  );
  // A fold in flight has already moved what the pointer names; its reference leads.
  assert.deepEqual(
    placeCandidates({ inherited: "b", pointer: "d", focus: null, visible }),
    ["b", "d", "c", "a"],
  );
  // Focus off-screen still leads, and is not repeated among the visible.
  assert.deepEqual(
    placeCandidates({ inherited: null, pointer: null, focus: "z", visible }),
    ["z", "a", "b", "c", "d"],
  );
});

test("a correction follows reflow and pays for a limit clamp only once", () => {
  const held = { scrollTop: 900, limit: 1200 };
  // Content above grew by 40: scroll down by 40.
  assert.equal(
    placeCorrection({ was: 1000, now: 1040, scrollTop: 900, limit: 1240, held }),
    40,
  );
  // Content shrank and the browser clamped the scroller from 900 to its new limit of
  // 700, carrying the reference 200 closer already.
  assert.equal(
    placeCorrection({ was: 1000, now: 700, scrollTop: 700, limit: 700, held }),
    -100,
  );
  // Standing short of the limit is the reader's own scroll, not a clamp.
  assert.equal(
    placeCorrection({ was: 1000, now: 1000, scrollTop: 650, limit: 700, held }),
    0,
  );
});

test("covers standing over a band's edges take their room off it", () => {
  const band = { left: 0, right: 300, top: 100, bottom: 500 };
  const box = (top, bottom, left = 0, right = 300) => ({ left, right, top, bottom });
  // A heading stuck over the top edge, drawn back 4px above it.
  assert.deepEqual(insetBand(band, [box(96, 130)]), { ...band, top: 130 });
  // A heading passing through the middle is content, not a cover.
  assert.deepEqual(insetBand(band, [box(200, 230)]), band);
  // One cover resting on another; and a footer over the bottom edge.
  assert.deepEqual(insetBand(band, [box(128, 150), box(96, 130), box(480, 510)]), {
    ...band,
    top: 150,
    bottom: 480,
  });
  // A cover beside the band covers nothing of it; covers taking all of it leave none.
  assert.deepEqual(insetBand(band, [box(96, 130, 400, 500)]), band);
  assert.equal(insetBand(band, [box(90, 510)]), null);
});

// A scroller whose boxes are stated: each node's viewport top is its content top less
// the scroller's scrollTop.
function laidOut() {
  const scroller = document.createElement("div");
  scroller.style.overflowY = "auto";
  document.body.append(scroller);
  let scrollTop = 0;
  Object.defineProperty(scroller, "scrollTop", {
    get: () => scrollTop,
    set: (value) => (scrollTop = value),
  });
  Object.defineProperties(scroller, {
    scrollHeight: { get: () => 5000 },
    clientHeight: { get: () => 400 },
    clientWidth: { get: () => 300 },
  });
  scroller.getBoundingClientRect = () => new DOMRect(0, 0, 300, 400);
  const at = new Map();
  const item = (id, contentTop) => {
    const node = document.createElement("section");
    node.className = "item";
    node.dataset.id = id;
    at.set(node, contentTop);
    node.getBoundingClientRect = () =>
      new DOMRect(0, at.get(node) - scrollTop, 300, 100);
    return node;
  };
  return {
    scroller,
    item,
    at,
    scrolled: () => scrollTop,
    scrollTo: (y) => (scrollTop = y),
  };
}

test("the band is the scroller's less a stuck cover", () => {
  const { scroller } = laidOut();
  const heading = document.createElement("h3");
  heading.className = "lf-pinned";
  heading.getBoundingClientRect = () => new DOMRect(0, -4, 300, 34);
  scroller.append(heading);
  assert.deepEqual(
    { top: visibleBand(scroller).top, bottom: visibleBand(scroller).bottom },
    { top: 30, bottom: 400 },
  );
  scroller.remove();
});

test("a node the render replaced hands the place across under its identity", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const nodes = ["a", "b", "c"].map((id, index) => item(id, 1000 + index * 150));
  scroller.append(...nodes);
  scrollTo(1000);
  const place = placeKeeper(scroller, {
    items: ".item",
    identity: (node) => node.dataset.id,
  });
  const hold = place.take();
  assert.equal(scroller.style.getPropertyValue("overflow-anchor"), "none");
  // The render rebuilds "a" as a new node 40px taller, and 60px of new content lands
  // above it. Held by "b" instead, the place would move by the 40px as well.
  const rebuilt = item("a", 1060);
  nodes[0].replaceWith(rebuilt);
  at.set(nodes[1], 1250);
  at.set(nodes[2], 1400);
  place.finish(hold);
  assert.equal(scrolled(), 1060);
  assert.equal(rebuilt.getBoundingClientRect().top, 0);
  assert.equal(scroller.style.getPropertyValue("overflow-anchor"), "");
  scroller.remove();
});
