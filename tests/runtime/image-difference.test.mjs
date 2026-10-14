/* Where two images differ: which pixels count, what each frame of a pair outlines, and
   the words that sum it up. */

import assert from "node:assert/strict";
import { test } from "node:test";

import {
  changedPixels,
  describeDifference,
  differingRegions,
} from "/runtime/image-difference.js";

// A blank opaque image, and a copy with the given rectangles repainted.
const blank = (width, height) => ({
  width,
  height,
  data: new Uint8ClampedArray(width * height * 4).fill(255),
});
// A page: a blank image with a column of short lines down its right edge that every
// pair here keeps, as the rest of a real page stays when one part of it changes.
const page = (width, height) =>
  painted(
    blank(width, height),
    ...Array.from({ length: 8 }, (_, i) => [
      width - 30,
      4 + i * 12,
      20 + (i % 3) * 2,
      6,
    ]),
  );
// `value` is what the rectangle's one channel is set to; the default paints it black,
// far enough to draw, and a rectangle under LINE (40) pixels on each side reads as a
// mark, as text does.
const painted = (image, ...rects) => {
  const copy = { ...image, data: image.data.slice() };
  for (const [x, y, width, height, channel, value = 0] of rects)
    for (let row = y; row < y + height; row += 1)
      for (let column = x; column < x + width; column += 1)
        for (const c of channel === undefined ? [0, 1, 2] : [channel])
          copy.data[(row * image.width + column) * 4 + c] = value;
  return copy;
};
// An outline holds the pixels on both sides of its content's edges, so it stands one
// pixel outside what was painted.
const outlines = (reading, side) =>
  reading.regions
    .filter((region) => region.side === side)
    .map(({ x, y, width, height, kind }) => ({ x, y, width, height, kind }));

test("identical images differ nowhere", async () => {
  const image = painted(blank(64, 48), [10, 10, 20, 8]);
  assert.deepEqual(await differingRegions(image, image), {
    width: 64,
    height: 48,
    changed: 0,
    throughout: false,
    regions: [],
  });
});

test("one level in any one channel, alpha included, is a change", async () => {
  const image = blank(40, 40);
  for (const channel of [0, 1, 2, 3])
    assert.equal(
      (await differingRegions(image, painted(image, [5, 6, 1, 1, channel, 254])))
        .changed,
      1,
    );
});

test("a pixel moved 48 levels is outlined, and none moved less is", async () => {
  const image = painted(page(200, 100), [10, 10, 20, 10], [120, 60, 20, 10]);
  const slight = await differingRegions(
    image,
    painted(image, [10, 10, 20, 10, undefined, 47]),
  );
  assert.equal(describeDifference(slight), "only slight changes");
  const strong = await differingRegions(
    image,
    painted(image, [120, 60, 20, 10, undefined, 48]),
  );
  assert.deepEqual(outlines(strong, "before"), [
    { x: 119, y: 59, width: 22, height: 12, kind: "changed" },
  ]);
  assert.deepEqual(outlines(strong, "after"), outlines(strong, "before"));
});

test("the changed-pixel masks are opaque where a pixel moved far, faint where slight, clear elsewhere", () => {
  // The after image is two rows taller, as a page that grew is.
  const after = painted(blank(20, 12), [2, 2, 1, 1, 0, 0], [5, 5, 1, 1, 0, 230]);
  const masks = changedPixels(blank(20, 10), after);
  const { width, height } = masks;
  const alpha = (mask, x, y) => masks[mask][(y * width + x) * 4 + 3];
  assert.deepEqual([width, height], [20, 12]);
  assert.equal(alpha("after", 2, 2), 255);
  // A slight shift, as a redrawn shadow is, draws nothing in either image, and shows
  // faintly: 25 levels of the 96 that make a pixel opaque.
  assert.equal(alpha("both", 5, 5), Math.round(40 + (215 * 25) / 96));
  assert.equal(alpha("after", 9, 9) + alpha("before", 9, 9) + alpha("both", 9, 9), 0);
  // A row only the taller image has changed throughout, and is that image's.
  assert.equal(alpha("after", 9, 11), 255);
});

