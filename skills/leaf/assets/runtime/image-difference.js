/* Where two images differ: the one rule every reader of a before/after pair shares.
 *
 * A pixel differs when any of its channels differs, alpha included, so two captures of
 * one runtime at one viewport compare equal and a redrawn pixel never does. Where the
 * sizes differ, a pixel only one image has differs.
 *
 * How far a pixel moved separates two kinds of change. Content that appears, moves or
 * changes colour moves some pixel far. A redrawn shadow edge, a contrast or palette
 * shift, or lossy encoding moves many pixels a little, and can spread over the whole
 * image. Measured on a thread card pair: its shadow edges moved at most 20 levels in
 * any channel, an 8% contrast change 17, palette quantization 35, and the card that
 * grew 227. A region is slight when none of its pixels moved SLIGHT levels. A slight
 * change can still be one a reader sees, such as text from #333 to #555, so slight
 * says how far pixels moved, not whether anyone notices.
 *
 * Changed pixels gather into regions, so a reader sees where the change is rather than
 * a speckle of pixels. The images are cut into CELL-pixel squares, and a square is
 * slight when its pixels are. Squares within REACH squares of one another join, so an
 * edited line or a restyled control reads as one region while two changes a card apart
 * stay two, with one exception that keeps the two kinds apart: a slight square joins a
 * strong one only as its edge, never through a chain of slight squares, or a speckle
 * of encoding noise would merge every real change into one region the size of the
 * frame. A region is the exact bounding box of its changed pixels, in the images' own
 * pixels, and regions come in reading order. A slight region inside another region's
 * box is left out; a strong region never is, since a box says nothing about what inside
 * it changed.
 *
 * A before/after widget outlines the regions over both frames of its pair, and
 * `scripts/stills.py` loads this module into its browser on its own and crops a
 * changed state to its strong regions, so the module imports nothing and touches no
 * document. */

const CELL = 8;
const REACH = 3;
const SLIGHT = 48;
// A region whose squares cover this share of the image is a change throughout it.
const THROUGHOUT = 0.5;

/* The regions where `a` and `b` differ, each `{x, y, width, height, slight,
 * throughout}`, and `changed`, the number of differing pixels. `a` and `b` are
 * ImageData, or `width`, `height`, and RGBA bytes in a `data` array of their own, which
 * each pixel is read from as one 32-bit word. */
