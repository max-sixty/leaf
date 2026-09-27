/* Where two images differ: which pixels count, and how they gather into the regions a
   reader of the pair is shown. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { differingRegions } from "/runtime/image-difference.js";

// A blank opaque image, and a copy with the given rectangles repainted.
const blank = (width, height) => ({
  width,
  height,
  data: new Uint8ClampedArray(width * height * 4).fill(255),
});
const painted = (image, ...rects) => {
  const copy = { ...image, data: image.data.slice() };
  for (const [x, y, width, height, channel = 0] of rects)
    for (let row = y; row < y + height; row += 1)
      for (let column = x; column < x + width; column += 1)
        copy.data[(row * image.width + column) * 4 + channel] = 254;
  return copy;
};

test("identical images differ nowhere", () => {
  const image = blank(64, 48);
  assert.deepEqual(differingRegions(image, painted(image)), {
    width: 64,
    height: 48,
    changed: 0,
    regions: [],
  });
});

test("one level in any one channel, alpha included, is a difference", () => {
  const image = blank(40, 40);
  for (const channel of [0, 1, 2, 3]) {
    const { changed, regions } = differingRegions(
      image,
      painted(image, [5, 6, 1, 1, channel]),
    );
    assert.equal(changed, 1);
    assert.deepEqual(regions, [{ x: 5, y: 6, width: 1, height: 1 }]);
  }
});

test("a region is the exact box of its pixels, not of its cells", () => {
  const image = blank(100, 100);
  const { regions } = differingRegions(image, painted(image, [13, 21, 5, 3]));
  assert.deepEqual(regions, [{ x: 13, y: 21, width: 5, height: 3 }]);
});

test("changes close together read as one region, far apart as two", () => {
  const image = blank(400, 300);
  // Two words on a line, a few pixels apart, and a chip in the far corner.
  const { regions, changed } = differingRegions(
    image,
    painted(image, [20, 20, 30, 10], [56, 22, 40, 8], [350, 270, 40, 20]),
  );
  assert.equal(changed, 30 * 10 + 40 * 8 + 40 * 20);
  assert.deepEqual(regions, [
    { x: 20, y: 20, width: 76, height: 10 },
    { x: 350, y: 270, width: 40, height: 20 },
  ]);
});

test("a change that wraps across a diagonal still joins", () => {
  const image = blank(200, 200);
  const { regions } = differingRegions(
    image,
    painted(image, [100, 10, 4, 4], [80, 22, 4, 4]),
  );
  assert.deepEqual(regions, [{ x: 80, y: 10, width: 24, height: 16 }]);
});

test("rows only the taller image has are a difference", () => {
  const short = blank(20, 10);
  const tall = blank(20, 16);
  const { changed, regions, height } = differingRegions(short, tall);
  assert.equal(height, 16);
  assert.equal(changed, 20 * 6);
  assert.deepEqual(regions, [{ x: 0, y: 10, width: 20, height: 6 }]);
});
