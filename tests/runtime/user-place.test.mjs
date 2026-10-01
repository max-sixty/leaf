/* The user's place in a scroller, and the band of it they can see.

   The folds (which candidate holds the place, how far a correction scrolls) are asked
   directly. The hold itself is asked over boxes this file
   states, since happy-dom lays nothing out: a node the render replaced hands the place
   to the node now rendered under its identity, and a synchronous hold lands its
   reference whatever the browser's own anchoring did first. */

import assert from "node:assert/strict";
import test from "node:test";

import { pointerAt } from "/runtime/pointer.js";
import { placeCandidates, placeCorrection, placeKeeper } from "/runtime/user-place.js";

test("the place follows the most recent named item, then visible items", () => {
  const visible = ["a", "b", "c", "d"];
  assert.deepEqual(placeCandidates({ inherited: null, named: ["c", "a"], visible }), [
    "c",
    "a",
    "d",
    "b",
  ]);
  assert.deepEqual(placeCandidates({ inherited: null, named: [], visible }), [
    "a",
    "b",
    "c",
    "d",
  ]);
  // A fold in flight has already moved what the pointer names; its reference leads.
  assert.deepEqual(placeCandidates({ inherited: "b", named: ["d"], visible }), [
    "b",
    "d",
    "c",
    "a",
  ]);
  // The caller admits only visible pointer and focus candidates.
  assert.deepEqual(placeCandidates({ inherited: null, named: ["d", "c"], visible }), [
    "d",
    "c",
    "a",
    "b",
  ]);
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
  // Standing short of the limit is the user's own scroll, not a clamp.
  assert.equal(
    placeCorrection({ was: 1000, now: 1000, scrollTop: 650, limit: 700, held }),
    0,
  );
  // Within one task the same movement is the browser's anchoring, and is paid for.
  assert.equal(
    placeCorrection({
      was: 1000,
      now: 1000,
      scrollTop: 650,
      limit: 700,
      held,
      withinTask: true,
    }),
    250,
  );
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

test("a hold names only a visible focus or pointer target", () => {
  const { scroller, item, scrollTo } = laidOut();
  const nodes = ["a", "b", "c"].map((id, index) => item(id, 1000 + index * 250));
  for (const node of nodes) node.tabIndex = 0;
  scroller.append(...nodes);
  scrollTo(1000);
  const place = placeKeeper(scroller, {
    items: ".item",
    identity: (node) => node.dataset.id,
  });
  nodes[2].focus();
  const offscreen = place.take();
  assert.equal(offscreen.named, null);
  assert.equal(offscreen.references[0].node, nodes[0]);
  place.finish(offscreen);

  nodes[1].focus();
  const focused = place.take();
  assert.equal(focused.named, nodes[1]);
  place.finish(focused);

  const originalHitTest = document.elementFromPoint;
  document.elementFromPoint = () => nodes[0];
  try {
    const movement = new Event("pointermove");
    Object.defineProperties(movement, {
      clientX: { value: 10 },
      clientY: { value: 50 },
    });
    document.dispatchEvent(movement);
    const pointed = place.take();
    assert.equal(pointed.named, nodes[0]);
    place.finish(pointed);
  } finally {
    document.elementFromPoint = originalHitTest;
    scroller.remove();
  }
});

test("a wheel leaves the precise pointer position intact", () => {
  const movement = new Event("pointermove");
  Object.defineProperties(movement, {
    clientX: { value: 120.5 },
    clientY: { value: 240.25 },
  });
  document.dispatchEvent(movement);
  document.dispatchEvent(new Event("wheel"));
  assert.deepEqual(pointerAt(), { x: 120.5, y: 240.25 });
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

test("a node with no identity passes the place to the next candidate, not a stranger", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const nodes = ["", "b"].map((id, index) => item(id, 1000 + index * 150));
  scroller.append(...nodes);
  scrollTo(1000);
  const place = placeKeeper(scroller, {
    items: ".item",
    identity: (node) => node.dataset.id,
  });
  const hold = place.take();
  // The unnamed reference leaves; another unnamed row arrives far below.
  nodes[0].remove();
  const stranger = item("", 1600);
  scroller.append(stranger);
  at.set(nodes[1], 1100);
  place.finish(hold);
  assert.equal(scrolled(), 950);
  assert.equal(nodes[1].getBoundingClientRect().top, 150);
  scroller.remove();
});

test("an item the band's top cuts holds the place only where none begins in view", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const nodes = ["a", "b"].map((id, index) => item(id, 950 + index * 100));
  for (const node of nodes) node.tabIndex = 0;
  scroller.append(...nodes);
  scrollTo(1000);
  const place = placeKeeper(scroller, {
    items: ".item",
    identity: (node) => node.dataset.id,
  });
  // Focus in "a", whose top stands above the band, names no place: "b" holds it.
  nodes[0].focus();
  const hold = place.take();
  assert.equal(hold.named, null);
  assert.equal(hold.references[0].node, nodes[1]);
  // "a" grows by 60px at its end, and so grows up into the room scrolled past.
  at.set(nodes[1], 1110);
  place.finish(hold);
  assert.equal(scrolled(), 1060);
  assert.equal(nodes[1].getBoundingClientRect().top, 50);

  // With nothing else in view, the cut item still holds it.
  nodes[1].remove();
  scrollTo(1000);
  const alone = place.take();
  assert.equal(alone.references[0].node, nodes[0]);
  place.finish(alone);
  scroller.remove();
});

test("a synchronous hold claims no anchoring and absorbs the browser's", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const nodes = ["a", "b"].map((id, index) => item(id, 1000 + index * 150));
  scroller.append(...nodes);
  scrollTo(1000);
  const place = placeKeeper(scroller, {
    items: ".item",
    identity: (node) => node.dataset.id,
  });
  place.around(() => {
    // 100px lands above "a", and the browser's own anchoring, applied by a forced
    // layout, followed only 60px of it.
    at.set(nodes[0], 1100);
    at.set(nodes[1], 1250);
    scrollTo(1060);
    assert.equal(scroller.style.getPropertyValue("overflow-anchor"), "");
  });
  assert.equal(scrolled(), 1100);
  assert.equal(nodes[0].getBoundingClientRect().top, 0);
  scroller.remove();
});