export function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  // Per square, the bounding box of its changed pixels; a square with none keeps -1.
  const boxes = new Int32Array(columns * rows * 4).fill(-1);
  // Per square, the farthest any of its pixels moved in one channel.
  const moved = new Uint8Array(columns * rows);
  let changed = 0;
  const one = new Uint32Array(a.data.buffer, a.data.byteOffset, a.width * a.height);
  const other = new Uint32Array(b.data.buffer, b.data.byteOffset, b.width * b.height);
  for (let y = 0; y < height; y += 1) {
    const inBoth = y < a.height && y < b.height;
    const row = Math.floor(y / CELL) * columns;
    for (let x = 0; x < width; x += 1) {
      const shared = inBoth && x < a.width && x < b.width;
      if (shared && one[y * a.width + x] === other[y * b.width + x]) continue;
      changed += 1;
      const cell = row + Math.floor(x / CELL);
      if (moved[cell] < SLIGHT) {
        const distance = shared
          ? largest(a.data, (y * a.width + x) * 4, b.data, (y * b.width + x) * 4)
          : 255;
        if (distance > moved[cell]) moved[cell] = distance;
      }
      const at = cell * 4;
      if (boxes[at] < 0) {
        boxes[at] = boxes[at + 2] = x;
        boxes[at + 1] = y;
      } else if (x < boxes[at]) boxes[at] = x;
      else if (x > boxes[at + 2]) boxes[at + 2] = x;
      boxes[at + 3] = y;
    }
  }

  const parent = new Int32Array(columns * rows).map((_, cell) => cell);
  const root = (cell) => {
    while (parent[cell] !== cell) cell = parent[cell] = parent[parent[cell]];
    return cell;
  };
  const join = (cell, near) => {
    const [from, to] = [root(cell), root(near)];
    if (from !== to) parent[to] = from;
  };
  const changedAt = (cell) => boxes[cell * 4] >= 0;
  const strong = (cell) => moved[cell] >= SLIGHT;
  // Calls `visit` with each changed square within REACH of `cell`, only those after
  // it in reading order when `later`, which is all a symmetric join needs, and stops
  // at the first for which it returns true.
  const around = (cell, later, visit) => {
    const row = Math.floor(cell / columns);
    const column = cell % columns;
    const [left, right] = [
      Math.max(0, column - REACH),
      Math.min(columns - 1, column + REACH),
    ];
    for (
      let r = later ? row : Math.max(0, row - REACH);
      r <= Math.min(rows - 1, row + REACH);
      r += 1
    )
      for (let c = left; c <= right; c += 1) {
        const near = r * columns + c;
        if (near === cell || (later && near < cell) || !changedAt(near)) continue;
        if (visit(near)) return;
      }
  };
  const cells = [];
  for (let cell = 0; cell < columns * rows; cell += 1)
    if (changedAt(cell)) cells.push(cell);
  for (const cell of cells)
    if (strong(cell)) around(cell, true, (near) => strong(near) && join(cell, near));
  const edges = new Uint8Array(columns * rows);
  for (const cell of cells)
    if (!strong(cell))
      around(cell, false, (near) => {
        if (!strong(near)) return false;
        parent[cell] = root(near);
        edges[cell] = 1;
        return true;
      });
  for (const cell of cells)
    if (!strong(cell) && !edges[cell])
      around(cell, true, (near) => !strong(near) && !edges[near] && join(cell, near));

  // [left, top, right, bottom, farthest moved, squares]
  const groups = new Map();
  for (const cell of cells) {
    const [left, top, right, bottom] = boxes.subarray(cell * 4, cell * 4 + 4);
    const group = root(cell);
    const box = groups.get(group);
    if (!box) groups.set(group, [left, top, right, bottom, moved[cell], 1]);
    else {
      box[0] = Math.min(box[0], left);
      box[1] = Math.min(box[1], top);
      box[2] = Math.max(box[2], right);
      box[3] = Math.max(box[3], bottom);
      box[4] = Math.max(box[4], moved[cell]);
      box[5] += 1;
    }
  }
  const regions = [...groups.values()].map(
    ([left, top, right, bottom, farthest, squares]) => ({
      x: left,
      y: top,
      width: right - left + 1,
      height: bottom - top + 1,
      slight: farthest < SLIGHT,
      throughout: squares >= THROUGHOUT * columns * rows,
    }),
  );
  // Larger boxes first, so a slight region only ever looks at the boxes that could
  // hold it, and a page of equal specks compares none of them.
  const area = (region) => region.width * region.height;
  const bySize = [...regions].sort((one, other) => area(other) - area(one));
  const holds = (outer, inner) =>
    outer.x <= inner.x &&
    outer.y <= inner.y &&
    outer.x + outer.width >= inner.x + inner.width &&
    outer.y + outer.height >= inner.y + inner.height;
  const held = (region) => {
    for (const outer of bySize) {
      if (area(outer) <= area(region)) return false;
      if (holds(outer, region)) return true;
    }
    return false;
  };
  return {
    width,
    height,
    changed,
    regions: regions
      .filter((region) => !region.slight || !held(region))
      .sort((one, other) => one.y - other.y || one.x - other.x),
  };
}

const largest = (one, i, other, j) =>
  Math.max(
    Math.abs(one[i] - other[j]),
    Math.abs(one[i + 1] - other[j + 1]),
    Math.abs(one[i + 2] - other[j + 2]),
    Math.abs(one[i + 3] - other[j + 3]),
  );

/* The reading in a few words: "identical", or the strong changes and then the slight
 * ones, each counted or said to run throughout the image: "2 changed areas",
 * "changed throughout", "1 changed area, 3 slight changes", "slight changes
 * throughout". */
export function describeDifference({ regions }) {
  if (!regions.length) return "identical";
  const strong = regions.filter((region) => !region.slight);
  const slight = regions.filter((region) => region.slight);
  if (strong.some((region) => region.throughout)) return "changed throughout";
  const count = (n, noun) => `${n} ${noun}${n === 1 ? "" : "s"}`;
  const slightly = slight.some((region) => region.throughout)
    ? "slight changes throughout"
    : count(slight.length, "slight change");
  if (!slight.length) return count(strong.length, "changed area");
  if (!strong.length) return slightly;
  return `${count(strong.length, "changed area")}, ${slightly}`;
}

/* `differingRegions` for two decoded images: HTMLImageElements, ImageBitmaps, or any
 * other canvas image source, read at their natural size. */
export function compareImages(a, b) {
  return differingRegions(pixels(a), pixels(b));
}

function pixels(image) {
  const width = image.naturalWidth ?? image.width;
  const height = image.naturalHeight ?? image.height;
  const context = new OffscreenCanvas(width, height).getContext("2d", {
    willReadFrequently: true,
  });
  context.drawImage(image, 0, 0);
  return context.getImageData(0, 0, width, height);
}
