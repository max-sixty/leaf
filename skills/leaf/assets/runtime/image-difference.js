/* Where two images differ: the one rule every reader of a before/after pair shares.
 *
 * A pixel differs when any of its channels differs, alpha included, so two captures of
 * one runtime at one viewport compare equal and a redrawn pixel never does. Where the
 * sizes differ, a pixel only one image has differs.
 *
 * A reader wants to know where to look, and not every differing pixel says. A redrawn
 * shadow edge, a contrast shift, or a re-encoded file moves many pixels a little, and a
 * region drawn around that sends the reader to a place where nothing visible changed.
 * Content that appears, moves or changes colour moves some pixel far. Measured on a
 * thread card pair: its redrawn shadows moved at most 20 levels in any channel, most of
 * them by 1, an 8% contrast change 17, palette quantization 35, and the card that grew
 * 227. So a region is only drawn around a pixel that moved SLIGHT levels, and a pair
 * whose pixels all moved less has `regions` empty and reads "only slight changes". That
 * also hides a small deliberate edit, text from #333 to #555 (34 levels).
 *
 * A strong change over most of the image, such as a photo turned black and white,
 * has no place to point to: where strong squares (below) cover THROUGHOUT of the image,
 * the reading is `throughout` and names no regions.
 *
 * Otherwise changed pixels gather into regions. The images are cut into CELL-pixel
 * squares; a square is strong when one of its pixels moved SLIGHT levels, and strong
 * squares within REACH squares of one another join, so an edited line or a restyled
 * control reads as one region while two changes a card apart stay two. A slight square
 * within REACH of a strong one joins it as its anti-aliased edge or shadow; slight
 * squares never join one another, or a speckle of encoding noise would merge every
 * real change into one region the size of the frame. A region is the exact bounding
 * box of its changed pixels, in the images' own pixels, and regions come in reading
 * order.
 *
 * A before/after widget outlines the regions over both frames of its pair, and
 * `leaf-dev stills` loads this module into its browser on its own and crops a changed
 * state to them, so the module imports nothing and touches no document. */

const CELL = 8;
const REACH = 3;
const SLIGHT = 48;
const THROUGHOUT = 0.5;

/* How `a` and `b` differ: `changed`, the number of differing pixels; `throughout`,
 * whether they differ over most of the image; and `regions`, each `{x, y, width,
 * height}`, where they differ strongly enough to point at. `a` and `b` are ImageData,
 * or `width`, `height`, and RGBA bytes in a `data` array of their own, which each pixel
 * is read from as one 32-bit word. */
export function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  // Per square, the bounding box of its changed pixels; a square with none keeps -1.
  const boxes = new Int32Array(columns * rows * 4).fill(-1);
  // Per square, the farthest any of its pixels moved in one channel, up to SLIGHT.
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

  const strong = (cell) => moved[cell] >= SLIGHT;
  const cells = [];
  let strongCount = 0;
  for (let cell = 0; cell < columns * rows; cell += 1)
    if (boxes[cell * 4] >= 0) {
      cells.push(cell);
      if (strong(cell)) strongCount += 1;
    }
  if (strongCount >= THROUGHOUT * columns * rows)
    return { width, height, changed, throughout: true, regions: [] };

  const parent = new Int32Array(columns * rows).map((_, cell) => cell);
  const root = (cell) => {
    while (parent[cell] !== cell) cell = parent[cell] = parent[parent[cell]];
    return cell;
  };
  // Calls `visit` with each strong square within REACH of `cell`, only those after it
  // in reading order when `later`, which is all a symmetric join needs, and stops at
  // the first for which it returns true.
  const strongAround = (cell, later, visit) => {
    const row = Math.floor(cell / columns);
    const column = cell % columns;
    const left = Math.max(0, column - REACH);
    const right = Math.min(columns - 1, column + REACH);
    const last = Math.min(rows - 1, row + REACH);
    for (let r = later ? row : Math.max(0, row - REACH); r <= last; r += 1)
      for (let c = left; c <= right; c += 1) {
        const near = r * columns + c;
        if (near === cell || (later && near < cell) || !strong(near)) continue;
        if (visit(near)) return;
      }
  };
  for (const cell of cells)
    if (strong(cell))
      strongAround(cell, true, (near) => {
        const [from, to] = [root(cell), root(near)];
        if (from !== to) parent[to] = from;
      });
  const drawn = new Uint8Array(columns * rows);
  for (const cell of cells)
    if (strong(cell)) drawn[cell] = 1;
    else
      strongAround(cell, false, (near) => {
        parent[cell] = root(near);
        drawn[cell] = 1;
        return true;
      });

  const groups = new Map();
  for (const cell of cells) {
    if (!drawn[cell]) continue;
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
  return { width, height, changed, throughout: false, regions };
}

const largest = (one, i, other, j) =>
  Math.max(
    Math.abs(one[i] - other[j]),
    Math.abs(one[i + 1] - other[j + 1]),
    Math.abs(one[i + 2] - other[j + 2]),
    Math.abs(one[i + 3] - other[j + 3]),
  );

/* The reading in a few words: "identical", "only slight changes", "changed
 * throughout", or how many regions changed. */
export function describeDifference({ changed, throughout, regions }) {
  if (!changed) return "identical";
  if (throughout) return "changed throughout";
  if (!regions.length) return "only slight changes";
  return `${regions.length} changed ${regions.length === 1 ? "area" : "areas"}`;
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
