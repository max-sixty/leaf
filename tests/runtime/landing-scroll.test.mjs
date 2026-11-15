/* Where a nearest landing aims while a glide runs: from where the glide is headed, so a
   key pressed during it acts where it lands. A destination the glide will leave shown
   keeps the glide going to its goal, and one it will carry out of view is brought back
   from that goal, whether or not it shows now. Asked over boxes this file states, since
   happy-dom lays nothing out. */

import assert from "node:assert/strict";
import test from "node:test";

import { scrollIntoView } from "/runtime/landing-scroll.js";
import { glideTo, scrollGoal, stopGlide } from "/runtime/scrolling.js";

// A scroller 400px tall over 5000px of content, holding one 100px box at `contentTop`;
// the box's viewport top is its content top less the scroller's scrollTop.
function laidOut(contentTop) {
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
  const box = document.createElement("section");
  box.tabIndex = 0;
  box.getBoundingClientRect = () => new DOMRect(0, contentTop - scrollTop, 300, 100);
  scroller.append(box);
  return { scroller, box, scrollTo: (/** @type {number} */ y) => (scrollTop = y) };
}

test("a nearest landing during a glide aims from where the glide is headed", () => {
  // Shown now, at 100..200, but the glide to 2000 will carry it 1000px above the window.
  const away = laidOut(1000);
  away.scrollTo(900);
  glideTo(away.scroller, 2000);
  scrollIntoView(away.box, { block: "nearest", behavior: "smooth" });
  const goal = scrollGoal(away.scroller);
  assert.ok(
    goal <= 1000 && goal > 900,
    `the landing aimed at ${goal}, not where the box comes in at the top from 2000`,
  );
  stopGlide(away.scroller);
  away.scroller.remove();

  // Out of view now, at 1100..1200, but the glide to 2000 will leave it at 100..200.
  const ahead = laidOut(2100);
  ahead.scrollTo(1000);
  glideTo(ahead.scroller, 2000);
  scrollIntoView(ahead.box, { block: "nearest", behavior: "smooth" });
  assert.equal(scrollGoal(ahead.scroller), 2000, "the landing turned the glide aside");
  stopGlide(ahead.scroller);
  ahead.scroller.remove();
});