test("a mark that moved is in the before mask where it was and the after mask where it went", () => {
  const read = (was, went) => {
    const masks = changedPixels(was, went);
    return (mask, x, y) => masks[mask][(y * masks.width + x) * 4 + 3];
  };
  const was = painted(blank(40, 20), [4, 4, 6, 6]);
  const went = painted(blank(40, 20), [24, 8, 6, 6]);
  let alpha = read(was, went);
  assert.deepEqual([alpha("before", 6, 6), alpha("after", 6, 6)], [255, 0]);
  assert.deepEqual([alpha("before", 26, 10), alpha("after", 26, 10)], [0, 255]);
  // On a dark ground the light mark is the one drawn.
  const dark = (image) => ({
    ...image,
    data: image.data.map((v, i) => (i % 4 === 3 ? v : 255 - v)),
  });
  alpha = read(dark(was), dark(went));
  assert.deepEqual([alpha("before", 6, 6), alpha("after", 26, 10)], [255, 255]);
  // The ground is the mark's own surroundings, not the image's commonest colour: a
  // light panel on a mostly dark page.
  const panel = painted(blank(80, 20), [0, 0, 80, 20], [2, 2, 32, 14, undefined, 255]);
  const onPanel = (rect) => painted(panel, rect);
  alpha = read(onPanel([4, 4, 6, 6]), onPanel([20, 8, 6, 6]));
  assert.deepEqual([alpha("before", 6, 6), alpha("after", 22, 10)], [255, 255]);
  // A mark one pixel inside the panel's edge stands on the panel too.
  alpha = read(onPanel([3, 3, 2, 2]), onPanel([20, 8, 2, 2]));
  assert.deepEqual([alpha("before", 3, 3), alpha("after", 20, 8)], [255, 255]);
});

test("a mark recoloured in place is in the both mask", () => {
  const red = painted(blank(20, 20), [4, 4, 6, 6, 1, 0], [4, 4, 6, 6, 2, 0]);
  const blue = painted(blank(20, 20), [4, 4, 6, 6, 0, 0], [4, 4, 6, 6, 1, 0]);
  const masks = changedPixels(red, blue);
  const at = (mask) => masks[mask][(6 * masks.width + 6) * 4 + 3];
  assert.deepEqual([at("before"), at("after"), at("both")], [0, 0, 255]);
});

test("a run with only what it encloses unchanged stands on no ground, in the both mask", () => {
  // The whole image recoloured, and the same with one pixel inside it kept: the kept
  // pixel is inside the run, not around it.
  const white = blank(5, 5);
  const black = painted(white, [0, 0, 5, 5]);
  const kept = painted(white, [2, 2, 1, 1]);
  for (const [was, went] of [
    [white, black],
    [kept, black],
    [black, kept],
  ]) {
    const masks = changedPixels(was, went);
    const at = (mask) => masks[mask][3];
    assert.deepEqual([at("before"), at("after"), at("both")], [0, 0, 255]);
  }
});

test("a mark spanning the frame stands on the ground left in its corners", () => {
  // A cross from edge to edge: the corners it leaves are ground joined to the edge.
  const white = blank(5, 5);
  const cross = painted(white, [2, 0, 1, 5], [0, 2, 5, 1]);
  const at = (masks, mask) => masks[mask][(0 * 5 + 2) * 4 + 3];
  const added = changedPixels(white, cross);
  const removed = changedPixels(cross, white);
  assert.deepEqual(
    [at(added, "after"), at(removed, "before"), at(added, "both")],
    [255, 255, 0],
  );
});

test("content that changed in place is outlined in both frames, whole", async () => {
  // A word becomes a longer word; the line beside it stays.
  const line = painted(page(300, 100), [200, 20, 30, 10]);
  const before = painted(line, [20, 20, 30, 10]);
  const after = painted(line, [20, 20, 50, 10]);
  const reading = await differingRegions(before, after);
  assert.deepEqual(outlines(reading, "before"), [
    { x: 19, y: 19, width: 32, height: 12, kind: "changed" },
  ]);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 19, y: 19, width: 52, height: 12, kind: "changed" },
  ]);
  assert.equal(describeDifference(reading), "1 changed area");
});

test("content pushed down by what grew above it moved, and is outlined where it is", async () => {
  // A paragraph grows by a line, and the one below it is pushed down unchanged.
  const column = page(200, 200);
  const before = painted(column, [20, 20, 30, 10], [20, 60, 24, 10], [60, 60, 12, 10]);
  const after = painted(
    column,
    [20, 20, 30, 10],
    [20, 34, 20, 10],
    [20, 80, 24, 10],
    [60, 80, 12, 10],
  );
  const reading = await differingRegions(before, after);
  // Nothing changed where the paragraph was, so before marks only the move.
  assert.deepEqual(outlines(reading, "before"), [
    { x: 19, y: 59, width: 54, height: 12, kind: "moved" },
  ]);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 19, y: 19, width: 32, height: 26, kind: "changed" },
    { x: 19, y: 79, width: 54, height: 12, kind: "moved" },
  ]);
  assert.equal(describeDifference(reading), "1 changed area, 1 moved");
});

