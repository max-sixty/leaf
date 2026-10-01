/* Where two images differ: the one rule every reader of a before/after pair shares.
 *
 * Experimental. The reading below is our own, tuned by eye on about 56 pairs of Leaf
 * captures and not yet tried on other screenshots (another site, a terminal, a plot).
 * We looked for a dependency first and found none that reads moves: pixelmatch, odiff,
 * BlazeDiff and looks-same compare pixels in place; lcs-image-diff aligns rows, so it
 * follows content pushed down but not a move across columns, and returns an image
 * rather than regions; x-img-diff-js, the one built for moved regions, took 7 s on a
 * 1440x900 pair, outlined page-wide bands and crashed on the next pair, and has not
 * been released since 2017. Tools that do read moves, such as Percy's and SmartUI's
 * layout modes, compare the DOM rather than the pixels, which an arbitrary pair of
 * images does not carry.
 *
 * A pixel differs when any of its channels differs, alpha included, so two captures of
 * one runtime at one viewport compare equal and a redrawn pixel never does. Where the
 * sizes differ, a pixel only one image has differs.
 *
 * Not every differing pixel is a place to look. A redrawn shadow edge, a contrast shift,
 * or a re-encoded file moves many pixels a little, while content that appears, moves or
 * changes colour moves some pixel far. Measured on a thread card pair: its redrawn
 * shadows moved at most 20 levels in any channel, most of them by 1, an 8% contrast
 * change 17, palette quantization 35, and the card that grew 227. So only a pixel that
 * moved SLIGHT levels changed a pair's content, and a pair whose pixels all moved less
 * reads "only slight changes". That also hides a small deliberate edit, text from #333
 * to #555 (34 levels).
 *
 * A reader is sent to things, not to pixels: the paragraph that rewrapped, the chart
 * that narrowed, the card that went. Comparing pixels at one place cannot name them: when
 * content above grows, everything below differs from what used to be there, and a
 * region drawn around those pixels covers half the page. So each image is first read as
 * blocks, the way a reader groups it. An edge is where a pixel is unlike its neighbour;
 * a straight run of one colour along an edge at least LINE long is a line (a border, a
 * rule, a bar's side), and the other edges are marks (text, icons). In CELL squares,
 * anything joins what it touches, and marks join the marks beside them, in a row or a
 * column, across a gap no wider than SPACING times the shorter one's height. So a word,
 * a paragraph, a control, or a chart on its axes reads as one block whatever the
 * capture's pixel density, while a frame's padding keeps the frame apart from what it
 * holds. A block of lines alone is a frame: a card's border, a filled panel's edge, a
 * rule.
 *
 * Each image's blocks are then read against the other image. A block none of whose
 * squares holds a changed pixel is the same. A block that did change is looked for in
 * the other image, among its blocks of the same size that changed too, the nearest
 * first: found there, no pixel more than SLIGHT apart, it moved; found nowhere, it
 * changed. Each frame of the pair is outlined on its own, around its own blocks: where
 * content changed, in both frames at the place it has in each, and where it moved, at
 * its old place in before and its new place in after. So a list that moved beside a
 * chart is outlined at the foot of before and beside the chart in after, and nothing
 * marks the empty place it left. A change where neither image draws an edge, such as
 * rows of ground only the taller image has, lies inside no block; its struck squares
 * are outlined as a change in each image that reaches them.
 *
 * A block that holds another outline is a container, such as a panel, a card or a lane.
 * One that changed and holds only what changed too, as a card whose text rewrapped, is
 * outlined whole. Any other gives way to what it holds: its contents are outlined, and
 * its own changed squares that no outline covers widen the outline within ABSORB of
 * them, as a card's edge does below the text that grew it, or stand alone. A frame
 * alone that moved, and a move inside a change, are not outlined. Outlines of one kind
 * that would touch as drawn join, and moves that share a displacement join within
 * MOVED_REACH.
 *
 * A strong change over most of the image, such as a photo turned black and white, has
 * no place to point to: where squares COARSE pixels on a side holding a pixel that moved
 * SLIGHT levels cover THROUGHOUT of the image, the reading is `throughout` and names no
 * regions.
 *
 * A before/after widget states the reading and, when asked, draws each frame's outlines,
 * and `leaf-dev stills` loads this module into its browser on its own and crops a
 * changed state to them, so the module imports nothing and touches no document. */

