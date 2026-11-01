/* The side a comment's surfaces take, the comment box and the thread card alike.

   A 1300px-wide, 900px-tall window throughout, whose boundary runs from 8 to 1292 across
   and from 50 to 847 down, and a card whose minimum width is 320. */

import assert from "node:assert/strict";
import test from "node:test";

import {
  LEAST_HEIGHT,
  commentPlacement,
  commentReference,
  commentSide,
} from "/runtime/annotation-overlay/comment-placement.js";
import { floatingPlacement } from "/runtime/annotation-overlay/floating.js";

// The card's widths as base.css declares them, which the placement reads off the root.
document.documentElement.style.setProperty("--thread-card-min", "320px");
document.documentElement.style.setProperty("--thread-card", "592px");

// A window boundary, keyed by its edges as commentBoundary keys one, with no chrome
// beside any columns, so its room across them is itself.
const windowBoundary = (left, top, width, height) => {
  const boundary = Object.assign(new DOMRect(left, top, width, height), {
    cut: null,
    key: [left, top, left + width, top + height],
  });
  return Object.assign(boundary, { across: () => boundary });
};
const boundary = windowBoundary(8, 50, 1284, 797);
// A paragraph `width` wide from x = `left`, from y = `top` to `bottom`.
const block = (left, width, top, bottom) => new DOMRect(left, top, width, bottom - top);
// A page scrolled `scrollTop` into a document `height` tall, in an 850px scrollport.
const scroller = (scrollTop, height = 3000) => {
  const box = { scrollTop, scrollHeight: height, clientHeight: 850 };
  box.ownerDocument = { scrollingElement: box };
  return box;
};
// Floating UI's platform for a surface of `dimensions()` in the window, unscaled.
const windowPlatform = (dimensions) => ({
  getElementRects: ({ reference }) => ({
    reference: reference.getBoundingClientRect(),
    floating: { x: 0, y: 0, ...dimensions() },
  }),
  getOffsetParent: () => window,
  getDimensions: dimensions,
  getClippingRect: ({ rootBoundary }) => rootBoundary,
  convertOffsetParentRelativeRectToViewportRelativeRect: ({ rect }) => rect,
  isElement: () => false,
  getDocumentElement: () => document.documentElement,
  isRTL: () => false,
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
      scroller: scroller(1000),
      coarse: false,
    };
    const editor = commentPlacement();
    const original = editor.choose({ ...input, clear: unanchored ? null : clear });
    const box = new DOMRect(980, 317, 320, 160);
    const card = commentPlacement();
    card.adopt({ box, placement: editor.capture() });
    const opening = card.choose(input);
    assert.equal(opening.side, original.side);
    assert.equal(opening.fresh, false);
    assert.equal(opening.adopted, true);
    assert.equal(card.choose(input).adopted, true);

    const scrolled = block(300, 660, 200, 400);
    const reading = card.choose({ ...input, clear: scrolled, row: scrolled.top });
    assert.equal(reading.fresh, false);
    assert.equal(reading.adopted, true);
    card.landed({
      x: box.left,
      y: box.top - 100,
      middlewareData: {
        scaled: {
          scale: { x: 1, y: 1 },
          column: scrolled.right - 320,
          attachmentInline: scrolled.left,
          line: unanchored ? scrolled.bottom : scrolled.top,
        },
        held: { height: box.height },
      },
    });
    assert.equal(card.choose({ ...input, clear: scrolled }).adopted, false);

    const reflowed = block(300, 700, 200, 400);
    assert.equal(card.choose({ ...input, clear: reflowed }).fresh, true);
    card.adopt({ box, placement: editor.capture() });
    const resized = windowBoundary(8, 50, 1084, 797);
    const afterResize = card.choose({ ...input, boundary: resized });
    assert.equal(afterResize.fresh, true);
    assert.equal(afterResize.adopted, false);
  }
});

