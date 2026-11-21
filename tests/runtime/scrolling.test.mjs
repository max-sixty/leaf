/* Which inputs the browser scrolls for (`scrollsFor`): a wheel, and one of its scroll
   keys wherever focus rests on no control that takes that key. A touch may be a tap, and
   a control takes keys of its own, as Space presses a button; read as the reader's
   scroll, Space on a button or a tap on one made a keep holding the reader's place across
   what the press changed stand down. A link or a button takes no arrow or paging key,
   and a radio no paging key, so the browser scrolls for those. And which way such a
   scroll heads its box until it ends, and where it found the box (`readerScroll`),
   which a writer of the box's end asks first. And how a move to a box's end meets a
   glide already headed there (`scrollToEnd`): the owners that keep a box at its end
   move it there at every fit, and a jump there cut the glide following an answer into
   sight. And that a glide lands on its goal in a box that stands only at whole pixels,
   so `u` pressed after `d` has landed takes the box back to its top. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  aimScroll,
  glideTo,
  readerScroll,
  scrollGoal,
  scrollsFor,
  scrollToEnd,
  stopGlide,
} from "/runtime/scrolling.js";

// The frames a glide asks for run when a test says, at the time it gives.
/** @type {FrameRequestCallback[]} */
let asked = [];
globalThis.requestAnimationFrame = (callback) => asked.push(callback);
/** @param {number} at */
const frameAt = async (at) => {
  const callbacks = asked;
  asked = [];
  for (const callback of callbacks) await callback(at);
};

test("the browser scrolls for a wheel, and for a scroll key a control leaves it", () => {
  const button = document.createElement("button");
  const field = document.createElement("input");
  const link = Object.assign(document.createElement("a"), { href: "#there" });
  const radio = Object.assign(document.createElement("input"), { type: "radio" });
  const prose = document.createElement("p");
  const words = document.createElement("span");
  prose.append(words);
  document.body.append(button, field, link, radio, prose);
  /** @param {Element} at @param {Event} event */
  const scrolls = (at, event) => {
    let asked = null;
    at.addEventListener(
      event.type,
      (/** @type {Event} */ heard) => {
        asked = scrollsFor(heard);
      },
      { once: true },
    );
    at.dispatchEvent(event);
    return asked;
  };
  /** @param {string} key */
  const key = (key) => new window.KeyboardEvent("keydown", { key, bubbles: true });
  assert.equal(scrolls(button, key(" ")), false);
  assert.equal(scrolls(button, key("ArrowUp")), true);
  assert.equal(scrolls(link, key("PageUp")), true);
  assert.equal(scrolls(link, key(" ")), true);
  assert.equal(scrolls(radio, key("ArrowUp")), false);
  assert.equal(scrolls(radio, key("PageUp")), true);
  assert.equal(scrolls(radio, key(" ")), false);
  assert.equal(scrolls(field, key("ArrowDown")), false);
  assert.equal(scrolls(words, key(" ")), true);
  assert.equal(scrolls(prose, key("PageDown")), true);
  assert.equal(scrolls(prose, key("d")), false);
  assert.equal(
    scrolls(button, new window.Event("touchstart", { bubbles: true })),
    false,
  );
  assert.equal(
    scrolls(button, new window.WheelEvent("wheel", { bubbles: true })),
    true,
  );
  [button, field, link, radio, prose].forEach((node) => node.remove());
});