const SLIGHT = 48;
const STEP = 4;
const LINE = 40;
const CELL = 4;
const SPACING = 1;
const COARSE = 8;
const THROUGHOUT = 0.5;
const PAD = 4;
const ABSORB = 16;
const MOVED_REACH = 32;

/* How `a` and `b` differ: `changed`, the number of differing pixels; `throughout`,
 * whether they differ over most of the image; and `regions`, each `{x, y, width, height,
 * side, kind}`: an outline on the `side` ("before" for `a`, "after" for `b`) around
 * content that `kind` "changed" or "moved", in that image's own pixels, in reading order.
 * `a` and `b` are ImageData, or `width`, `height`, and RGBA bytes in a `data` array of
 * their own, which each pixel is read from as one 32-bit word. */
export function differingRegions(a, b) {
  const width = Math.max(a.width, b.width);
  const height = Math.max(a.height, b.height);
  const columns = Math.ceil(width / CELL);
  const one = words(a);
  const other = words(b);
  // Per square of the pair, whether a pixel in it moved SLIGHT levels or more, and the
  // same over the coarser squares THROUGHOUT is read in.
  const struck = new Uint8Array(columns * Math.ceil(height / CELL));
  const coarseColumns = Math.ceil(width / COARSE);
  const coarse = new Uint8Array(coarseColumns * Math.ceil(height / COARSE));
  let changed = 0;
  for (let y = 0; y < height; y += 1) {
    const row = Math.floor(y / CELL) * columns;
    const coarseRow = Math.floor(y / COARSE) * coarseColumns;
    for (let x = 0; x < width; x += 1) {
      const p = x < a.width && y < a.height ? one[y * a.width + x] : undefined;
      const q = x < b.width && y < b.height ? other[y * b.width + x] : undefined;
      if (p === q && p !== undefined) continue;
      changed += 1;
      if (p === undefined || q === undefined || distance(p, q) >= SLIGHT) {
        struck[row + Math.floor(x / CELL)] = 1;
        coarse[coarseRow + Math.floor(x / COARSE)] = 1;
      }
    }
  }
  if (coarse.reduce((sum, square) => sum + square, 0) >= THROUGHOUT * coarse.length)
    return { width, height, changed, throughout: true, regions: [] };
  // A block changed only where a square was struck, so with none, none did.
  if (!struck.includes(1))
    return { width, height, changed, throughout: false, regions: [] };
  const before = blocksOf(a, one, columns);
  const after = blocksOf(b, other, columns);
  const touched = (block) => block.cells.some((cell) => struck[cell]);
  const reading = (blocks, image, pixels, others, otherImage, otherPixels) =>
    blocks.map((block) => {
      if (!touched(block)) return { state: "same" };
      let found = null;
      let nearest = Infinity;
      for (const candidate of others) {
        // Content arrives only where the other image changed, so a block that stayed
        // where it was, such as one of a row of like icons, is never where this went.
        if (!touched(candidate)) continue;
        if (candidate.width !== block.width || candidate.height !== block.height)
          continue;
        const far = Math.abs(candidate.x - block.x) + Math.abs(candidate.y - block.y);
        if (
          far < nearest &&
          alike(image, pixels, block, otherImage, otherPixels, candidate)
        )
          [found, nearest] = [candidate, far];
      }
      if (!found) return { state: "changed" };
      if (!nearest) return { state: "same" };
      return { state: "moved", d: [found.x - block.x, found.y - block.y] };
    });
  const readBefore = reading(before, a, one, after, b, other);
  const readAfter = reading(after, b, other, before, a, one);
  // A change where neither image draws an edge, such as rows of ground only the taller
  // image has, lies inside no block's box, so its squares are outlined on their own, in
  // each image that reaches them.
  const owned = new Uint8Array(struck.length);
  for (const block of [...before, ...after])
    for (let r = Math.floor(block.y / CELL); r * CELL < block.y + block.height; r += 1)
      owned.fill(
        1,
        r * columns + Math.floor(block.x / CELL),
        r * columns + Math.ceil((block.x + block.width) / CELL),
      );
  const bare = [];
  for (let cell = 0; cell < struck.length; cell += 1)
    if (struck[cell] && !owned[cell]) {
      const x = (cell % columns) * CELL;
      const y = Math.floor(cell / columns) * CELL;
      bare.push({
        x,
        y,
        width: Math.min(CELL, width - x),
        height: Math.min(CELL, height - y),
      });
    }
  const unowned = merged(bare, (p, q) => near(p, q, 2 * CELL)).flatMap((box) =>
    [
      ["before", a],
      ["after", b],
    ].flatMap(([side, image]) => {
      const right = Math.min(box.x + box.width, image.width);
      const bottom = Math.min(box.y + box.height, image.height);
      return right > box.x && bottom > box.y
        ? [
            {
              x: box.x,
              y: box.y,
              width: right - box.x,
              height: bottom - box.y,
              side,
              kind: "changed",
            },
          ]
        : [];
    }),
  );
  const regions = [
    ...outlines(before, readBefore, struck, columns, "before"),
    ...outlines(after, readAfter, struck, columns, "after"),
    ...unowned,
  ]
    .sort((p, q) => p.y - q.y || p.x - q.x)
    .map(({ x, y, width, height, side, kind }) => ({
      x,
      y,
      width,
      height,
      side,
      kind,
    }));
  return { width, height, changed, throughout: false, regions };
}

