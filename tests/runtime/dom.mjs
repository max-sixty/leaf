/* The world a runtime module is imported into by `npm run test:runtime`.

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

   This is not Chrome, and which readings may be asked of it is `tests/CLAUDE.md`'s,
   under "Put each assertion at the boundary that owns it". */

import { existsSync, readdirSync } from "node:fs";
import { registerHooks } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { GlobalRegistrator } from "@happy-dom/global-registrator";

GlobalRegistrator.register({ url: "https://leaf.test/" });

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

registerHooks({
  resolve(specifier, context, next) {
    if (/^\/(runtime|vendor|widgets)\//.test(specifier)) {
      // An unanswered one falls through, so it reads as the module Node could not find
      // rather than as a missing file at a path the layer would never have served it at.
      const file = composed(specifier);
      if (file) return { url: pathToFileURL(file).href, shortCircuit: true };
    }
    return next(specifier, context);
  },
});