test("a scroll heads its box the furthest way any of its inputs does, until it ends", () => {
  const box = document.createElement("div");
  document.body.append(box);
  let top = 200;
  Object.defineProperties(box, {
    clientHeight: { value: 100 },
    scrollHeight: { value: 300 },
    scrollTop: { get: () => top },
    scrollLeft: { value: 0 },
  });
  /** @param {WheelEventInit} delta */
  const wheel = (delta) => new window.WheelEvent("wheel", delta);
  /** @param {string} key @param {boolean} [shiftKey] */
  const key = (key, shiftKey = false) =>
    new window.KeyboardEvent("keydown", { key, shiftKey });
  // The scroll moves the box and ends.
  const ended = () => {
    top -= 50;
    box.dispatchEvent(new window.Event("scrollend"));
  };
  aimScroll(box, wheel({ deltaY: 100 }));
  assert.deepEqual(readerScroll(box), {
    heads: "down",
    top: 200,
    fromEnd: 0,
    starts: 0,
  });
  top = 150;
  aimScroll(box, wheel({ deltaX: 80 }));
  aimScroll(box, wheel({ deltaY: 100 }));
  assert.deepEqual(
    readerScroll(box),
    { heads: "across", top: 200, fromEnd: 0, starts: 0 },
    "across, from where the first input found the box",
  );
  aimScroll(box, wheel({ deltaY: -100 }));
  assert.equal(readerScroll(box)?.heads, "up");
  ended();
  assert.equal(readerScroll(box), null, "until that scroll ends");
  for (const [input, heads] of /** @type {[Event, string][]} */ ([
    [wheel({ deltaX: 100, deltaY: -80 }), "across"],
    [wheel({ deltaY: 100, deltaX: 4 }), "down"],
    [wheel({ deltaY: -100, deltaX: 4 }), "up"],
    [key("PageUp"), "up"],
    [key(" ", true), "up"],
    [key("End"), "down"],
    [key(" "), "down"],
  ])) {
    aimScroll(box, input);
    assert.equal(readerScroll(box)?.heads, heads);
    ended();
  }
  // Where the browser applied the input's scroll before the input was heard, as
  // Chromium can a wheel's, the input found the box where the page last heard it.
  top = 200;
  box.dispatchEvent(new window.Event("scroll"));
  ended();
  box.dispatchEvent(new window.Event("scroll"));
  top = 100;
  aimScroll(box, wheel({ deltaY: -100 }));
  assert.deepEqual(readerScroll(box), {
    heads: "up",
    top: 150,
    fromEnd: 50,
    starts: 0,
  });
  box.remove();
});

test("a move to the end leaves a glide headed there going, and turns it to a new end", () => {
  // A box 400px tall over content 1000px tall, which grows as an answer arrives.
  const box = document.createElement("div");
  document.body.append(box);
  let top = 0;
  let height = 1000;
  Object.defineProperties(box, {
    scrollTop: {
      get: () => top,
      set: (value) => {
        top = value;
      },
    },
    scrollHeight: { get: () => height },
    clientHeight: { get: () => 400 },
  });
  box.scrollTo = ({ top: to = top }) => {
    top = to;
  };
  scrollToEnd(box, "smooth");
  assert.equal(scrollGoal(box), 600);
  scrollToEnd(box);
  assert.equal(box.scrollTop, 0, "a move to the end cut the glide to a jump");
  assert.equal(scrollGoal(box), 600);
  height = 1200;
  scrollToEnd(box);
  assert.equal(box.scrollTop, 0, "a move to the new end cut the glide to a jump");
  assert.equal(scrollGoal(box), 800, "the glide kept going to the old end");
  stopGlide(box);
  scrollToEnd(box);
  assert.equal(box.scrollTop, 800, "with no glide under way, the move is instant");
  box.remove();
});

test("a glide lands on its goal in a box that stands at whole pixels", async () => {
  // A box 268px tall over content 488px tall, which the browser scrolls only to whole
  // pixels, as Chrome does at one device pixel to the CSS pixel.
  const box = document.createElement("div");
  document.body.append(box);
  let top = 0;
  Object.defineProperties(box, {
    scrollTop: { get: () => top },
    scrollHeight: { get: () => 488 },
    clientHeight: { get: () => 268 },
  });
  box.scrollTo = ({ top: to = top }) => {
    top = Math.round(Math.min(Math.max(to, 0), 220));
  };
  // A page of the threads view measures 159.7px, so `d` heads for 159.7, and a frame
  // late in its glide leaves the box at 160, within a pixel of that goal.
  const page = 159.7;
  await frameAt(performance.now());
  let start = performance.now();
  glideTo(box, scrollGoal(box) + page);
  await frameAt(start + 0.95 * 140);
  await frameAt(start + 1000);
  assert.equal(box.scrollTop, 160);
  // `u` pressed once `d` has landed heads a page back from where the box stands, and a
  // frame late in its glide leaves the box at 1.
  start = performance.now();
  glideTo(box, scrollGoal(box) - page);
  await frameAt(start + 0.85 * 140);
  await frameAt(start + 1000);
  assert.equal(box.scrollTop, 0, "u left the box short of its top");
  stopGlide(box);
  box.remove();
});