/* One image's outlines from its blocks and their readings. */
function outlines(blocks, states, struck, columns, side) {
  const marks = [];
  for (const [i, block] of blocks.entries()) {
    const { state, d } = states[i];
    if (state === "same") continue;
    // A frame alone that moved, such as a rule, is not a place to look.
    if (state === "moved" && block.frame) continue;
    marks.push({ ...box(block), side, kind: state, d, block });
  }
  // Containers are outlined whole or give way, as the module header states.
  const whole = marks.filter(
    (mark) =>
      mark.kind === "changed" &&
      marks.some((inner) => contains(mark, inner)) &&
      blocks.every(
        (block, i) => states[i].state === "changed" || !contains(mark, block),
      ),
  );
  const inWhole = (mark) => whole.some((outer) => contains(outer, mark));
  const holds = (mark) =>
    !whole.includes(mark) && marks.some((inner) => contains(mark, inner));
  const shown = marks.filter((mark) => !holds(mark) && !inWhole(mark));
  for (const mark of marks) {
    if (!holds(mark) || inWhole(mark) || mark.kind !== "changed") continue;
    const loose = mark.block.cells
      .filter((cell) => struck[cell])
      .map((cell) => mark.block.boxes.get(cell))
      .filter((cellBox) => !shown.some((other) => contains(other, cellBox)));
    for (const group of merged(loose, (p, q) => near(p, q, 2 * CELL))) {
      const host = shown.find(
        (other) => other.kind === "changed" && near(other, group, ABSORB),
      );
      if (host) Object.assign(host, union(host, group));
      else shown.push({ ...group, side, kind: "changed" });
    }
  }
  const joined = join(shown);
  return joined.filter(
    (mark) =>
      mark.kind !== "moved" ||
      !joined.some((outer) => outer.kind === "changed" && contains(outer, mark)),
  );
}

/* The blocks of one image: each with its box, its squares (numbered in the pair's
 * `columns`), each square's own box of edge pixels, and whether it is a frame. */
