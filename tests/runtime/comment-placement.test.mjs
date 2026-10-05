/* The side a comment's surfaces take, the comment box and the thread card alike.

   A 1300px-wide, 900px-tall window throughout, whose boundary runs from 8 to 1292 across
   and from 50 to 847 down, and a card whose minimum width is 320. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  LEAST_HEIGHT,
  commentPlacement,
  commentSide,
} from "/runtime/annotation-overlay/comment-placement.js";

// The card's widths as theme.css declares them, which the placement reads off the root.
document.documentElement.style.setProperty("--thread-card-min", "320px");
document.documentElement.style.setProperty("--thread-card", "592px");

// A window boundary, keyed by its edges as commentBoundary keys one.
const windowBoundary = (left, top, width, height) =>
  Object.assign(new DOMRect(left, top, width, height), {
    inRegion: null,
    key: [left, top, left + width, top + height],
  });
const boundary = windowBoundary(8, 50, 1284, 797);
// A paragraph `width` wide from x = `left`, from y = `top` to `bottom`.
const block = (left, width, top, bottom) => new DOMRect(left, top, width, bottom - top);
// A page scrolled `scrollTop` into a document `height` tall, in an 850px scrollport.
const scroller = (scrollTop, height = 3000) => {
  const box = { scrollTop, scrollHeight: height, clientHeight: 850 };
  box.ownerDocument = { scrollingElement: box };
  return box;
};
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
          column: scrolled.right - 320,
          line: card.line(scrolled, scrolled.top),
        },
        held: { height: box.height },
      },
    });
    assert.equal(card.choose({ ...input, clear: scrolled }).hold, undefined);

    const reflowed = block(300, 700, 200, 400);
    assert.equal(card.choose({ ...input, clear: reflowed }).fresh, true);
    card.adopt({ box, placement: editor.capture() });
    const resized = windowBoundary(8, 50, 1084, 797);
    const afterResize = card.choose({ ...input, boundary: resized });
    assert.equal(afterResize.fresh, true);
    assert.equal(afterResize.hold, undefined);
  }
});

test("a page scroll that moves a region's shown bounds keeps the side", () => {
  // A region boundary is keyed by the region's whole size, so a scroll of the page that
  // moves and clips its shown bounds chooses no side afresh, while a resize does.
  const region = (top, height, size = [0, 0, 900, 600]) =>
    Object.assign(new DOMRect(100, top, 900, height), { inRegion: {}, key: size });
  const clear = block(120, 860, 300, 500);
  const input = {
    clear,
    row: clear.top,
    scroller: scroller(1000),
    coarse: false,
  };
  const card = commentPlacement();
  assert.equal(card.choose({ ...input, boundary: region(58, 597) }).fresh, true);
  assert.equal(card.choose({ ...input, boundary: region(50, 560) }).fresh, false);
  assert.equal(
    card.choose({ ...input, boundary: region(50, 560, [0, 0, 900, 500]) }).fresh,
    true,
  );
});

test("a growing card holds its top while read and its foot for the turn that joins a draft", () => {
  const clear = block(300, 660, 300, 500);
  const input = {
    clear,
    boundary,
    row: clear.top,
    scroller: scroller(1000),
    coarse: false,
  };
  const card = commentPlacement();
  const land = () =>
    card.landed({
      x: 980,
      y: 292,
      middlewareData: {
        scaled: { scale: { x: 1, y: 1 }, column: 0, line: card.line(clear, clear.top) },
        held: { height: 200 },
      },
    });
  const place = (reading) => {
    const { fresh, hold } = card.choose(input);
    const edge = card.holding({ fresh, hold, ...reading });
    land();
    return edge;
  };
  const turn = (key, author) => ({ key, author });
  assert.equal(
    place({ transcript: 100, drafting: false, latest: turn("a", "agent") }),
    "top",
  );
  // The user starts a reply: its first line holds the top.
  assert.equal(
    place({
      transcript: 100,
      drafting: true,
      latest: turn("a", "agent"),
      draftText: "Hi",
    }),
    "top",
  );
  // An agent turn joins while they draft: the reply row holds, keyed to that turn.
  assert.equal(
    place({
      transcript: 160,
      drafting: true,
      latest: turn("b", "agent"),
      draftText: "Hi",
    }),
    "foot",
  );
  assert.equal(
    place({
      transcript: 160,
      drafting: true,
      latest: turn("b", "agent"),
      draftText: "Hi",
    }),
    "foot",
  );
  // A new edit releases it.
  assert.equal(
    place({
      transcript: 160,
      drafting: true,
      latest: turn("b", "agent"),
      draftText: "Hi!",
    }),
    "top",
  );
  assert.deepEqual(card.heldAt("top"), { top: -8 });
  assert.equal(card.heldHeight(), 200);
});

test("beside, a margin row is kept clear only where that leaves the card its whole measure", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  // A paragraph ending at 600, and a margin row 40px wide out past it.
  const clear = block(300, 300, 300, 500);
  const reference = (rowRight) => {
    const placement = commentPlacement();
    placement.choose({ clear, boundary, scroller: scroller(1000), coarse: false });
    return placement.options(ui, {
      clear,
      row: clear.top,
      margin: { left: rowRight - 40, right: rowRight },
      boundary,
      fit() {},
    }).reference;
  };
  // Past a row ending at 692, 592 remains to the boundary at 1292 after the gap: the
  // card keeps the row in view at no cost to its width.
  assert.equal(reference(692).right, 692);
  // A row ending 1px further would take that pixel from the card, so the card stands
  // over the row, beside the words.
  assert.equal(reference(693).right, clear.right);
});
