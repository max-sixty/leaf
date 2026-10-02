/* The side a comment's surfaces take, the comment box and the thread card alike.

   A 1300px-wide, 900px-tall window throughout, whose boundary runs from 8 to 1292 across
   and from 50 to 847 down, and a card whose minimum width is 320. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  LEAST_HEIGHT,
  commentPlacement,
  commentSide,
} from "/runtime/comment-placement.js";

const boundary = new DOMRect(8, 50, 1284, 797);
// A paragraph `width` wide from x = `left`, from y = `top` to `bottom`.
const block = (left, width, top, bottom) => new DOMRect(left, top, width, bottom - top);
// A page scrolled `scrollTop` into a document `height` tall, in an 850px scrollport.
const scroller = (scrollTop, height = 3000) => ({
  scrollTop,
  scrollHeight: height,
  clientHeight: 850,
});
const side = (clear, { scrolled = 1000, document = 3000, coarse = false } = {}) =>
  commentSide({
    clear,
    extent: clear,
    boundary,
    width: 320,
    scroller: scroller(scrolled, document),
    coarse,
  });

test("beside needs room for the card, not only the box", () => {
  // 326px right of the paragraph holds the card's 320 and the gap: beside.
  assert.equal(side(block(300, 660, 300, 500)), "right");
  // 300px would hold a comment box but not the card, so neither stands there.
  assert.notEqual(side(block(300, 686, 300, 500)), "right");
});

test("left of the words when only that side holds the card", () => {
  assert.equal(side(block(400, 880, 300, 500)), "left");
});

test("under or over by the room the page can make, not the room it shows", () => {
  // More shows over the paragraph than under it, but the page can scroll further down.
  const low = block(40, 1240, 500, 700);
  assert.equal(side(low, { scrolled: 100 }), "bottom");
  // The same paragraph near the document's foot: only over it can the page make room.
  assert.equal(side(low, { scrolled: 2150 }), "top");
});

test("the side is the same wherever the page is scrolled", () => {
  // A scroll moves the paragraph by as much as it moves the travel left each way, so
  // under, where the document ends 300px past the paragraph, stays the smaller room.
  const at = (scrolled) =>
    side(block(40, 1240, 1400 - scrolled, 1600 - scrolled), {
      scrolled,
      document: 1900,
    });
  assert.deepEqual([700, 800, 900, 1000].map(at), ["top", "top", "top", "top"]);
});

test("where both sides can make the whole room, the one that shows more takes it", () => {
  const at = (scrolled) =>
    side(block(40, 1240, 1400 - scrolled, 1600 - scrolled), { scrolled });
  assert.deepEqual([900, 1300].map(at), ["top", "bottom"]);
});

test("a touch screen takes under wherever the page can make a surface's least room", () => {
  // At the document's foot, only what shows under the paragraph is room there: 847, the
  // boundary's foot, less the gap, less the paragraph's foot.
  const under = (room) => block(40, 1240, 847 - 8 - room - 200, 847 - 8 - room);
  assert.equal(side(under(LEAST_HEIGHT), { scrolled: 2150 }), "top");
  assert.equal(side(under(LEAST_HEIGHT), { scrolled: 2150, coarse: true }), "bottom");
  assert.equal(side(under(LEAST_HEIGHT - 1), { scrolled: 2150, coarse: true }), "top");
});

test("a submitted frame survives supersession until it lands, then follows scroll but not reflow", () => {
  for (const unanchored of [false, true]) {
    const clear = block(300, 660, 300, 500);
    const input = {
      clear,
      boundary,
      row: clear.top,
      minimum: { width: 320 },
      scroller: scroller(1000),
      coarse: false,
    };
    const editor = commentPlacement();
    editor.choose({ ...input, clear: unanchored ? null : clear });
    const box = new DOMRect(980, 317, 320, 160);
    const card = commentPlacement();
    card.adopt({ box, placement: editor.capture() });
    const opening = card.choose(input);
    assert.equal(opening.side, editor.side);
    assert.equal(opening.fresh, false);
    const top = box.top - (unanchored ? clear.bottom : clear.top);
    assert.deepEqual(opening.hold, { top, foot: top + box.height });
    assert.deepEqual(card.choose(input).hold, opening.hold);

    const scrolled = block(300, 660, 200, 400);
    const reading = card.choose({ ...input, clear: scrolled, row: scrolled.top });
    assert.equal(reading.fresh, false);
    assert.deepEqual(reading.hold, opening.hold);
    card.landed({
      x: box.left,
      y: box.top - 100,
      middlewareData: {
        scaled: {
          scale: { x: 1, y: 1 },
          column: scrolled.right - input.minimum.width,
          line: card.line(scrolled, scrolled.top),
        },
        held: { height: box.height },
      },
    });
    assert.equal(card.choose({ ...input, clear: scrolled }).hold, undefined);

    const reflowed = block(300, 700, 200, 400);
    assert.equal(card.choose({ ...input, clear: reflowed }).fresh, true);
    card.adopt({ box, placement: editor.capture() });
    const resized = new DOMRect(8, 50, 1084, 797);
    const afterResize = card.choose({ ...input, boundary: resized });
    assert.equal(afterResize.fresh, true);
    assert.equal(afterResize.hold, undefined);
  }
});