function blocksOf(image, pixels, columns) {
  const { width, height } = image;
  // Whether each pixel is unlike the one below it, and the one to its right.
  const belowDiffers = new Uint8Array(width * height);
  const rightDiffers = new Uint8Array(width * height);
  for (let i = 0; i < width * height; i += 1) {
    const p = pixels[i];
    if (
      i + width < width * height &&
      p !== pixels[i + width] &&
      distance(p, pixels[i + width]) > STEP
    )
      belowDiffers[i] = 1;
    if ((i + 1) % width && p !== pixels[i + 1] && distance(p, pixels[i + 1]) > STEP)
      rightDiffers[i] = 1;
  }
  // An edge across rows (the pixel below differs) and across columns, on both pixels.
  const acrossRows = new Uint8Array(width * height);
  const acrossColumns = new Uint8Array(width * height);
  for (let i = 0; i < width * height; i += 1) {
    if (belowDiffers[i]) acrossRows[i] = acrossRows[i + width] = 1;
    if (rightDiffers[i]) acrossColumns[i] = acrossColumns[i + 1] = 1;
  }
  // A line: LINE or more pixels along a row (or a column) on one edge, each like the
  // last.
  const line = new Uint8Array(width * height);
  for (let y = 0; y < height; y += 1) {
    const row = y * width;
    let start = 0;
    for (let x = 1; x <= width; x += 1) {
      const i = row + x;
      if (x < width && acrossRows[i] && acrossRows[i - 1] && !rightDiffers[i - 1])
        continue;
      if (x - start >= LINE && acrossRows[row + start])
        line.fill(1, row + start, row + x);
      start = x;
    }
  }
  for (let x = 0; x < width; x += 1) {
    let start = 0;
    for (let y = 1; y <= height; y += 1) {
      const i = y * width + x;
      if (
        y < height &&
        acrossColumns[i] &&
        acrossColumns[i - width] &&
        !belowDiffers[i - width]
      )
        continue;
      if (y - start >= LINE && acrossColumns[start * width + x])
        for (let k = start; k < y; k += 1) line[k * width + x] = 1;
      start = y;
    }
  }

  const rows = Math.ceil(height / CELL);
  const ownColumns = Math.ceil(width / CELL);
  const count = ownColumns * rows;
  const boxes = new Int32Array(count * 4).fill(-1);
  const marked = new Uint8Array(count);
  for (let y = 0; y < height; y += 1)
    for (let x = 0; x < width; x += 1) {
      const i = y * width + x;
      if (!acrossRows[i] && !acrossColumns[i]) continue;
      const cell = Math.floor(y / CELL) * ownColumns + Math.floor(x / CELL);
      if (!line[i]) marked[cell] = 1;
      const k = cell * 4;
      if (boxes[k] < 0) {
        boxes[k] = boxes[k + 2] = x;
        boxes[k + 1] = boxes[k + 3] = y;
      } else {
        boxes[k] = Math.min(boxes[k], x);
        boxes[k + 1] = Math.min(boxes[k + 1], y);
        boxes[k + 2] = Math.max(boxes[k + 2], x);
        boxes[k + 3] = Math.max(boxes[k + 3], y);
      }
    }
  const parent = Int32Array.from({ length: count }, (_, cell) => cell);
  const root = (cell) => {
    while (parent[cell] !== cell) cell = parent[cell] = parent[parent[cell]];
    return cell;
  };
  const join = (one, other) => {
    const [from, to] = [root(one), root(other)];
    if (from !== to) parent[to] = from;
  };
  // Squares that touch join.
  for (let r = 0; r < rows; r += 1)
    for (let c = 0; c < ownColumns; c += 1) {
      const cell = r * ownColumns + c;
      if (boxes[cell * 4] < 0) continue;
      for (const near of [
        cell + 1,
        cell + ownColumns - 1,
        cell + ownColumns,
        cell + ownColumns + 1,
      ])
        if (
          near < count &&
          Math.abs((near % ownColumns) - c) <= 1 &&
          boxes[near * 4] >= 0
        )
          join(cell, near);
    }
  // Then marks join the marks beside them, in a row or a column, across a gap no wider
  // than SPACING times the shorter one's height: the space between words, or between the
  // lines of a paragraph, scales with the text, whatever the capture's pixel density.
  const pieces = new Map();
  for (let cell = 0; cell < count; cell += 1) {
    const k = cell * 4;
    if (boxes[k] < 0) continue;
    const id = root(cell);
    const piece = pieces.get(id);
    if (!piece)
      pieces.set(id, {
        id,
        left: boxes[k],
        top: boxes[k + 1],
        right: boxes[k + 2],
        bottom: boxes[k + 3],
        marked: !!marked[cell],
      });
    else {
      piece.left = Math.min(piece.left, boxes[k]);
      piece.top = Math.min(piece.top, boxes[k + 1]);
      piece.right = Math.max(piece.right, boxes[k + 2]);
      piece.bottom = Math.max(piece.bottom, boxes[k + 3]);
      piece.marked ||= !!marked[cell];
    }
  }
  const marks = [...pieces.values()]
    .filter((piece) => piece.marked)
    .sort((p, q) => p.top - q.top);
  for (const [i, p] of marks.entries()) {
    const height = p.bottom - p.top + 1;
    for (let j = i + 1; j < marks.length; j += 1) {
      const q = marks[j];
      if (q.top > p.bottom + SPACING * height) break;
      const reach = SPACING * Math.min(height, q.bottom - q.top + 1);
      const across = Math.max(q.left - p.right, p.left - q.right) - 1;
      const down = Math.max(q.top - p.bottom, p.top - q.bottom) - 1;
      // Beside one another, not one inside the other.
      if (
        (down < 0 && across >= 0 && across <= reach) ||
        (across < 0 && down >= 0 && down <= reach)
      )
        join(p.id, q.id);
    }
  }
  const groups = new Map();
  for (let cell = 0; cell < count; cell += 1) {
    const k = cell * 4;
    if (boxes[k] < 0) continue;
    const id = root(cell);
    let group = groups.get(id);
    if (!group)
      groups.set(
        id,
        (group = {
          left: Infinity,
          top: Infinity,
          right: -1,
          bottom: -1,
          frame: true,
          cells: [],
          boxes: new Map(),
        }),
      );
    group.left = Math.min(group.left, boxes[k]);
    group.top = Math.min(group.top, boxes[k + 1]);
    group.right = Math.max(group.right, boxes[k + 2]);
    group.bottom = Math.max(group.bottom, boxes[k + 3]);
    if (marked[cell]) group.frame = false;
    const pairCell = Math.floor(cell / ownColumns) * columns + (cell % ownColumns);
    group.cells.push(pairCell);
    group.boxes.set(pairCell, {
      x: boxes[k],
      y: boxes[k + 1],
      width: boxes[k + 2] - boxes[k] + 1,
      height: boxes[k + 3] - boxes[k + 1] + 1,
    });
  }
  return [...groups.values()].map((group) => ({
    x: group.left,
    y: group.top,
    width: group.right - group.left + 1,
    height: group.bottom - group.top + 1,
    frame: group.frame,
    cells: group.cells,
    boxes: group.boxes,
  }));
}

