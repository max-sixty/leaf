/* Where two images differ: the one rule every reader of a before/after pair shares.
 *
 * A pixel differs when any of its channels differs, alpha included, so two captures of
 * one runtime at one viewport compare equal and a redrawn pixel never does. Where the
 * sizes differ, a pixel only one image has differs. There is no tolerance: a pair is
 * screenshots, and a screenshot that changed by one level in one channel was redrawn.
 *
 * A region is faint when no pixel in it moved by FAINT levels in any channel. That is
 * a change a reader can look straight at and not see: a shadow edge redrawn, a
 * contrast or palette shift, lossy encoding. Content that appears, moves or changes
 * colour moves some pixel by far more. Measured on a thread card pair: its shadow
 * edges moved by at most 20 levels, a whole-image contrast change by 17, palette
 * quantization by 35, and the card that grew by 227.
 *
 * Changed pixels gather into regions, so a reader sees where the change is rather than
 * a speckle of pixels. The images are cut into CELL-pixel squares; changed squares
 * within REACH squares of one another join, so an edited line or a restyled control
 * reads as one region while two changes a card apart stay two, and a faint region is
 * one made only of faint squares. A region is the exact
 * bounding box of its changed pixels, in the images' own pixels, and regions come in
 * reading order.
 *
 * A before/after widget outlines the regions over both frames of its pair, and
 * `scripts/stills.py` loads this module into its browser on its own and crops a changed
 * state to their union, so the module imports nothing and touches no document. */

const CELL = 8;
const REACH = 3;
const FAINT = 48;
// A region this much of the frame's width and height is a change to the whole image.
const THROUGHOUT = 0.9;

/* The regions where `a` and `b` differ, each `{x, y, width, height, faint}`, and
 * `changed`, the number of differing pixels. `a` and `b` are ImageData, or `width`, `height`, and
 * RGBA bytes in a `data` array of their own, which each pixel is read from as one
 * 32-bit word. */
export function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const rows = Math.ceil(height / CELL);
  // Per cell, the bounding box of its changed pixels; a cell with none keeps -1.
  const boxes = new Int32Array(columns * rows * 4).fill(-1);
  // Per cell, the largest difference in any one channel of its changed pixels.
  const strengths = new Uint8Array(columns * rows);
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
      const cell = row + Math.floor(x / CELL);
      const at = cell * 4;
      const strength =
        inA && inB && x < a.width && x < b.width
          ? largest(a.data, (y * a.width + x) * 4, b.data, (y * b.width + x) * 4)
          : 255;
      if (strength > strengths[cell]) strengths[cell] = strength;
      if (boxes[at] < 0) {
        boxes[at] = boxes[at + 2] = x;
        boxes[at + 1] = y;
      } else if (x < boxes[at]) boxes[at] = x;
      else if (x > boxes[at + 2]) boxes[at + 2] = x;
      boxes[at + 3] = y;
    }
  }

  // Strong cells, those with a pixel that moved FAINT levels, join one another first.
  // A faint cell near a strong one then joins that change, as the anti-aliased edge or
  // shadow around it; the faint cells left join one another. Faint cells never join
  // across the page to a strong one, or a speckle of encoding noise would merge every
  // real change into one region the size of the frame.
  const parent = new Int32Array(columns * rows).map((_, cell) => cell);
  const root = (cell) => {
    while (parent[cell] !== cell) cell = parent[cell] = parent[parent[cell]];
    return cell;
  };
  const changedCell = (cell) => boxes[cell * 4] >= 0;
  const strong = (cell) => strengths[cell] >= FAINT;
  const near = (cell) => {
    const row = Math.floor(cell / columns);
    const column = cell % columns;
    const cells = [];
    for (let r = Math.max(0, row - REACH); r <= Math.min(rows - 1, row + REACH); r += 1)
      for (
        let c = Math.max(0, column - REACH);
        c <= Math.min(columns - 1, column + REACH);
        c += 1
      ) {
        const other = r * columns + c;
        if (other !== cell && changedCell(other)) cells.push(other);
      }
    return cells;
  };
  const join = (cell, other) => {
    const [from, to] = [root(cell), root(other)];
    if (from !== to) parent[to] = from;
  };
  const cells = [];
  for (let cell = 0; cell < columns * rows; cell += 1)
    if (changedCell(cell)) cells.push(cell);
  const [strongCells, faintCells] = [
    cells.filter(strong),
    cells.filter((c) => !strong(c)),
  ];
  for (const cell of strongCells)
    for (const other of near(cell)) if (strong(other)) join(cell, other);
  const edges = new Set();
  for (const cell of faintCells) {
    const beside = near(cell).find(strong);
    if (beside === undefined) continue;
    parent[cell] = root(beside);
    edges.add(cell);
  }
  for (const cell of faintCells)
    if (!edges.has(cell))
      for (const other of near(cell))
        if (!strong(other) && !edges.has(other)) join(cell, other);

  const groups = new Map();
  for (const cell of cells) {
    const [left, top, right, bottom] = boxes.subarray(cell * 4, cell * 4 + 4);
    const group = root(cell);
    const box = groups.get(group);
    if (!box) groups.set(group, [left, top, right, bottom, strengths[cell]]);
    else {
      box[0] = Math.min(box[0], left);
      box[1] = Math.min(box[1], top);
      box[2] = Math.max(box[2], right);
      box[3] = Math.max(box[3], bottom);
      box[4] = Math.max(box[4], strengths[cell]);
    }
  }
  const regions = [...groups.values()]
    .map(([left, top, right, bottom, strength]) => ({
      x: left,
      y: top,
      width: right - left + 1,
      height: bottom - top + 1,
      faint: strength < FAINT,
    }))
    .sort((one, other) => one.y - other.y || one.x - other.x);
  // A region inside another of its kind adds nothing to where the change is.
  const inside = (region, other) =>
    other !== region &&
    other.faint === region.faint &&
    other.x <= region.x &&
    other.y <= region.y &&
    other.x + other.width >= region.x + region.width &&
    other.y + other.height >= region.y + region.height;
  return {
    width,
    height,
    changed,
    regions: regions.filter(
      (region) => !regions.some((other) => inside(region, other)),
    ),
  };
}

const largest = (one, i, other, j) =>
  Math.max(
    Math.abs(one[i] - other[j]),
    Math.abs(one[i + 1] - other[j + 1]),
    Math.abs(one[i + 2] - other[j + 2]),
    Math.abs(one[i + 3] - other[j + 3]),
  );

/* The reading in a few words: "identical", or the changes a reader can see and then
 * the faint ones, each counted or said to run throughout the image: "2 changed
 * areas", "changed throughout", "1 changed area, 3 faint", "faint changes
 * throughout". */
export function describeDifference({ width, height, regions }) {
  if (!regions.length) return "identical";
  const whole = (region) =>
    region.width >= THROUGHOUT * width && region.height >= THROUGHOUT * height;
  const seen = regions.filter((region) => !region.faint);
  const faint = regions.filter((region) => region.faint);
  if (seen.some(whole)) return "changed throughout";
  const areas = (count) => `${count} changed ${count === 1 ? "area" : "areas"}`;
  if (!faint.length) return areas(seen.length);
  if (!seen.length)
    return faint.some(whole)
      ? "faint changes throughout"
      : `${faint.length} faint ${faint.length === 1 ? "change" : "changes"}`;
  return `${areas(seen.length)}, ${faint.some(whole) ? "faint throughout" : `${faint.length} faint`}`;
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
