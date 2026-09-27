/* Where two images differ: the one rule every reader of a before/after pair shares.
 *
 * A pixel differs when any of its channels differs, alpha included, so two captures of
 * one runtime at one viewport compare equal and a redrawn pixel never does. Where the
 * sizes differ, a pixel only one image has differs. There is no tolerance: a pair is
 * screenshots, and a screenshot that changed by one level in one channel was redrawn.
 *
 * Changed pixels gather into regions, so a reader sees where the change is rather than
 * a speckle of pixels. The images are cut into CELL-pixel squares; changed squares
 * within REACH squares of one another join, so an edited line or a restyled control
 * reads as one region while two changes a card apart stay two. A region is the exact
 * bounding box of its changed pixels, in the images' own pixels, and regions come in
 * reading order.
 *
 * A before/after widget outlines the regions over both frames of its pair, and
 * `scripts/stills.py` loads this module into its browser on its own and crops a changed
 * state to their union, so the module imports nothing and touches no document. */

const CELL = 8;
const REACH = 3;

/* The regions where `a` and `b` differ, each `{x, y, width, height}`, and `changed`,
 * the number of differing pixels. `a` and `b` are ImageData, or `width`, `height`, and
 * RGBA bytes in a `data` array of their own, which each pixel is read from as one
 * 32-bit word. */
export function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  // Per cell, the bounding box of its changed pixels; a cell with none keeps -1.
  const boxes = new Int32Array(columns * rows * 4).fill(-1);
  let changed = 0;
  const one = new Uint32Array(a.data.buffer, a.data.byteOffset, a.width * a.height);
  const other = new Uint32Array(b.data.buffer, b.data.byteOffset, b.width * b.height);
  for (let y = 0; y < height; y += 1) {
    const inA = y < a.height;
    const inB = y < b.height;
    const row = Math.floor(y / CELL) * columns;
    for (let x = 0; x < width; x += 1) {
      if (
        inA &&
        inB &&
        x < a.width &&
        x < b.width &&
        one[y * a.width + x] === other[y * b.width + x]
      )
        continue;
      changed += 1;
      const at = (row + Math.floor(x / CELL)) * 4;
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
  const cells = [];
  for (let cell = 0; cell < columns * rows; cell += 1)
    if (boxes[cell * 4] >= 0) cells.push(cell);
  for (const cell of cells) {
    const row = Math.floor(cell / columns);
    const column = cell % columns;
    for (let r = row; r <= Math.min(rows - 1, row + REACH); r += 1)
      for (
        let c = Math.max(0, column - REACH);
        c <= Math.min(columns - 1, column + REACH);
        c += 1
      ) {
        const near = r * columns + c;
        if (near <= cell || boxes[near * 4] < 0) continue;
        const [from, to] = [root(cell), root(near)];
        if (from !== to) parent[to] = from;
      }
  }

  const groups = new Map();
  for (const cell of cells) {
    const [left, top, right, bottom] = boxes.subarray(cell * 4, cell * 4 + 4);
    const group = root(cell);
    const box = groups.get(group);
    if (!box) groups.set(group, [left, top, right, bottom]);
    else {
      box[0] = Math.min(box[0], left);
      box[1] = Math.min(box[1], top);
      box[2] = Math.max(box[2], right);
      box[3] = Math.max(box[3], bottom);
    }
  }
  const regions = [...groups.values()]
    .map(([left, top, right, bottom]) => ({
      x: left,
      y: top,
      width: right - left + 1,
      height: bottom - top + 1,
    }))
    .sort((one, other) => one.y - other.y || one.x - other.x);
  return { width, height, changed, regions };
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