// Whether `block` of `image` holds what `other` does at `candidate`, no pixel SLIGHT apart.
function alike(image, pixels, block, otherImage, otherPixels, candidate) {
  for (let j = 0; j < block.height; j += 1) {
    const p = (block.y + j) * image.width + block.x;
    const q = (candidate.y + j) * otherImage.width + candidate.x;
    for (let i = 0; i < block.width; i += 1) {
      const u = pixels[p + i];
      const v = otherPixels[q + i];
      if (u !== v && distance(u, v) >= SLIGHT) return false;
    }
  }
  return true;
}

const box = ({ x, y, width, height }) => ({ x, y, width, height });
const contains = (outer, inner) =>
  outer !== inner &&
  outer.x <= inner.x &&
  outer.y <= inner.y &&
  outer.x + outer.width >= inner.x + inner.width &&
  outer.y + outer.height >= inner.y + inner.height;
const near = (p, q, reach) =>
  p.x - reach < q.x + q.width &&
  q.x - reach < p.x + p.width &&
  p.y - reach < q.y + q.height &&
  q.y - reach < p.y + p.height;
const union = (p, q) => {
  const x = Math.min(p.x, q.x);
  const y = Math.min(p.y, q.y);
  return {
    x,
    y,
    width: Math.max(p.x + p.width, q.x + q.width) - x,
    height: Math.max(p.y + p.height, q.y + q.height) - y,
  };
};

