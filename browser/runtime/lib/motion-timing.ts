// The times and curves a page's stylesheet sets for motion, read so that a script's
// motion and the stylesheet's share one value. CSS owns them as custom properties: the
// document-wide ones on the root, and a surface's own on that surface. A caller names
// the property it reads. A registered <time> resolves variables and calculations before
// this read; each call reads the live cascade, so a revision or theme override changes
// CSS and Web Animations together.

const token = (property: string, on: Element) =>
  getComputedStyle(on).getPropertyValue(property).trim();

// A time-valued custom property, in milliseconds, as `on` inherits or declares it.
export const motionTime = (
  property: string,
  on: Element = document.documentElement,
) => {
  const value = token(property, on);
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1000);
};

// A curve-valued custom property, as Web Animations takes it.
export const motionEasing = (
  property: string,
  on: Element = document.documentElement,
) => token(property, on);
