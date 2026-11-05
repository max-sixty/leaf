/* The user's place in a scroller, and the one hold that keeps it across a change.

   Asked over boxes this file states, since happy-dom lays nothing out: focus scrolled
   away or riding in a stuck header names no place, and a hold puts the node it read
   back where it stood, or its stand-in where the change hid it, paying only for what
   the browser's own anchoring left. The user's place across a reading is the first the
   change moved of those they named, and its keep yields to any scroll or input since. */

import assert from "node:assert/strict";
import test from "node:test";

import { recentPlaceInput } from "/runtime/focus.js";
import { pointerAt } from "/runtime/pointer.js";
import { focusedInView, holdPlace, holdUserPlace } from "/runtime/user-place.js";

// A scroller whose boxes are stated: each node's viewport top is its content top less
// the scroller's scrollTop.
function laidOut() {
  const scroller = document.createElement("div");
  scroller.style.overflowY = "auto";
  document.body.append(scroller);
  let scrollTop = 0;
  Object.defineProperty(scroller, "scrollTop", {
    get: () => scrollTop,
    set: (value) => {
      scrollTop = value;
    },
  });
  Object.defineProperties(scroller, {
    scrollHeight: { get: () => 5000 },
    clientHeight: { get: () => 400 },
    clientWidth: { get: () => 300 },
  });
  scroller.scrollTo = ({ top }) => {
    scrollTop = top;
  };
  scroller.getBoundingClientRect = () => new DOMRect(0, 0, 300, 400);
  const at = new Map();
  const item = (id, contentTop, height = 100) => {
    const node = document.createElement("section");
    node.className = "item";
    node.dataset.id = id;
    at.set(node, contentTop);
    node.getBoundingClientRect = () =>
      new DOMRect(0, at.get(node) - scrollTop, 300, node.hidden ? 0 : height);
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

test("focus marks the place while some of it shows, and never from a stuck header", () => {
  const { scroller, item, scrollTo } = laidOut();
  const [first, second] = [item("a", 1000), item("b", 1250)];
  first.tabIndex = 0;
  // A heading sticking at the scroller's top, which holds it at its own place until
  // its section scrolls past that top.
  const heading = document.createElement("h2");
  heading.tabIndex = 0;
  heading.style.position = "sticky";
  heading.style.top = "0px";
  heading.getBoundingClientRect = () =>
    new DOMRect(0, Math.max(second.getBoundingClientRect().top, 0), 300, 20);
  second.append(heading);
  scroller.append(first, second);

  scrollTo(1000);
  first.focus();
  assert.equal(focusedInView(), first);
  scrollTo(3000);
  assert.equal(focusedInView(), null, "focus scrolled away still named the place");

  scrollTo(1000);
  heading.focus();
  assert.equal(focusedInView(), heading);
  scrollTo(1300);
  assert.equal(focusedInView(), null, "a stuck heading named the place it rides over");
  scroller.remove();
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

test("a mouse that leaves the window stands nowhere, and a lifted finger stays", () => {
  /** @param {string} type @param {object} fields */
  const send = (type, fields) => {
    const event = new Event(type);
    for (const [name, value] of Object.entries(fields))
      Object.defineProperty(event, name, { value });
    document.dispatchEvent(event);
  };
  send("pointermove", { clientX: 40, clientY: 50 });
  // Out to another element of the page: the mouse is still over it.
  send("pointerout", { pointerType: "mouse", relatedTarget: document.body });
  assert.deepEqual(pointerAt(), { x: 40, y: 50 });
  send("pointerout", { pointerType: "touch", relatedTarget: null });
  assert.deepEqual(pointerAt(), { x: 40, y: 50 });
  send("pointerout", { pointerType: "mouse", relatedTarget: null });
  assert.deepEqual(pointerAt(), { x: -1, y: -1 });
});

test("a hold pays for the growth above its node that anchoring left", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [above, read] = [item("a", 1000), item("b", 1150)];
  scroller.append(above, read);
  scrollTo(1100);
  const hold = holdPlace(read);
  // The edit grows the block above by 126px, and the browser's anchoring, holding that
  // block's top, paid for none of it.
  at.set(read, 1276);
  hold();
  assert.equal(scrolled(), 1226);
  assert.equal(read.getBoundingClientRect().top, 50);
  // Where anchoring already paid, the hold has nothing left to pay.
  const again = holdPlace(read);
  at.set(read, 1300);
  scrollTo(1250);
  again();
  assert.equal(scrolled(), 1250);
  scroller.remove();
});

test("a change that hides the held node puts its stand-in where it stood", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [gist, folded] = [item("gist", 1000), item("folded", 1100)];
  scroller.append(gist, folded);
  scrollTo(1080);
  const hold = holdPlace(folded, (node) => (node === folded ? gist : null));
  // The fold hides the block being read, and the gist it runs under stays put above.
  // happy-dom applies no user-agent sheet, so the block states what `[hidden]` computes.
  folded.hidden = true;
  folded.style.display = "none";
  hold();
  assert.equal(scrolled(), 980);
  assert.equal(gist.getBoundingClientRect().top, 20);
  // With no stand-in, a hidden or removed node holds nothing.
  at.set(gist, 1000);
  const lost = holdPlace(gist);
  gist.remove();
  scrollTo(900);
  lost();
  assert.equal(scrolled(), 900);
  scroller.remove();
});

// The pointer moved to rest over `node`, as the platform reports what lies under it.
/** @param {Element | null} node */
function restOn(node) {
  document.elementFromPoint = () => node;
  const movement = new Event("pointermove");
  Object.defineProperties(movement, { clientX: { value: 10 }, clientY: { value: 10 } });
  document.dispatchEvent(movement);
}

test("the keep puts back the first place the change moved", () => {
  const page = laidOut();
  const rail = laidOut();
  const read = page.item("read", 1150);
  const resting = rail.item("rail", 0);
  page.scroller.append(read);
  rail.scroller.append(resting);
  page.scrollTo(1100);
  read.tabIndex = 0;
  read.focus();
  // The pointer, moved last, rests on a rail of its own that the edit leaves still, so
  // the focused block it pushed down 126px is the place kept.
  restOn(resting);
  assert.equal(recentPlaceInput(), "pointer");
  const keep = holdUserPlace();
  page.at.set(read, 1276);
  keep();
  assert.equal(page.scrolled(), 1226);
  // With focus in a field that names no place, the row under the resting pointer is kept.
  const search = document.createElement("input");
  document.body.append(search);
  search.focus();
  restOn(read);
  const row = holdUserPlace();
  page.at.set(read, 1400);
  row();
  assert.equal(page.scrolled(), 1350);
  [page.scroller, rail.scroller, search].forEach((node) => node.remove());
  restOn(null);
});

test("a place the change left still keeps its scroller", () => {
  const { scroller, item, at, scrolled, scrollTo } = laidOut();
  const [above, below] = [item("above", 1150), item("below", 1300)];
  scroller.append(above, below);
  scrollTo(1100);
  // Focus arrives last on the upper block, with the pointer resting on the lower one;
  // news joins between them, and anchoring holds the upper block.
  restOn(below);
  above.tabIndex = 0;
  above.focus();
  assert.equal(recentPlaceInput(), "focus");
  const keep = holdUserPlace();
  at.set(below, 1426);
  keep();
  assert.equal(scrolled(), 1100, "the block under the pointer moved the focused one");
  scroller.remove();
  restOn(null);
});

test("the keep yields to a scroll under way and to any input since the reading", () => {
  for (const since of [
    (/** @type {Element} */ box) => box.dispatchEvent(new Event("scroll")),
    () => window.dispatchEvent(new Event("wheel")),
  ]) {
    const { scroller, item, at, scrolled, scrollTo } = laidOut();
    const read = item("read", 1150);
    scroller.append(read);
    scrollTo(1100);
    read.tabIndex = 0;
    read.focus();
    const keep = holdUserPlace();
    at.set(read, 1276);
    since(scroller);
    keep();
    assert.equal(scrolled(), 1100, `the keep overrode ${since}`);
    scroller.remove();
  }
});

test("a block folded until found holds its stand-in, though it keeps a box", () => {
  const { scroller, item, scrolled, scrollTo } = laidOut();
  const [gist, folded] = [item("gist", 1000), item("folded", 1100)];
  scroller.append(gist, folded);
  scrollTo(1080);
  const hold = holdPlace(folded, (node) => (node === folded ? gist : null));
  // `hidden="until-found"` keeps the block's box and hides its contents.
  folded.setAttribute("hidden", "until-found");
  folded.style.display = "block";
  assert.ok(folded.checkVisibility());
  hold();
  assert.equal(scrolled(), 980);
  scroller.remove();
});
