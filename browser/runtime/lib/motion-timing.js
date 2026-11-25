// The times and curves a page's stylesheet sets for motion, read so that a script's
// motion and the stylesheet's share one value. CSS owns them as custom properties: the
// document-wide ones on the root, and a surface's own on that surface. A caller names
// the property it reads. A registered <time> resolves variables and calculations before
// this read; each call reads the live cascade, so a revision or theme override changes
// CSS and Web Animations together.

/** @param {string} property @param {Element} on */
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();

// A time-valued custom property, in milliseconds, as `on` inherits or declares it.
/** @param {string} property @param {Element} [on] */
export const motionTime = (property, on = document.documentElement) => {
  const value = token(property, on);
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1000);
};

// How a script's scroll moves: a glide, or a jump for a user who asked for less
// motion, as `scrollIntoView` and `scrollTo` take it.
/** @returns {ScrollBehavior} */
export const glide = () =>
  matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";

// A curve-valued custom property, as Web Animations takes it.
/** @param {string} property @param {Element} [on] */
export const motionEasing = (property, on = document.documentElement) =>
  token(property, on);