// `items` with every two that `joins` accepts replaced by their union, until it accepts
// no two. A union keeps the fields of the item it grows from.
function merged(items, joins) {
  const list = items.map((item) => ({ ...item }));
  for (let i = 0; i < list.length; i += 1)
    for (let j = 0; j < list.length; j += 1) {
      if (j === i || !joins(list[i], list[j])) continue;
      list[i] = { ...list[i], ...union(list[i], list[j]) };
      list.splice(j, 1);
      if (j < i) i -= 1;
      // `list[i]` grew, so every other item is read against it again.
      j = -1;
    }
  return list;
}

// Outlines of one kind that would touch as drawn become one, and moves that share a
// displacement join within MOVED_REACH.
const join = (marks) =>
  merged(
    marks,
    (p, q) =>
      p.kind === q.kind &&
      (p.kind === "moved"
        ? p.d.join() === q.d.join() && near(p, q, MOVED_REACH)
        : near(p, q, 2 * PAD)),
  );

function words(image) {
  return new Uint32Array(
    image.data.buffer,
    image.data.byteOffset,
    image.width * image.height,
  );
}

// The farthest any channel of two RGBA words lies apart.
function distance(p, q) {
  return Math.max(
    Math.abs((p & 255) - (q & 255)),
    Math.abs(((p >>> 8) & 255) - ((q >>> 8) & 255)),
    Math.abs(((p >>> 16) & 255) - ((q >>> 16) & 255)),
    Math.abs((p >>> 24) - (q >>> 24)),
  );
}

/* Which of four readings a difference is: "identical", "throughout", "slight" (it
 * changed, but nowhere far enough to point at), or "areas", the one with regions. */
export function differenceKind({ changed, throughout, regions }) {
  if (!changed) return "identical";
  if (throughout) return "throughout";
  return regions.length ? "areas" : "slight";
}

/* The reading in a few words: "identical", "changed throughout", "only slight
 * changes", or how many areas changed and moved. An area that changed in place counts
 * once, though both frames outline it; one that moved counts once for its pair. */
export function describeDifference(reading) {
  const kind = differenceKind(reading);
  if (kind !== "areas")
    return {
      identical: "identical",
      throughout: "changed throughout",
      slight: "only slight changes",
    }[kind];
  const { changed: changedCount, moved: movedCount } = countAreas(reading.regions);
  const areas = (n) => `${n} ${n === 1 ? "area" : "areas"}`;
  if (!changedCount) return `${areas(movedCount)} moved`;
  return `${areas(changedCount).replace(" ", " changed ")}${movedCount ? `, ${movedCount} moved` : ""}`;
}

/* How many areas `regions` mark: `changed` and `moved`. A change outlined in both frames,
 * where the two outlines overlap, is one change seen twice and counts once. Each frame
 * leaves out its own moves inside a change, so a move can be drawn in one frame alone;
 * the frame that draws more moves gives their count. */
export function countAreas(regions) {
  const changes = regions.filter((region) => region.kind === "changed");
  const before = changes.filter((region) => region.side === "before");
  const after = changes.filter((region) => region.side === "after");
  const shared = before.filter((p) => after.some((q) => near(p, q, 0))).length;
  return {
    changed: before.length + after.length - shared,
    moved: Math.max(
      ...["before", "after"].map(
        (side) =>
          regions.filter((region) => region.kind === "moved" && region.side === side)
            .length,
      ),
    ),
  };
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
