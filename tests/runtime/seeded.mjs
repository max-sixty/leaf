/* A seeded generator of numbers in [0, 1), so a runtime test that draws its cases at
   random names a run that fails again. Its arithmetic is exact in 32-bit integers, so
   a long run doesn't fall into a short cycle. */

/** @param {number} seed */
export function random(seed) {
  let s = seed >>> 0;
  return () => (s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 2 ** 32;
}
