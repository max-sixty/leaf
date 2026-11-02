/* Review pace changes wall time, never the recording clock or capture order.
 * Explicit important intervals run at 0.35x; quiet intervals run at 3x.
 * Integrating at every boundary prevents a slow frame from jumping over an
 * important interval. Recorded pace uses no intervals and stays at 1x. */
/** @typedef {[start: number, end: number]} Interval */
/** @param {number} time @param {number} elapsed @param {Interval[] | null} [intervals] */
export function advancePlayback(time, elapsed, intervals = null) {
  if (!intervals) return time + elapsed;
  while (elapsed > 0) {
    const active = intervals.find(([start, end]) => time >= start && time < end);
    const rate = active ? 0.35 : 3;
    const boundary = active
      ? active[1]
      : (intervals.find(([start]) => start > time)?.[0] ?? Infinity);
    const remaining = (boundary - time) / rate;
    if (elapsed <= remaining) return time + elapsed * rate;
    time = boundary;
    elapsed -= remaining;
  }
  return time;
}

/** @param {Interval[]} intervals */
export function mergeIntervals(intervals) {
  /** @type {Interval[]} */
  const merged = [];
  for (const [start, end] of intervals.toSorted((a, b) => a[0] - b[0])) {
    const previous = merged.at(-1);
    if (previous && start <= previous[1]) previous[1] = Math.max(previous[1], end);
    else merged.push([start, end]);
  }
  return merged;
}
