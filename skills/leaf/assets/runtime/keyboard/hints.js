/* Shared mechanics for transient keyboard hints.

   A hint code is generated from a caller-owned alphabet. Replacing one leaf with all of
   its children keeps the result prefix-free while leaving most targets on one letter;
   only the tail branches when a scene contains more targets than the alphabet. The
   placement pass keeps every generated route visible. Unlike an ordinal address, an
   opaque hint has no meaning once its face is hidden, so collisions are spread rather
   than removed. Geometry belongs to each caller and is passed in so this policy module
   introduces no ownership cycle through the key line. */

export const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];

export function hintCodes(count, keys = HINT_KEYS) {
  const codes = [...keys];
  while (codes.length < count) {
    const shortest = Math.min(...codes.map((code) => code.length));
    const at = codes.findLastIndex((code) => code.length === shortest);
    const parent = codes[at];
    codes.splice(at, 1, ...keys.map((key) => parent + key));
  }
  return codes.slice(0, count);
}

const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

const movedTo = (box, left, top) => ({
  left,
  right: left + box.width,
  top,
  bottom: top + box.height,
  width: box.width,
  height: box.height,
});

const clamp = (value, start, end) => Math.max(start, Math.min(value, end));

function nearestOpenTop(box, preferred, barriers, top, bottom, gap) {
  const last = Math.max(top, bottom - box.height);
  const seats = [preferred, top, last];
  for (const barrier of barriers)
    seats.push(barrier.bottom + gap, barrier.top - gap - box.height);
  return seats
    .map((seat) => clamp(seat, top, last))
    .filter(
      (seat) =>
        !barriers.some((barrier) => overlaps(movedTo(box, box.left, seat), barrier)),
    )
    .sort((left, right) => Math.abs(left - preferred) - Math.abs(right - preferred))[0];
}

// Read every face before moving one, keeping the pass to one layout. Callers append all
// chips first and provide the visible rectangle each chip names.
export function spreadHints(
  hints,
  {
    lineBox,
    viewportLeft = 0,
    viewportTop = 0,
    viewportRight = document.documentElement.clientWidth,
    viewportBottom = document.documentElement.clientHeight,
  } = {},
) {
  const gap = 2;
  // The browsed hint wears the layer's band (--here-shadow, theme.css), which a face's
  // own rectangle does not report. Any chip can become the browsed one as the reader
  // types, so the pass seats every face as though it were, keeping the one layout. A
  // window edge takes the whole band, because a band drawn past it is clipped away. A
  // barrier — another face, or the key line — takes the wider of the gap and the band,
  // because a band may stand in the gap it keeps but not past it; only the browsed chip
  // paints one, so it has that space to itself. Seated to the gap alone both cleared by
  // coincidence, the gap and the band both being 2px.
  const band =
    parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--here-ring-w"),
    ) || 0;
  const clear = Math.max(gap, band);
  const line = lineBox ?? { left: 0, top: viewportBottom, right: 0, height: 0 };
  const lineBand = {
    left: line.left,
    top: line.top,
    right: line.right,
    bottom: viewportBottom,
  };
  const edgeLeft = viewportLeft + band;
  const edgeTop = viewportTop + band;
  const edgeRight = viewportRight - band;
  const edgeBottom = viewportBottom - band;
  const measured = hints.map(({ chip, target }) => {
    const start = chip.getBoundingClientRect();
    const first = movedTo(
      start,
      clamp(start.left, edgeLeft, Math.max(edgeLeft, edgeRight - start.width)),
      clamp(start.top, edgeTop, Math.max(edgeTop, edgeBottom - start.height)),
    );
    const rightSeat = Math.max(target.left, line.right + clear);
    const canSitRight = rightSeat + start.width <= Math.min(target.right, edgeRight);
    const left =
      line.height && overlaps(first, lineBand) && canSitRight ? rightSeat : first.left;
    return [chip, movedTo(first, left, first.top), start];
  });
  const placed = [];
  for (const [chip, seated, start] of measured) {
    const barriers = placed.filter(
      (other) => other.left < seated.right && seated.left < other.right,
    );
    if (
      lineBand.bottom > lineBand.top &&
      lineBand.left < seated.right &&
      seated.left < lineBand.right
    )
      barriers.push(lineBand);
    const top = nearestOpenTop(
      seated,
      seated.top,
      barriers,
      edgeTop,
      edgeBottom,
      clear,
    );
    // A viewport can be physically too small for every face. Keep the preferred clamped
    // seat in that impossible case; ordinary scenes always have an open interval, and
    // the invariant tests exercise collisions at every viewport edge.
    const box = movedTo(seated, seated.left, top ?? seated.top);
    const sideShift = box.left - start.left;
    const shift = box.top - start.top;
    if (sideShift) chip.style.left = `${parseFloat(chip.style.left) + sideShift}px`;
    if (shift) chip.style.top = `${parseFloat(chip.style.top) + shift}px`;
    placed.push(box);
  }
}
