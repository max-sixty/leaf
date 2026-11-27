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
} from "/runtime/annotations/annotation-overlay/comment-placement.js";
import { floatingPlacement } from "/runtime/annotations/annotation-overlay/floating.js";

// The card's widths, as tokens.css declares them, which the placement reads off the
// root.
document.documentElement.style.setProperty("--lf-thread-card-min", "320px");
document.documentElement.style.setProperty("--lf-thread-card", "592px");
// The room the marks round a paragraph take past it on each side, their gap and band,
// as the attachment reads it (dom/geometry.js, `markedBox`).
const paragraph = { left: 8, top: 8, right: 8, bottom: 8 };

// A window boundary, keyed by its edges as commentBoundary keys one, with no chrome
// beside any columns, so its room across them is itself, and the window holds it.
const windowBoundary = (left, top, width, height) => {
  const boundary = Object.assign(new DOMRect(left, top, width, height), {
    cut: null,
    holders: { top: null, bottom: null },
    key: [left, top, left + width, top + height],
  });
  return Object.assign(boundary, { across: () => boundary });
};
const boundary = windowBoundary(8, 50, 1284, 797);
// A paragraph `width` wide from x = `left`, from y = `top` to `bottom`.
const block = (left, width, top, bottom) => new DOMRect(left, top, width, bottom - top);
// The element a surface is about, which no sticky box holds, so a scroll of the page
// carries it the whole way.
const subject = document.body.appendChild(document.createElement("p"));
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
    room: paragraph,
    extent: clear,
    boundary,
    width: 320,
    element: subject,
    scroller: scroller(scrolled, document),
    coarse,
  });

test("beside needs room for the card, not only the box", () => {
  // 336px right of the paragraph holds the card's 320 and its 16 from the words: beside.
  assert.equal(side(block(300, 656, 300, 500)), "right");
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
  // boundary's foot, less the card's 16 from the words, less the paragraph's foot.
  const under = (room) => block(40, 1240, 847 - 16 - room - 200, 847 - 16 - room);
  assert.equal(side(under(LEAST_HEIGHT), { scrolled: 2150 }), "top");
  assert.equal(side(under(LEAST_HEIGHT), { scrolled: 2150, coarse: true }), "bottom");
  assert.equal(side(under(LEAST_HEIGHT - 1), { scrolled: 2150, coarse: true }), "top");
});

