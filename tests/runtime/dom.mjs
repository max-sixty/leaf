/* The world a runtime module is imported into by `pnpm run test:runtime`.

   A fold needs no browser, but the modules holding folds are written for one: they sit
   in files that also reach for `document`, `customElements`, or a DOM type at module
   scope, and an import that found none of those would fail before any test ran.
   happy-dom supplies the document object model itself — nodes, trees, selectors,
   ranges, and the geometry types — in this process.

   A served page answers those modules at `/runtime/…`, its vendored bundles at
   `/vendor/…` and its widget modules at `/widgets/…`, so that is how the runtime imports
   them, and Node reads a root-absolute specifier as a path from the filesystem root.
   Each of those three is a composed directory rather than one place on disk: the layer's
   own, then every selected package's, the last to hold a name winning
   (`composed_dir_files` in `layer.py`). A bundle in particular lives in the package
   whose widget imports it, so mapping `/vendor/` onto the layer's half alone would send
   a widget to a path that never held its bundle. No test selects packages, so the
   composition here is every bundled one.

   This is not Chrome, and which readings may be asked of it is `tests/AGENTS.md`'s,
   under "Put each assertion at the boundary that owns it". */

import { existsSync, readdirSync } from "node:fs";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register({ url: "https://leaf.test/" });
// Nothing is laid out here, so every box is whatever a test states. The window is the
// one box this world states itself, as a browser does: the root reports its size, and
// the visual viewport, which happy-dom lacks and geometry.js reads (`shownWindow`) and
// listens to (`whenNone`), covers it unzoomed.
for (const [name, size] of [
  ["clientWidth", () => innerWidth],
  ["clientHeight", () => innerHeight],
])
  Object.defineProperty(document.documentElement, name, {
    configurable: true,
    get: size,
  });
const viewport = new window.EventTarget();
for (const [name, read] of Object.entries({
  offsetLeft: () => 0,
  offsetTop: () => 0,
  pageLeft: () => scrollX,
  pageTop: () => scrollY,
  width: () => innerWidth,
  height: () => innerHeight,
  scale: () => 1,
}))
  Object.defineProperty(viewport, name, { configurable: true, get: read });
window.visualViewport ??= viewport;
// happy-dom's computed style is the declared style: no initial values, and no
// shorthand expanded. The runtime names the values it acts on, so a property left
// unset reads as its initial value, but it reads overflow per axis, which a test may
// declare with the shorthand. So each axis computes as CSS says: from its own
// declaration or the shorthand, and `visible` (or `clip`) beside an axis that scrolls
// computes `auto` (or `hidden`).
const SCROLLING = /^(auto|scroll|hidden)$/;
const declaredStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = (element, pseudo) => {
  const style = declaredStyle(element, pseudo);
  // Read at each access, as a browser's computed style is live.
  const axis = (name) => {
    const [x = "visible", y = x] = style.overflow.split(/\s+/).filter(Boolean);
    const declared = {
      overflowX: style.overflowX || x,
      overflowY: style.overflowY || y,
    };
    const other = declared[name === "overflowX" ? "overflowY" : "overflowX"];
    if (!SCROLLING.test(other)) return declared[name];
    return { visible: "auto", clip: "hidden" }[declared[name]] ?? declared[name];
  };
  return new Proxy(style, {
    get(target, key) {
      if (key === "overflowX" || key === "overflowY") return axis(key);
      const value = Reflect.get(target, key, target);
      return typeof value === "function" ? value.bind(target) : value;
    },
  });
};
// What a delivered document's prepaint declares before any module runs
// (`runtime/prepaint.js`): the page's storage scope, "" for a page at the origin's root.
document.documentElement.dataset.lfPageScope = "";
await import("../../skills/leaf/assets/runtime/prepaint.js");
// And the runtime sheets every delivery carries (`delivery_sheets` in
// revision_delivery.py), which `runtime/stylesheets.js` constructs as it evaluates.
// Nothing here is laid out, so their rules are empty.
const sheets = document.createElement("script");
sheets.type = "application/json";
sheets.dataset.lfRuntime = "";
sheets.dataset.lfSheets = "";
sheets.textContent = JSON.stringify({ chrome: "", marks: "" });
document.head.append(sheets);

const at = (path) => fileURLToPath(new URL(path, import.meta.url));
const PACKAGES = at("../../skills/leaf/packages");
const ROOTS = [
  at("../../skills/leaf/assets"),
  ...readdirSync(PACKAGES, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => `${PACKAGES}/${entry.name}`)
    .sort(),
];

const composed = (specifier) =>
  ROOTS.map((root) => root + specifier).findLast(existsSync);

// A test's comparisons go through `assert.mjs`, which writes a node as its opening tag.
const ASSERT = pathToFileURL(at("./assert.mjs")).href;

registerHooks({
  resolve(specifier, context, next) {
    if (specifier === "node:assert/strict" && context.parentURL !== ASSERT)
      return { url: ASSERT, shortCircuit: true };
    if (/^\/(runtime|vendor|widgets)\//.test(specifier)) {
      // An unanswered one falls through, so it reads as the module Node could not find
      // rather than as a missing file at a path the layer would never have served it at.
      const file = composed(specifier);
      if (file) return { url: pathToFileURL(file).href, shortCircuit: true };
    }
    return next(specifier, context);
  },
});
