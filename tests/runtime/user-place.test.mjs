/* The user's place in a scroller, and the band of it they can see.

   The folds (which candidate holds the place, how far a correction scrolls, what a cover
   takes off a band) are asked directly. The hold itself is asked once over boxes this
   file states, since happy-dom lays nothing out: a node the render replaced hands the
   place to the node now rendered under its identity. */

import assert from "node:assert/strict";
import test from "node:test";

import { declareCoverRoom, insetBand, visibleBand } from "/runtime/geometry.js";
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
  // A cover stuck at its sticky inset, under a banner, takes the band to its foot; the
  // same box in flow further down is content passing through.
  const stuck = (top, bottom) => ({ ...box(top, bottom), stickyTop: 42 });
  assert.deepEqual(insetBand(band, [stuck(142, 190)]), { ...band, top: 190 });
  assert.deepEqual(insetBand(band, [stuck(260, 308)]), band);
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
  heading.getBoundingClientRect = () => new DOMRect(0, -4, 300, 34);
  scroller.append(heading);
  // Undeclared, a sticky box is content like any other.
  assert.equal(visibleBand(scroller).top, 0);
  declareCoverRoom(scroller, "--lf-head-room", [heading]);
  assert.deepEqual(
    { top: visibleBand(scroller).top, bottom: visibleBand(scroller).bottom },
    { top: 30, bottom: 400 },
  );
  // Read while detached, then put back and declared again, it is still a cover.
  heading.remove();
  visibleBand(scroller);
  scroller.append(heading);
  declareCoverRoom(scroller, "--lf-head-room", [heading]);
  assert.equal(visibleBand(scroller).top, 30);
  // A cover does not hide what it holds: read for a node inside it, the band keeps it.
  const label = document.createElement("span");
  heading.append(label);
  assert.equal(visibleBand(scroller, label).top, 0);
  // A heading stuck in a nested scroller is that scroller's, though this one holds it.
  heading.remove();
  const inner = document.createElement("div");
  inner.style.overflowY = "auto";
  inner.append(heading);
  scroller.append(inner);
  assert.equal(visibleBand(scroller).top, 0);
  // A cover in a widget's shadow tree sticks in the scroller outside it.
  inner.remove();
  const widget = document.createElement("div");
  widget.attachShadow({ mode: "open" }).append(heading);
  scroller.append(widget);
  assert.equal(visibleBand(scroller).top, 30);
  scroller.remove();
});

test("a host's first cover keeps its room from the declaration on", () => {
  // The first observation comes after the frame's layout, and a document's initial
  // fragment landing reads the room before it: declared, the room is already there.
  const { scroller } = laidOut();
  const strip = document.createElement("div");
  strip.getBoundingClientRect = () => new DOMRect(0, 42, 300, 47);
  scroller.append(strip);
  declareCoverRoom(scroller, "--lf-strip-room", [strip]);
  assert.equal(scroller.style.getPropertyValue("--lf-strip-room"), "47px");
  // A cover replacing it starts at the room the host keeps rather than at none.
  const next = document.createElement("div");
  next.getBoundingClientRect = () => new DOMRect(0, 42, 300, 30);
  scroller.append(next);
  declareCoverRoom(scroller, "--lf-strip-room", [next]);
  assert.equal(scroller.style.getPropertyValue("--lf-strip-room"), "47px");
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
