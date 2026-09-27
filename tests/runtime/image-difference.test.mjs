/* Where two images differ: which pixels count, and how they gather into the regions a
   reader of the pair is shown. */

import assert from "node:assert/strict";
import { test } from "node:test";

import { describeDifference, differingRegions } from "/runtime/image-difference.js";

// A blank opaque image, and a copy with the given rectangles repainted.
const blank = (width, height) => ({
  width,
  height,
  data: new Uint8ClampedArray(width * height * 4).fill(255),
});
// `value` is what the rectangle's one channel is set to, on a white image.
const painted = (image, ...rects) => {
  const copy = { ...image, data: image.data.slice() };
  for (const [x, y, width, height, channel = 0, value = 254] of rects)
    for (let row = y; row < y + height; row += 1)
      for (let column = x; column < x + width; column += 1)
        copy.data[(row * image.width + column) * 4 + channel] = value;
  return copy;
};
const slight = (region) => ({ ...region, slight: true, throughout: false });

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
    assert.deepEqual(regions, [slight({ x: 5, y: 6, width: 1, height: 1 })]);
  }
});

test("a region is the exact box of its pixels, not of its cells", () => {
  const image = blank(100, 100);
  const { regions } = differingRegions(image, painted(image, [13, 21, 5, 3]));
  assert.deepEqual(regions, [slight({ x: 13, y: 21, width: 5, height: 3 })]);
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
    slight({ x: 20, y: 20, width: 76, height: 10 }),
    slight({ x: 350, y: 270, width: 40, height: 20 }),
  ]);
});

test("a change that wraps across a diagonal still joins", () => {
  const image = blank(200, 200);
  const { regions } = differingRegions(
    image,
    painted(image, [100, 10, 4, 4], [80, 22, 4, 4]),
  );
  assert.deepEqual(regions, [slight({ x: 80, y: 10, width: 24, height: 16 })]);
});

test("rows only the taller image has are a difference", () => {
  const short = blank(64, 40);
  const tall = blank(64, 48);
  const { changed, regions, height } = differingRegions(short, tall);
  assert.equal(height, 48);
  assert.equal(changed, 64 * 8);
  assert.deepEqual(regions, [
    { x: 0, y: 40, width: 64, height: 8, slight: false, throughout: false },
  ]);
});

test("a region is slight until some pixel in it moves 48 levels", () => {
  const image = blank(200, 100);
  const { regions } = differingRegions(
    image,
    painted(image, [10, 10, 20, 20, 1, 255 - 47], [150, 60, 20, 20, 1, 255 - 48]),
  );
  assert.deepEqual(
    regions.map((region) => region.slight),
    [true, false],
  );
});

test("slight noise stays apart from a strong change, except at its edge", () => {
  const image = blank(400, 200);
  // A strong block with a slight rim beside it, and slight speckle across the page
  // that would otherwise chain everything into one region.
  const rects = [
    [200, 80, 40, 40, 1, 0],
    [242, 80, 4, 40, 1, 250],
  ];
  for (let x = 0; x < 400; x += 16) rects.push([x, 10, 2, 2, 1, 250]);
  for (let y = 10; y < 200; y += 16) rects.push([0, y, 2, 2, 1, 250]);
  const { regions } = differingRegions(image, painted(image, ...rects));
  const strong = regions.filter((region) => !region.slight);
  assert.deepEqual(strong, [
    { x: 200, y: 80, width: 46, height: 40, slight: false, throughout: false },
  ]);
  assert.ok(regions.some((region) => region.slight));
});

test("a slight region inside another's box is left out, a strong one never", () => {
  const image = blank(200, 200);
  // A ring, a dot at its centre too far from it to join, and a strong mark there too.
  const ring = (value) => [
    [10, 10, 180, 2, 1, value],
    [10, 188, 180, 2, 1, value],
    [10, 10, 2, 180, 1, value],
    [188, 10, 2, 180, 1, value],
  ];
  const inside = [
    [60, 100, 2, 2, 1, 250],
    [130, 100, 4, 4, 1, 0],
  ];
  const slightRing = differingRegions(image, painted(image, ...ring(250), ...inside));
  assert.deepEqual(
    slightRing.regions.map(({ x, y, slight }) => [x, y, slight]),
    [
      [10, 10, true],
      [130, 100, false],
    ],
  );
  const strongRing = differingRegions(image, painted(image, ...ring(0), ...inside));
  assert.deepEqual(
    strongRing.regions.map(({ x, y, slight }) => [x, y, slight]),
    [
      [10, 10, false],
      [130, 100, false],
    ],
  );
});

test("a region over half the image's squares is a change throughout", () => {
  const image = blank(160, 160);
  const most = differingRegions(image, painted(image, [0, 0, 160, 90, 1, 250]));
  const ring = differingRegions(
    image,
    painted(image, [0, 0, 160, 8, 1, 0], [0, 152, 160, 8, 1, 0], [0, 0, 8, 160, 1, 0]),
  );
  assert.deepEqual(
    [most, ring].map(({ regions }) => regions.map((region) => region.throughout)),
    [[true], [false]],
  );
});

test("the description counts the strong changes, then the slight ones", () => {
  const reading = (...regions) => ({ regions });
  const area = (slight, throughout = false) => ({ slight, throughout });
  assert.equal(describeDifference(reading()), "identical");
  assert.equal(describeDifference(reading(area(false))), "1 changed area");
  assert.equal(describeDifference(reading(area(true))), "1 slight change");
  assert.equal(describeDifference(reading(area(true), area(true))), "2 slight changes");
  assert.equal(
    describeDifference(reading(area(false), area(true), area(true))),
    "1 changed area, 2 slight changes",
  );
  assert.equal(
    describeDifference(reading(area(true, true))),
    "slight changes throughout",
  );
  assert.equal(
    describeDifference(reading(area(false), area(false), area(true, true))),
    "2 changed areas, slight changes throughout",
  );
  assert.equal(
    describeDifference(reading(area(false, true), area(true))),
    "changed throughout",
  );
});