test("content moved across the page marks nothing at the place it left", async () => {
  // A list moves from under a chart to beside it.
  const chart = painted(page(400, 300), [20, 20, 200, 120, undefined, 120]);
  const list = (x, y) => [
    [x, y, 30, 10],
    [x, y + 20, 26, 10],
    [x, y + 40, 34, 10],
  ];
  const reading = await differingRegions(
    painted(chart, ...list(20, 180)),
    painted(chart, ...list(250, 20)),
  );
  assert.deepEqual(outlines(reading, "before"), [
    { x: 19, y: 179, width: 36, height: 52, kind: "moved" },
  ]);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 249, y: 19, width: 36, height: 52, kind: "moved" },
  ]);
  assert.equal(describeDifference(reading), "1 area moved");
});

test("rounded frames do not join neighbouring text into a changed container", async () => {
  // The curve has non-line edge pixels, but the border is not a paragraph. A frame
  // near static text used to join it, then fragment the moving frame into changes.
  const framed = (x) => {
    const image = painted(
      blank(360, 180),
      [x, 20, 140, 50],
      [x + 2, 22, 136, 46, undefined, 255],
      ...[
        [0, 0],
        [138, 0],
        [0, 48],
        [138, 48],
      ].map(([dx, dy]) => [x + dx, 20 + dy, 2, 2, undefined, 255]),
      [x + 12, 34, 20, 10],
      [x + 44, 34, 18, 10],
      ...Array.from({ length: 4 }, (_, i) => [20 + i * 25, 78, 18, 10]),
    );
    return image;
  };
  const reading = await differingRegions(framed(20), framed(60));
  assert.deepEqual(outlines(reading, "before"), [
    { x: 31, y: 33, width: 52, height: 12, kind: "moved" },
  ]);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 71, y: 33, width: 52, height: 12, kind: "moved" },
  ]);
  assert.equal(describeDifference(reading), "1 area moved");
});

test("a card that only shrank is outlined between its two edges, not whole", async () => {
  // A panel loses its empty room below unchanged contents. Its contents are the same
  // blocks in both frames, so the card gives way to them like any other container.
  // A faint rule under it follows it up, so the card's old sides, a grey near the
  // rule's, cross where the rule now stands: the ground beside the rule changed there,
  // which is the card's change, not the rule's.
  const card = (height) =>
    painted(
      blank(300, 220),
      [20, 20, 200, height, undefined, 200],
      [22, 22, 196, height - 4, undefined, 255],
      [40, 40, 30, 10],
      [80, 40, 24, 10],
      [40, 60, 50, 10],
      [0, 30 + height, 300, 2, undefined, 225],
    );
  const reading = await differingRegions(card(150), card(100));
  assert.deepEqual(outlines(reading, "before"), [
    { x: 20, y: 116, width: 200, height: 55, kind: "changed" },
  ]);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 20, y: 116, width: 200, height: 5, kind: "changed" },
  ]);
  assert.equal(describeDifference(reading), "1 changed area");
});

test("a rule drawn in the image's commonest colour still changes where it is drawn", async () => {
  // A black rule on a white band of a black page: the rule's own colour is the page's
  // ground, but not the band's it stands on.
  const band = painted(
    blank(300, 200),
    [0, 0, 300, 200, undefined, 0],
    [0, 20, 300, 80, undefined, 255],
  );
  const reading = await differingRegions(
    painted(band, [0, 60, 300, 2, undefined, 0]),
    painted(band, [0, 60, 300, 2, undefined, 120]),
  );
  assert.deepEqual(outlines(reading, "before"), outlines(reading, "after"));
  assert.equal(outlines(reading, "before").length, 1);
});

test("crowded changes consolidate nearby fragments while a distant edit stays separate", async () => {
  // Adjacent fragments of the same hunk once kept separate outlines around line
  // numbers and individual words. The same two fragments merit separate attention
  // in a sparse comparison, but less ink when there are many places to inspect.
  for (const scale of [1, 2, 3]) {
    const pair = [
      [20, 20, 12, 10],
      [51, 49, 12, 10],
    ];
    const clutter = Array.from({ length: 22 }, (_, i) => [
      100 + (i % 8) * 30,
      20 + Math.floor(i / 8) * 30,
      12,
      10,
    ]);
    const remote = [500, 300, 12, 10];
    const compare = (rects) => {
      const source = blank(600 * scale, 400 * scale);
      const boxes = rects.map((rect) => rect.map((value) => value * scale));
      return differingRegions(
        painted(source, ...boxes),
        painted(source, ...boxes.map((rect) => [...rect, undefined, 100])),
      );
    };
    const sparse = outlines(await compare(pair), "after");
    assert.equal(sparse.length, 2);
    const dense = outlines(await compare([...pair, ...clutter, remote]), "after");
    assert.ok(dense.length < 8, JSON.stringify(dense));
    assert.ok(
      dense.some(
        (box) =>
          box.x <= pair[0][0] * scale &&
          box.x + box.width >= (pair[1][0] + pair[1][2]) * scale &&
          box.y <= pair[0][1] * scale &&
          box.y + box.height >= (pair[1][1] + pair[1][3]) * scale,
      ),
      "the same two nearby fragments should share an outline under clutter",
    );
    const isolated = dense.filter((box) => box.x > 450 * scale);
    assert.equal(isolated.length, 1);
    assert.ok(isolated[0].width < 20 * scale && isolated[0].height < 20 * scale);
  }
});