test("a page scroll that moves a region's shown bounds keeps the side", () => {
  // A region boundary is keyed by the region's whole size, so a scroll of the page that
  // moves and clips its shown bounds chooses no side afresh, while a resize does.
  const region = (top, height, size = [0, 0, 900, 600]) =>
    Object.assign(new DOMRect(100, top, 900, height), { cut: {}, key: size });
  const clear = block(120, 860, 300, 500);
  const input = {
    clear,
    row: clear.top,
    scroller: scroller(1000),
    coarse: false,
  };
  const card = commentPlacement();
  assert.equal(card.choose({ ...input, boundary: region(58, 597) }).fresh, true);
  // A placement superseded before it lands opened nothing, so the next is still
  // opening: a card opened as Floating UI first loads makes room clear of its target.
  // It keeps the side the first chose, so it is not fresh.
  const again = card.choose({ ...input, boundary: region(58, 597) });
  assert.deepEqual([again.fresh, again.opening], [false, true]);
  card.landed({
    x: clear.left,
    y: clear.bottom + 8,
    middlewareData: {
      scaled: {
        scale: { x: 1, y: 1 },
        column: clear.left,
        attachmentInline: clear.left,
        line: clear.bottom,
      },
      held: { height: 160 },
    },
  });
  const landed = card.choose({ ...input, boundary: region(50, 560) });
  assert.deepEqual([landed.fresh, landed.opening], [false, false]);
  assert.equal(
    card.choose({ ...input, boundary: region(50, 560, [0, 0, 900, 500]) }).fresh,
    true,
  );
});

test("beside, clearing a margin row never costs the card width", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  // A paragraph ending at 600, and a margin row 40px wide out past it.
  const clear = block(300, 300, 300, 500);
  const options = (rowRight) => {
    const placement = commentPlacement();
    const seat = placement.choose({
      clear,
      boundary,
      scroller: scroller(1000),
      coarse: false,
    });
    return seat.options(ui, {
      clear,
      row: clear.top,
      margin: { left: rowRight - 40, right: rowRight },
      boundary,
      fit() {},
    });
  };
  const reference = (rowRight) => options(rowRight).reference;
  // Exactly the preferred 592px remains beyond the row and the 8px gap.
  assert.equal(reference(692).right, 692);
  // Even one pixel of lost message width puts the card over the row.
  assert.equal(reference(693).right, clear.right);
  // A readable but narrower lane still gives its space back to the message.
  assert.equal(reference(964).right, clear.right);

  // 600 client pixels do not hold a 592 CSS-pixel card at 120% zoom.
  const zoomed = options(684);
  const state = {
    rects: { reference: { x: clear.left, y: clear.top } },
    elements: { floating: {} },
    platform: {
      getOffsetParent: () => window,
      convertOffsetParentRelativeRectToViewportRelativeRect: () => ({
        width: 1.2,
        height: 1.2,
      }),
    },
  };
  const reset = await zoomed.middleware[0].fn(state);
  assert.deepEqual(reset, { reset: { rects: true } });
  assert.equal(zoomed.reference.right, clear.right);
  const settled = await zoomed.middleware[0].fn(state);
  assert.equal(settled.reset, undefined);
  assert.deepEqual(settled.data.scale, { x: 1.2, y: 1.2 });

  // At 75%, the same 484 client-pixel lane holds the full 444px footprint.
  const smaller = options(800);
  const reduced = {
    ...state,
    platform: {
      ...state.platform,
      convertOffsetParentRelativeRectToViewportRelativeRect: () => ({
        width: 0.75,
        height: 0.75,
      }),
    },
  };
  assert.deepEqual(await smaller.middleware[0].fn(reduced), {
    reset: { rects: true },
  });
  assert.equal(smaller.reference.right, 800);
  assert.equal((await smaller.middleware[0].fn(reduced)).reset, undefined);
});

