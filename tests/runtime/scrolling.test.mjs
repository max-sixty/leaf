/* Which inputs the browser scrolls for (`scrollsFor`): a wheel, and one of its scroll
   keys only where focus rests on no control. A touch may be a tap, and a control takes
   keys of its own, as Space presses a button; read as the reader's scroll, Space on a
   button or a tap on one made a keep holding the reader's place across what the press
   changed stand down. */

import assert from "node:assert/strict";
import test from "node:test";

import { scrollsFor } from "/runtime/scrolling.js";

test("the browser scrolls for a wheel, and for a scroll key only off a control", () => {
  const button = document.createElement("button");
  const field = document.createElement("input");
  const prose = document.createElement("p");
  const words = document.createElement("span");
  prose.append(words);
  document.body.append(button, field, prose);
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
  [button, field, prose].forEach((node) => node.remove());
});
