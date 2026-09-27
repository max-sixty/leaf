/* Where two images differ: which pixels count, where a reader is sent to look, and
   the words that sum it up. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { describeDifference, differingRegions } from "/runtime/image-difference.js";

// A blank opaque image, and a copy with the given rectangles repainted.
const blank = (width, height) => ({
  width,
  height,
  data: new Uint8ClampedArray(width * height * 4).fill(255),
});
// `value` is what the rectangle's one channel is set to, on a white image; the default
// moves it far enough to draw.
const painted = (image, ...rects) => {
  const copy = { ...image, data: image.data.slice() };
  for (const [x, y, width, height, channel = 0, value = 0] of rects)
    for (let row = y; row < y + height; row += 1)
      for (let column = x; column < x + width; column += 1)
        copy.data[(row * image.width + column) * 4 + channel] = value;
  return copy;
};
const read = (image, ...rects) => differingRegions(image, painted(image, ...rects));

test("identical images differ nowhere", () => {
  const image = blank(64, 48);
  assert.deepEqual(read(image), {
    width: 64,
    height: 48,
    changed: 0,
    throughout: false,
    regions: [],
  });
});

test("one level in any one channel, alpha included, is a change", () => {
  const image = blank(40, 40);
  for (const channel of [0, 1, 2, 3])
    assert.equal(read(image, [5, 6, 1, 1, channel, 254]).changed, 1);
});

test("a pixel moved 48 levels is drawn, and none moved less is", () => {
  const image = blank(200, 100);
  const reading = read(image, [10, 10, 20, 20, 1, 255 - 47], [150, 60, 20, 20, 1, 207]);
  assert.equal(reading.changed, 800);
  assert.deepEqual(reading.regions, [{ x: 150, y: 60, width: 20, height: 20 }]);
  assert.equal(
    describeDifference(read(image, [10, 10, 20, 20, 1, 208])),
    "only slight changes",
  );
});

test("a region is the exact box of its pixels, not of its squares", () => {
  const { regions } = read(blank(100, 100), [13, 21, 5, 3]);
  assert.deepEqual(regions, [{ x: 13, y: 21, width: 5, height: 3 }]);
});

test("changes close together read as one region, far apart as two", () => {
  // Two words on a line, a few pixels apart, and a chip in the far corner.
  const { regions } = read(
    blank(400, 300),
    [20, 20, 30, 10],
    [56, 22, 40, 8],
    [350, 270, 40, 20],
  );
  assert.deepEqual(regions, [
    { x: 20, y: 20, width: 76, height: 10 },
    { x: 350, y: 270, width: 40, height: 20 },
  ]);
});

test("a change that wraps across a diagonal still joins", () => {
  const { regions } = read(blank(200, 200), [100, 10, 4, 4], [80, 22, 4, 4]);
  assert.deepEqual(regions, [{ x: 80, y: 10, width: 24, height: 16 }]);
});

test("rows only the taller image has are a change", () => {
  const reading = differingRegions(blank(64, 40), blank(64, 48));
  assert.equal(reading.changed, 64 * 8);
  assert.deepEqual(reading.regions, [{ x: 0, y: 40, width: 64, height: 8 }]);
});

test("slight speckle joins a change only as its edge, and never joins itself", () => {
  // A block with a slight rim, and slight speckle across the page that would chain
  // everything into one region if slight squares joined one another.
  const rects = [
    [200, 80, 40, 40],
    [242, 80, 4, 40, 1, 250],
  ];
  for (let x = 0; x < 400; x += 16) rects.push([x, 10, 2, 2, 1, 250]);
  for (let y = 10; y < 200; y += 16) rects.push([0, y, 2, 2, 1, 250]);
  const { regions } = read(blank(400, 200), ...rects);
  assert.deepEqual(regions, [{ x: 200, y: 80, width: 46, height: 40 }]);
});

test("a strong change over half the image points nowhere", () => {
  const image = blank(160, 160);
  const most = read(image, [0, 0, 160, 90]);
  assert.deepEqual([most.throughout, most.regions], [true, []]);
  // Slight everywhere, as a contrast shift is, is still only slight.
  assert.equal(
    describeDifference(read(image, [0, 0, 160, 160, 1, 250])),
    "only slight changes",
  );
  // A strong ring around the edge covers less than half, so it is drawn.
  const ring = read(image, [0, 0, 160, 8], [0, 152, 160, 8], [0, 0, 8, 160]);
  assert.deepEqual([ring.throughout, ring.regions.length], [false, 1]);
});

test("the description", () => {
  const reading = (changed, throughout, count) => ({
    changed,
    throughout,
    regions: Array.from({ length: count }, () => ({})),
  });
  assert.equal(describeDifference(reading(0, false, 0)), "identical");
  assert.equal(describeDifference(reading(5, false, 0)), "only slight changes");
  assert.equal(describeDifference(reading(5, true, 0)), "changed throughout");
  assert.equal(describeDifference(reading(5, false, 1)), "1 changed area");
  assert.equal(describeDifference(reading(5, false, 3)), "3 changed areas");
});