test("a submitted frame survives supersession until it lands, then follows scroll but not reflow", () => {
  for (const unanchored of [false, true]) {
    const clear = block(300, 660, 300, 500);
    const input = {
      clear,
      room: paragraph,
      boundary,
      row: clear.top,
      element: subject,
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
    room: paragraph,
    row: clear.top,
    element: subject,
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
      room: paragraph,
      boundary,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    return seat.options(ui, {
      clear,
      room: paragraph,
      row: clear.top,
      margin: { left: rowRight - 40, right: rowRight },
      boundary,
      fit() {},
    });
  };
  const reference = (rowRight) => options(rowRight).reference;
  // Exactly the preferred 592px remains beyond the row and the 16px gap.
  assert.equal(reference(684).right, 684);
  // Even one pixel of lost message width puts the card over the row.
  assert.equal(reference(685).right, clear.right);
  // A readable but narrower lane still gives its space back to the message.
  assert.equal(reference(964).right, clear.right);

  // 600 client pixels do not hold a 592 CSS-pixel card at 120% zoom.
  const zoomed = options(676);
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

  // At 75%, a 476 client-pixel lane holds the full 444px footprint.
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
    { scale: 1.2, rowRight: 676, expected: clear.right + 16 },
    { scale: 0.75, rowRight: 800, expected: 816 },
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
      room: paragraph,
      boundary,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware, plane } = seat.options(ui, {
      clear,
      room: paragraph,
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
    assert.notEqual(referenceRights[0], expected - 16);
    assert.equal(referenceRights.at(-1), expected - 16);
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
      const input = {
        clear,
        boundary,
        element: subject,
        scroller: scroller(1000),
        coarse: false,
      };
      assert.equal(rule.choose(input).side, side);
      rule.adopt({ box: dropped, placement: { ...rule.capture(), moved } });
      const seat = rule.choose(input);
      assert.equal(seat.fresh, false);
      const { reference, placement, middleware } = seat.options(ui, {
        clear,
        room: paragraph,
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
      room: paragraph,
      boundary,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      room: paragraph,
      row: clear.top,
      lastRow: clear.bottom,
      boundary,
      fit(room) {
        ({ stood } = room);
      },
      keeps: "top",
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
      room: paragraph,
      boundary,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      room: paragraph,
      row: clear.top,
      lastRow: clear.bottom,
      boundary,
      fit(offered) {
        room = offered.height;
      },
      keeps: "top",
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

test("a card keeping a line of its own grows up over it and down under it", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  // What stands over the card's own line, as its transcript does, and under it, as its
  // reply box does.
  let over = 200;
  let under = 40;
  const platform = windowPlatform(() => ({ width: 320, height: over + under }));
  const held = { name: "held", fn: ({ rects }) => ({ data: rects.floating }) };
  const card = commentPlacement();
  // What the last fit offered the card, and the height it caps no lower than.
  let room = null;
  let stood = null;
  // A tall element 400px down, `scrolled` further by a scroll of the page. With
  // `stoodAt`, the solve is floating.js's for the card at that height, the one it last
  // stood at, which names itself ahead of the card's middleware (`position`).
  const place = async (keeps, scrolled = 0, stoodAt = null) => {
    const clear = block(300, 300, 400 - scrolled, 2000 - scrolled);
    const seat = card.choose({
      clear,
      room: paragraph,
      boundary,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      room: paragraph,
      row: clear.top,
      lastRow: clear.bottom,
      boundary,
      fit(offered) {
        ({ height: room, stood } = offered);
      },
      keeps,
      under: () => under,
    });
    const answer = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      {
        placement,
        middleware: [
          ...(stoodAt ? [{ name: "stood", fn: () => ({}) }] : []),
          ...middleware,
          held,
        ],
        platform: stoodAt
          ? windowPlatform(() => ({ width: 320, height: stoodAt }))
          : platform,
        strategy: "fixed",
      },
    );
    if (!stoodAt) card.landed(answer);
    return answer.y;
  };
  // Read, it keeps its top, level with its row.
  assert.equal(await place("top"), 392);
  // A line the draft gains stands under the line: the top stays and the foot drops.
  // The card is offered the room over its line and what stands under it.
  under = 61;
  assert.equal(await place("line"), 392);
  assert.equal(room, 392 + 200 + 61 - boundary.top);
  // A turn joining the transcript stands over the line, and lifts the top by its height.
  over = 300;
  assert.equal(await place("line"), 292);
  // A line taken from the draft lifts the foot again.
  under = 40;
  assert.equal(await place("line"), 292);
  // Solved for the size it stood at, it stands where it landed, whatever is under its
  // line now (floating.js, `position`).
  under = 82;
  assert.equal(await place("line", 0, 300 + 40), 292);
  under = 40;
  // A scroll carries its rule's top past the window's head, which holds it in. A line
  // the draft gains there may still grow it, by as much as stands under its line.
  assert.equal(await place("line", 500), boundary.top);
  under = 61;
  assert.equal(await place("line", 500), boundary.top);
  assert.equal(stood, 300 + 61);
  // Filling the room, it may not outgrow it: a line the draft gains there takes its
  // room from what stands over the line, at this placement and the next.
  over = boundary.height - 61;
  await place("line", 500);
  for (const lines of [82, 103]) {
    over = boundary.height - lines;
    under = lines;
    assert.equal(await place("line", 500), boundary.top);
    assert.equal(Math.max(room, stood), boundary.height);
  }
});

test("a surface with no subject keeps the room's gap, not a mark's", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  const card = commentPlacement();
  const seat = card.choose({
    clear: null,
    boundary,
    element: subject,
    scroller: scroller(1000),
    coarse: false,
  });
  const { reference, placement, middleware } = seat.options(ui, {
    clear: null,
    row: boundary.top,
    boundary,
    fit() {},
  });
  const answer = await ui.computePosition(
    { getBoundingClientRect: () => reference },
    document.body,
    { placement, middleware, platform, strategy: "fixed" },
  );
  assert.equal(answer.y, boundary.top + 8);
});

test("a surface stands by the edge facing its subject, or the end of its place nearer it", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  // The side a surface on `clear` takes, quoting words that start at `column` and read
  // in `direction`, the inline edge it is held by and widens away from, and where its
  // left edge lands.
  const stands = async (clear, column = null, direction = "ltr") => {
    const surface = commentPlacement();
    const seat = surface.choose({
      clear,
      room: paragraph,
      column,
      boundary,
      element: subject,
      scroller: scroller(100),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      room: paragraph,
      row: clear?.top ?? boundary.top,
      column,
      direction,
      boundary,
      fit() {},
    });
    const answer = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      { placement, middleware, platform, strategy: "fixed" },
    );
    return [seat.side, surface.capture().holds, Math.round(answer.x)];
  };
  assert.deepEqual((await stands(block(300, 656, 300, 500))).slice(0, 2), [
    "right",
    "left",
  ]);
  // Left of its words it holds the edge beside them.
  assert.deepEqual((await stands(block(400, 880, 300, 500))).slice(0, 2), [
    "left",
    "right",
  ]);
  // Under or over, its place is the measure's 592px from the quoted words, or from
  // 700, where the measure meets the room's right edge at 1292.
  const wide = block(40, 1240, 500, 700);
  assert.deepEqual(await stands(wide, 100), ["bottom", "left", 100]);
  // Words 200px into that place are nearer its start, so it stands there and still
  // reaches them.
  assert.deepEqual(await stands(wide, 900), ["bottom", "left", 700]);
  // Words 400px in are nearer its end: it stands against the room's edge.
  assert.deepEqual(await stands(wide, 1100), ["bottom", "right", 972]);
  // Right-to-left words starting at 900 read leftward, so the place ends there and
  // the box stands at that end, its right edge at their first character.
  assert.deepEqual(await stands(wide, 900, "rtl"), ["bottom", "right", 580]);
  // Starting 200px from the room's left edge, they are nearer the start of a place
  // the room holds there.
  assert.deepEqual(await stands(wide, 208, "rtl"), ["bottom", "left", 8]);
  // On the whole paragraph it ends at the paragraph's right edge.
  assert.deepEqual(await stands(wide), ["bottom", "right", 960]);
  // With nothing to stand by, it starts at the room's edge.
  assert.deepEqual(await stands(null), ["bottom", "left", 8]);
});

test("a surface under words near a line's end crosses a sideways scroll with them", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  // floating.js's own middleware, reduced to the width the landing reads.
  const held = { name: "held", fn: ({ rects }) => ({ data: rects.floating }) };
  const box = commentPlacement();
  // Words starting at `column`, in a log starting at `left` that a sideways scroll
  // moves them in, or that moves with them where a box around it scrolls.
  const place = async (column, left = 40) => {
    const wide = block(left, 1240, 500, 700);
    const seat = box.choose({
      clear: wide,
      room: paragraph,
      column,
      boundary,
      element: subject,
      scroller: scroller(100),
      coarse: false,
    });
    const { reference, placement, middleware } = seat.options(ui, {
      clear: wide,
      room: paragraph,
      row: wide.top,
      column,
      boundary,
      fit() {},
    });
    const answer = await ui.computePosition(
      { getBoundingClientRect: () => reference },
      document.body,
      { placement, middleware: [...middleware, held], platform, strategy: "fixed" },
    );
    box.landed(answer);
    return Math.round(answer.x);
  };
  // Words 1100px in stand the box against the room's right edge, its place held 192px
  // short of them by the room.
  assert.equal(await place(1100), 972);
  // A scroll carrying the words 200px left carries the box 200px with them.
  assert.equal(await place(900), 772);
  // Scrolled back, it returns to where it stood.
  assert.equal(await place(1100), 972);
  // A box around the log scrolling it 200px left carries the box the same 200px.
  assert.equal(await place(900, -160), 772);
});