test("joining an L-shaped change does not absorb an island in its empty interior", async () => {
  const rectangles = [
    [20, 20, 200, 10],
    [20, 45, 10, 200],
    [180, 180, 12, 10],
    ...Array.from({ length: 100 }, (_, i) => [
      400 + (i % 20) * 58,
      20 + Math.floor(i / 20) * 58,
      12,
      10,
    ]),
  ];
  const source = blank(1600, 400);
  const reading = await differingRegions(
    painted(source, ...rectangles),
    painted(source, ...rectangles.map((rect) => [...rect, undefined, 100])),
  );
  assert.ok(
    outlines(reading, "after").some(
      (box) => box.x === 179 && box.y === 179 && box.width === 14 && box.height === 12,
    ),
  );
});

test("thin changed marks join when their drawn outlines touch", async () => {
  const source = blank(100, 80);
  const rectangles = [
    [20, 20, 10, 2],
    [38, 20, 10, 2],
  ];
  const reading = await differingRegions(
    painted(source, ...rectangles),
    painted(source, ...rectangles.map((rect) => [...rect, undefined, 100])),
  );
  assert.deepEqual(outlines(reading, "after"), [
    { x: 19, y: 19, width: 30, height: 4, kind: "changed" },
  ]);
});

test("fixed edge padding does not change grouping at different capture densities", async () => {
  for (const scale of [1, 2, 3]) {
    const source = blank(200 * scale, 100 * scale);
    const rectangles = [
      [20, 20, 12, 10],
      [55, 20, 12, 10],
    ].map((rect) => rect.map((value) => value * scale));
    const reading = await differingRegions(
      painted(source, ...rectangles),
      painted(source, ...rectangles.map((rect) => [...rect, undefined, 100])),
    );
    assert.equal(outlines(reading, "after").length, 2);
  }
});

test("rows only the taller image has are a change, though they draw nothing", async () => {
  const reading = await differingRegions(blank(64, 40), blank(64, 60));
  assert.equal(reading.changed, 64 * 20);
  assert.deepEqual(outlines(reading, "before"), []);
  assert.deepEqual(outlines(reading, "after"), [
    { x: 0, y: 40, width: 64, height: 20, kind: "changed" },
  ]);
  assert.equal(describeDifference(reading), "1 changed area");
});

test("content in rows only the taller image has is one area with them", async () => {
  const reading = await differingRegions(
    painted(blank(64, 40), [10, 10, 20, 8]),
    painted(blank(64, 60), [10, 10, 20, 8], [10, 46, 20, 8]),
  );
  assert.deepEqual(outlines(reading, "after"), [
    { x: 0, y: 40, width: 64, height: 20, kind: "changed" },
  ]);
  assert.equal(describeDifference(reading), "1 changed area");
});

test("a strong change over most of the image points nowhere", async () => {
  const image = page(160, 160);
  const most = await differingRegions(image, painted(image, [0, 0, 160, 90, 1, 0]));
  assert.deepEqual([most.throughout, most.regions], [true, []]);
  assert.equal(describeDifference(most), "changed throughout");
  // Slight everywhere, as a contrast shift is, is still only slight.
  assert.equal(
    describeDifference(
      await differingRegions(
        blank(160, 160),
        painted(blank(160, 160), [0, 0, 160, 160, 1, 250]),
      ),
    ),
    "only slight changes",
  );
});

test("the description", () => {
  const reading = (changed, throughout, regions = []) => ({
    changed,
    throughout,
    regions,
  });
  const region = (side, kind, x = 0) => ({
    x,
    y: 0,
    width: 10,
    height: 10,
    side,
    kind,
  });
  assert.equal(describeDifference(reading(0, false)), "identical");
  assert.equal(describeDifference(reading(5, false)), "only slight changes");
  assert.equal(describeDifference(reading(5, true)), "changed throughout");
  // A change seen in both frames counts once; one seen in only one frame counts too.
  assert.equal(
    describeDifference(
      reading(5, false, [region("before", "changed"), region("after", "changed")]),
    ),
    "1 changed area",
  );
  assert.equal(
    describeDifference(
      reading(5, false, [region("after", "changed"), region("after", "changed", 50)]),
    ),
    "2 changed areas",
  );
  assert.equal(
    describeDifference(
      reading(5, false, [
        region("before", "changed"),
        region("after", "changed"),
        region("before", "moved", 50),
        region("after", "moved", 90),
      ]),
    ),
    "1 changed area, 1 moved",
  );
});
