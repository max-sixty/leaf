/* The user's place in a scroller, and the one hold that keeps it across a change.

   Asked over boxes this file states, since happy-dom lays nothing out: focus scrolled
   away or riding in a stuck header names no place, and a hold puts the node it read
   back where it stood, or its stand-in where the change hid it, paying only for what
   the browser's own anchoring left. */

import assert from "node:assert/strict";
import test from "node:test";

import { pointerAt } from "/runtime/pointer.js";
import { focusedInView, holdPlace } from "/runtime/user-place.js";

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
  folded.hidden = true;
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