test("zoom clearance reaches the solver through the floating driver", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const clear = block(300, 300, 300, 500);
  for (const { scale, rowRight, expected } of [
    { scale: 1.2, rowRight: 684, expected: clear.right + 8 },
    { scale: 0.75, rowRight: 800, expected: 808 },
  ]) {
    const floating = document.createElement("div");
    document.body.append(floating);
    let width = 592;
    const referenceRights = [];
    const dimensions = () => ({ width, height: 100 });
    const toClient = ({ rect }) => ({
      x: rect.x * scale,
      y: rect.y * scale,
      width: rect.width * scale,
      height: rect.height * scale,
    });
    // The platform supplies measured geometry; the real solver owns reset, offset,
    // size and shift. Both application reference wrappers remain on the path.
    const platform = {
      getElementRects({ reference }) {
        const rect = reference.getBoundingClientRect();
        referenceRights.push(rect.right);
        return {
          reference: {
            x: rect.left / scale,
            y: rect.top / scale,
            width: rect.width / scale,
            height: rect.height / scale,
          },
          floating: { x: 0, y: 0, ...dimensions() },
        };
      },
      getOffsetParent: () => window,
      getDimensions: dimensions,
      getClippingRect: () => ({
        x: boundary.left,
        y: boundary.top,
        width: boundary.width,
        height: boundary.height,
      }),
      convertOffsetParentRelativeRectToViewportRelativeRect: toClient,
      isElement: () => false,
      getDocumentElement: () => document.documentElement,
      isRTL: () => false,
    };
    const rule = commentPlacement();
    const seat = rule.choose({
      clear,
      boundary,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware, plane } = seat.options(ui, {
      clear,
      row: clear.top,
      margin: { left: rowRight - 40, right: rowRight },
      boundary,
      fit: (room) => {
        width = Math.min(592, room.width);
      },
    });
    const driver = floatingPlacement({ floating, update() {} });
    driver.begin();
    const answer = await driver.position(
      ui.computePosition,
      commentReference(
        {
          element: null,
          contextNode: null,
          extent: clear,
          row: clear.top,
          geometry: { anchors: new Map() },
        },
        reference,
      ),
      { placement, middleware, platform },
      plane,
      null,
    );
    assert.ok(answer);
    assert.notEqual(referenceRights[0], expected - 8);
    assert.equal(referenceRights.at(-1), expected - 8);
    assert.ok(
      Math.abs(answer.x * scale - expected) < 0.01,
      `${scale}: ${answer.x * scale}`,
    );
    floating.remove();
  }
});

test("a carried surface stands where it was dropped, past the attachment limit", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const dimensions = () => ({ width: 320, height: 100 });
  const platform = windowPlatform(dimensions);
  // One line of words with the whole room right of it, which the surface stands beside,
  // and one across the window, which it stands under; each dropped well away from it.
  for (const { clear, dropped, side } of [
    {
      clear: block(300, 300, 300, 330),
      dropped: new DOMRect(700, 600, 320, 100),
      side: "right",
    },
    {
      clear: block(8, 1284, 400, 430),
      dropped: new DOMRect(500, 120, 320, 100),
      side: "bottom",
    },
  ]) {
    const stand = async (moved) => {
      const rule = commentPlacement();
      const input = { clear, boundary, scroller: scroller(1000), coarse: false };
      assert.equal(rule.choose(input).side, side);
      rule.adopt({ box: dropped, placement: { ...rule.capture(), moved } });
      const seat = rule.choose(input);
      assert.equal(seat.fresh, false);
      const { reference, placement, middleware } = seat.options(ui, {
        clear,
        row: clear.top,
        boundary,
        fit() {},
      });
      return ui.computePosition(
        { getBoundingClientRect: () => reference },
        document.body,
        { placement, middleware, platform, strategy: "fixed" },
      );
    };
    // Handed over by Send, a frame that far away is held back to its words.
    const handed = await stand(false);
    assert.notEqual(handed.y, dropped.top, side);
    // Carried there by the user, it stands where it was put, and holds the edge its
    // inline offset is measured from.
    const carried = await stand(true);
    assert.deepEqual([carried.x, carried.y], [dropped.left, dropped.top], side);
    assert.equal(carried.middlewareData.hold.inline, "left");
  }
});