test("the card Send opens holds the edge its comment box held", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  const wide = block(40, 1240, 500, 700);
  // The box stood by its right edge, 1092px in, with its quoted words 200px further
  // left than where it was placed. The same task's sideways scroll carried the words to
  // 900px, nearer their place's start, where a fresh choice would hold the left edge
  // at 700px, and the place's right end stands at the room's edge, 1292px.
  const card = commentPlacement();
  card.adopt({
    box: new DOMRect(772, 716, 320, 120),
    placement: { side: "bottom", boundary: boundary.key, moved: false, holds: "right" },
  });
  const seat = card.choose({
    clear: wide,
    room: paragraph,
    column: 900,
    boundary,
    element: subject,
    scroller: scroller(100),
    coarse: false,
  });
  const { reference, placement, middleware } = seat.options(ui, {
    clear: wide,
    room: paragraph,
    row: wide.top,
    column: 900,
    boundary,
    fit() {},
  });
  const answer = await ui.computePosition(
    { getBoundingClientRect: () => reference },
    document.body,
    { placement, middleware, platform, strategy: "fixed" },
  );
  assert.equal(card.capture().holds, "right");
  assert.equal(Math.round(answer.x), 772);
});

test("a carried surface whose words scrolled past the room is no wider than the room", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  const wide = block(40, 1240, 500, 700);
  // Dropped 400px left of words 900px in, which a sideways scroll then carried 1200px
  // further left, past the room's left edge.
  const surface = commentPlacement();
  surface.adopt({
    box: new DOMRect(500, 716, 320, 120),
    placement: { side: "bottom", boundary: boundary.key, moved: true, holds: "left" },
  });
  surface.choose({
    clear: wide,
    room: paragraph,
    column: 900,
    boundary,
    element: subject,
    scroller: scroller(100),
    coarse: false,
  });
  const seat = surface.choose({
    clear: wide,
    room: paragraph,
    column: -300,
    boundary,
    element: subject,
    scroller: scroller(100),
    coarse: false,
  });
  let width = null;
  const { reference, placement, middleware } = seat.options(ui, {
    clear: wide,
    room: paragraph,
    row: wide.top,
    column: -300,
    boundary,
    fit(room) {
      ({ width } = room);
    },
  });
  await ui.computePosition({ getBoundingClientRect: () => reference }, document.body, {
    placement,
    middleware,
    platform,
    strategy: "fixed",
  });
  assert.ok(width !== null && width <= boundary.width, String(width));
});

