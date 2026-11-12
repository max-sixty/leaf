/* Which inputs the browser scrolls for (`scrollsFor`): a wheel, and one of its scroll
   keys wherever focus rests on no control that takes that key. A touch may be a tap, and
   a control takes keys of its own, as Space presses a button; read as the reader's
   scroll, Space on a button or a tap on one made a keep holding the reader's place across
   what the press changed stand down. A link or a button takes no arrow or paging key,
   and a radio no paging key, so the browser scrolls for those. And which of those
   scrolls a writer of a box's end leaves alone (`leavesEnd`): one up or across, until
   it ends. */

import assert from "node:assert/strict";
import test from "node:test";

import { aimScroll, leavesEnd, scrollsFor } from "/runtime/scrolling.js";

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

test("a scroll up or across leaves the box's end to the reader until it ends", () => {
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
  assert.equal(leavesEnd(box), false, "a wheel down heads to the end");
  aimScroll(box, wheel({ deltaY: -100 }));
  assert.equal(leavesEnd(box), true, "one up in the same scroll leaves it");
  ended();
  assert.equal(leavesEnd(box), false, "until that scroll ends");
  for (const [input, leaves] of /** @type {[Event, boolean][]} */ ([
    [wheel({ deltaX: 80 }), true],
    [wheel({ deltaX: 100, deltaY: -80 }), true],
    [wheel({ deltaY: 100, deltaX: 4 }), false],
    [key("PageUp"), true],
    [key(" ", true), true],
    [key("End"), false],
    [key(" "), false],
  ])) {
    aimScroll(box, input);
    assert.equal(leavesEnd(box), leaves);
    ended();
  }
  box.remove();
});