test("held in at the window's foot, a card may grow back to the tallest it stood", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  let height = 300;
  const dimensions = () => ({ width: 320, height });
  const platform = windowPlatform(dimensions);
  // floating.js's own middleware, reduced to the height the landing reads.
  const held = { name: "held", fn: ({ rects }) => ({ data: rects.floating }) };
  const card = commentPlacement();
  // The height the last fit was told the card caps no lower than.
  let stood = null;
  // An element 700px down, `scrolled` further by a scroll of the page.
  const place = async (scrolled = 0) => {
    const clear = block(300, 300, 700 - scrolled, 730 - scrolled);
    const seat = card.choose({
      clear,
      boundary,
      scroller: scroller(1000),
      coarse: false,
    });
    const edge = "top";
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      row: clear.top,
      lastRow: clear.bottom,
      boundary,
      fit(room) {
        ({ stood } = room);
      },
      edge,
    });
    const answer = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      { placement, middleware: [...middleware, held], platform, strategy: "fixed" },
    );
    card.landed(answer);
    return answer.y;
  };
  // Too tall for the room under its line, it stands against the boundary's foot.
  assert.equal(await place(), boundary.bottom - 300);
  // Shrunk, as a rewrite opening over long words shrinks it, it falls back level with
  // its line, and may still grow back to the height it stood at.
  height = 150;
  assert.equal(await place(), 700 - 8);
  assert.equal(stood, 300);
  // Repeated fitting at the smaller size must not ratchet the growth room down.
  assert.equal(await place(), 700 - 8);
  assert.equal(stood, 300);
  height = 300;
  assert.equal(await place(), boundary.bottom - 300);
  // Once a scroll moves its line, from the first fit after it, it keeps only the
  // height it stands at.
  height = 150;
  await place();
  assert.equal(stood, 300);
  await place(10);
  assert.equal(stood, 150);
});

test("a rising card has the window's height and keeps the top it stood at", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  let height = 120;
  const platform = windowPlatform(() => ({ width: 320, height }));
  const held = { name: "held", fn: ({ rects }) => ({ data: rects.floating }) };
  const card = commentPlacement();
  // The height the last fit offered the card.
  let room = null;
  // An element 700px down, with 155px of room under the card's line.
  const clear = block(300, 300, 700, 730);
  const place = async (rises = false) => {
    const seat = card.choose({
      clear,
      boundary,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      row: clear.top,
      lastRow: clear.bottom,
      boundary,
      fit(offered) {
        room = offered.height;
      },
      edge: "top",
      rises,
    });
    const answer = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      { placement, middleware: [...middleware, held], platform, strategy: "fixed" },
    );
    card.landed(answer);
    return answer.y;
  };
  await place();
  // Holding its top, a card is offered the room below it.
  height = 150;
  assert.equal(await place(), 692);
  assert.equal(room, boundary.bottom - 692);
  // Rising, it is offered the window's height, and the boundary lifts it.
  height = 400;
  assert.equal(await place(true), boundary.bottom - 400);
  assert.equal(room, boundary.height);
  // Shorter again, it comes back down to the top it held.
  height = 150;
  assert.equal(await place(true), 692);
});

test("chrome beside a card's columns leaves it the window's height", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 700 }));
  // A row like the floating panel's stands under the columns left of 600, so a card
  // reaching over them has 45px less room than the window's foot.
  const whole = windowBoundary(8, 50, 1284, 842);
  const rowed = Object.assign(windowBoundary(8, 50, 1284, 797), {
    across: ({ left }) => (left < 600 ? rowed : whole),
  });
  const placed = async (clear) => {
    const card = commentPlacement();
    const seat = card.choose({
      clear,
      boundary: rowed,
      scroller: scroller(1000),
      coarse: false,
    });
    let offered = null;
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      row: clear.top,
      boundary: rowed,
      fit: ({ room }) => (offered = room),
      rises: true,
    });
    const { x, y } = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      { placement, middleware, platform, strategy: "fixed" },
    );
    return { x, foot: y + 700, room: offered };
  };
  // Beside words that end at 600, the card stands in the margin, past the row.
  const margin = await placed(block(100, 500, 300, 330));
  assert.equal(margin.x, 608);
  assert.equal(margin.room, whole);
  assert.equal(margin.foot, whole.bottom);
  // Beside words that end at 500, it reaches over the row's columns and stops above it.
  const over = await placed(block(100, 400, 300, 330));
  assert.equal(over.room, rowed);
  assert.equal(over.foot, rowed.bottom);
});