test("a surface carried left of its subject widens away from the left edge it holds", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 120 }));
  // Words from 600px to 1280px leave room only on their left, where the box stood until
  // the reader carried it by its grip against the room's left edge.
  const words = block(600, 680, 300, 400);
  const surface = commentPlacement();
  surface.adopt({
    box: new DOMRect(8, 300, 320, 120),
    placement: { side: "left", boundary: boundary.key, moved: true, holds: "left" },
  });
  const seat = surface.choose({
    clear: words,
    room: paragraph,
    boundary,
    element: subject,
    scroller: scroller(100),
    coarse: false,
  });
  let width = null;
  const { reference, placement, middleware } = seat.options(ui, {
    clear: words,
    room: paragraph,
    row: words.top,
    boundary,
    fit(room) {
      ({ width } = room);
    },
  });
  await ui.computePosition({ getBoundingClientRect: () => reference }, document.body, {
    placement,
    middleware,
    platform,
    strategy: "fixed",
  });
  assert.equal(width, boundary.right - 8);
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
      room: paragraph,
      boundary: rowed,
      element: subject,
      scroller: scroller(1000),
      coarse: false,
    });
    let offered = null;
    const { reference, placement, middleware } = seat.options(ui, {
      clear,
      room: paragraph,
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
  assert.equal(margin.x, 616);
  assert.equal(margin.room, whole);
  assert.equal(margin.foot, whole.bottom);
  // Beside words that end at 500, it reaches over the row's columns and stops above it.
  const over = await placed(block(100, 400, 300, 330));
  assert.equal(over.room, rowed);
  assert.equal(over.foot, rowed.bottom);
});

test("a surface stands clear of chrome across the columns it may widen into", async () => {
  const ui = await import("/vendor/floating-ui.esm.js");
  const platform = windowPlatform(() => ({ width: 320, height: 700 }));
  // A panel like the floating panel stands at the window's foot right of 800. A surface
  // 320px wide right of words ending at 400 stops short of it, but widening with its
  // words to the measure would take it over the panel.
  const whole = windowBoundary(8, 50, 1284, 842);
  const paneled = Object.assign(windowBoundary(8, 50, 1284, 700), {
    across: ({ right }) => (right > 800 ? paneled : whole),
  });
  const surface = commentPlacement();
  const clear = block(100, 300, 300, 330);
  const seat = surface.choose({
    clear,
    room: paragraph,
    boundary: paneled,
    element: subject,
    scroller: scroller(1000),
    coarse: false,
  });
  let offered = null;
  const { reference, placement, middleware } = seat.options(ui, {
    clear,
    room: paragraph,
    row: clear.top,
    boundary: paneled,
    fit: ({ room }) => (offered = room),
    rises: true,
  });
  const { x, y } = await ui.computePosition(
    { getBoundingClientRect: () => reference },
    document.body,
    { placement, middleware, platform, strategy: "fixed" },
  );
  assert.equal(x, 416);
  assert.equal(offered, paneled);
  assert.equal(y + 700, paneled.bottom);
});
