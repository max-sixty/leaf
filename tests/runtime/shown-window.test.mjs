/* The room the page shows past the chrome: a cover takes the room from itself to the
   edge it stands nearer, read in the viewport the caller asks for, so a visual viewport
   panned to the window's foot doesn't turn the floating panel's layout side around. */

import assert from "node:assert/strict";
import test from "node:test";

const { declareCover, shownWindow } = await import("/runtime/geometry.js");

test("a layout reading takes a cover's side from the layout viewport", (t) => {
  const surface = document.createElement("div");
  t.after(
    declareCover(surface, () => ({ left: 0, top: 500, right: 1000, bottom: 886 })),
  );
  const restore = Object.getOwnPropertyDescriptors(visualViewport);
  t.after(() => {
    for (const name of ["offsetTop", "height"])
      Object.defineProperty(visualViewport, name, restore[name]);
  });
  // A 900px layout viewport whose visual viewport is panned to show y=600-900.
  Object.defineProperty(visualViewport, "offsetTop", {
    configurable: true,
    get: () => 600,
  });
  Object.defineProperty(visualViewport, "height", {
    configurable: true,
    get: () => 300,
  });
  const clientHeight = Object.getOwnPropertyDescriptor(
    document.documentElement,
    "clientHeight",
  );
  Object.defineProperty(document.documentElement, "clientHeight", {
    configurable: true,
    get: () => 900,
  });
  t.after(() =>
    Object.defineProperty(document.documentElement, "clientHeight", clientHeight),
  );

  const layout = shownWindow({ viewport: "layout" });
  assert.deepEqual([layout.top, layout.bottom], [0, 500]);
  const visual = shownWindow();
  assert.deepEqual([visual.top, visual.bottom], [886, 900]);
});
