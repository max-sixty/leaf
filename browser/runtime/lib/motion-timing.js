// What the browser and the page's stylesheet say about motion's timing: whether the
// user asked for less of it (`reducedMotion`, `scrollBehavior`,
// `onMotionPreferenceChange`), and the times and curves the stylesheet sets
// (`motionTime`, `motionEasing`).

// A stylesheet's reduced-motion guard covers CSS animation and transitions; motion
// driven from JS, such as a smooth scroll or a Web Animation, checks this instead.
const preference = matchMedia("(prefers-reduced-motion: reduce)");
export const reducedMotion = () => preference.matches;
export const scrollBehavior = () => (preference.matches ? "instant" : "smooth");
// Hear the preference change, with whether the user now asks for less motion. The
// returned function stops hearing.
/** @param {(reduced: boolean) => void} listener */
export function onMotionPreferenceChange(listener) {
  const changed = (/** @type {MediaQueryListEvent} */ event) => listener(event.matches);
  preference.addEventListener("change", changed);
  return () => preference.removeEventListener("change", changed);
}

// CSS owns the durations and curves shared with stylesheet motion: the document-wide
// ones on the root, and a surface's own on that surface. A caller names the property it
// reads. Registered <time> values resolve variables and calculations before this read;
// each call reads the live cascade, so a revision or theme override changes CSS and Web
// Animations together.
/** @param {string} property @param {Element} on */
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
// A time-valued custom property, in milliseconds, as `on` inherits or declares it.
/** @param {string} property @param {Element} [on] */
export const motionTime = (property, on = document.documentElement) => {
  const value = token(property, on);
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1000);
};
// A curve-valued custom property, as Web Animations takes it.
/** @param {string} property @param {Element} [on] */
export const motionEasing = (property, on = document.documentElement) =>
  token(property, on);
