/* Where a landing aims while a glide runs: from where the glide is headed, so a key
   pressed during it acts where it lands. A destination the glide will leave shown keeps
   the glide going to its goal, and one it will carry out of view is brought back from
   that goal, whether or not it shows now. An instant landing lands the glide, and a
   sideways reveal on the way leaves it going. A box held at the band's foot as it grows
   travels only whole pixels, so the browser's snapping never carries it past; a reveal
   travels the fraction it asked for, so the browser's snapping never leaves its target
   clipped. Asked over boxes this file states, since happy-dom lays nothing out. */

import assert from "node:assert/strict";
import test from "node:test";

import { keepInBand, scrollIntoView } from "/runtime/readings/landing-scroll.js";
import { glideTo, scrollGoal, stopGlide } from "/runtime/dom/scrolling.js";

// A scroller 300px wide and 400px tall, with no border or scrollbar, over content
// 1000px wide and 5000px tall, holding one box at `contentTop` and `contentLeft`, 100px
// tall and as wide as `width`; the box's viewport place is its content place less the
// scroller's scroll.
function laidOut(contentTop, contentLeft = 0, width = 300) {
  const scroller = document.createElement("div");
  scroller.style.overflow = "auto";
  document.body.append(scroller);
  let scrollTop = 0;
  let scrollLeft = 0;
  Object.defineProperties(scroller, {
    scrollTop: {
      get: () => scrollTop,
      set: (value) => {
        scrollTop = value;
      },
    },
    scrollLeft: {
      get: () => scrollLeft,
      set: (value) => {
        scrollLeft = value;
      },
    },
    scrollHeight: { get: () => 5000 },
    scrollWidth: { get: () => 1000 },
    clientHeight: { get: () => 400 },
    clientWidth: { get: () => 300 },
    offsetHeight: { get: () => 400 },
    offsetWidth: { get: () => 300 },
  });
  scroller.scrollTo = ({ top = scrollTop, left = scrollLeft }) => {
    scrollTop = top;
    scrollLeft = left;
  };
  scroller.getBoundingClientRect = () => new DOMRect(0, 0, 300, 400);
  const box = document.createElement("section");
  box.tabIndex = 0;
  box.getBoundingClientRect = () =>
    new DOMRect(contentLeft - scrollLeft, contentTop - scrollTop, width, 100);
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

test("an instant landing takes the box from the glide", () => {
  // Out of view now, at 1100..1200, and shown where the glide to 2000 leaves it.
  const ahead = laidOut(2100);
  ahead.scrollTo(1000);
  glideTo(ahead.scroller, 2000);
  scrollIntoView(ahead.box, { block: "nearest", behavior: "instant" });
  assert.equal(ahead.scroller.scrollTop, 2000, "the box was left to the glide's end");
  assert.equal(scrollGoal(ahead.scroller), 2000);
  stopGlide(ahead.scroller);
  ahead.scroller.remove();

  // Centred now, at 150..250, and carried 1000px up by the glide to 2000.
  const centred = laidOut(1150);
  centred.scrollTo(1000);
  glideTo(centred.scroller, 2000);
  scrollIntoView(centred.box, { block: "center", behavior: "instant" });
  assert.equal(scrollGoal(centred.scroller), 1000, "the glide carried the box away");
  stopGlide(centred.scroller);
  centred.scroller.remove();
});

test("a sideways reveal during a glide leaves the glide going", () => {
  // 400..500 across, past the scroller's 300px, and shown down where the glide to 2000
  // leaves it.
  const aside = laidOut(2100, 400, 100);
  aside.scrollTo(1000);
  glideTo(aside.scroller, 2000);
  scrollIntoView(aside.box, { block: "nearest", behavior: "smooth" });
  assert.equal(aside.scroller.scrollLeft, 200, "the box wasn't brought in across");
  assert.equal(scrollGoal(aside.scroller), 2000, "the reveal across stopped the glide");
  stopGlide(aside.scroller);
  aside.scroller.remove();
});

test("a box held at the band's foot travels only whole pixels", () => {
  // 450.578..550.578, so its foot is 150.578px below the scroller's 400px; the browser
  // would snap a move of that fraction to 151 and carry the foot a pixel past the band.
  const growing = laidOut(450.578);
  keepInBand(growing.box);
  assert.equal(growing.scroller.scrollTop, 150, "the held box travelled a fraction");
  growing.scroller.remove();
});

test("a reveal in an inner scrollport travels the fraction it asks for", () => {
  // A 200px scrollport that only a script scrolls, at the top of the reading scroller,
  // stands at 100 with its box's foot 1.75px past its own foot. Cut to the whole pixel,
  // the reveal would leave 0.75px clipped, which a retry is too short to move
  // (dom/arrivals.js, `setScroll`).
  const { scroller } = laidOut(0);
  const inner = document.createElement("div");
  inner.style.overflow = "hidden";
  let scrollTop = 100;
  Object.defineProperties(inner, {
    scrollTop: {
      get: () => scrollTop,
      set: (value) => {
        scrollTop = value;
      },
    },
    scrollLeft: { get: () => 0, set: () => {} },
    scrollHeight: { get: () => 1000 },
    scrollWidth: { get: () => 300 },
    clientHeight: { get: () => 200 },
    clientWidth: { get: () => 300 },
    offsetHeight: { get: () => 200 },
    offsetWidth: { get: () => 300 },
  });
  inner.scrollTo = ({ top = scrollTop }) => {
    scrollTop = top;
  };
  inner.getBoundingClientRect = () => new DOMRect(0, 0, 300, 200);
  const box = document.createElement("section");
  box.tabIndex = 0;
  box.getBoundingClientRect = () => new DOMRect(0, 201.75 - scrollTop, 300, 100);
  inner.append(box);
  scroller.append(inner);
  scrollIntoView(box, { block: "nearest", behavior: "instant" });
  assert.equal(inner.scrollTop, 101.75, "the reveal stopped short of the box's foot");
  scroller.remove();
});
