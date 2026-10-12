/* The file a served page answers a root-absolute module specifier with.

   A served page answers the runtime's modules at `/runtime/…`, its vendored bundles at
   `/vendor/…` and its widget modules at `/widgets/…`. Each of those three is a composed
   directory rather than one place on disk: the layer's own, then every selected
   package's, the last to hold a name winning (`composed_dir_files` in `layer.py`). A
   bundle in particular lives in the package whose widget imports it, so mapping
   `/vendor/` onto the layer's half alone would send a widget to a path that never held
   its bundle. No test selects packages, so the composition here is every bundled one. */

import { existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

const at = (path) => fileURLToPath(new URL(path, import.meta.url));
const PACKAGES = at("../skills/leaf/packages");
const ROOTS = [
  at("../skills/leaf/assets"),
  ...readdirSync(PACKAGES, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => `${PACKAGES}/${entry.name}`)
    .sort(),
];

// The absolute path of `specifier`'s file, or undefined where it names none.
export const served = (specifier) =>
  /^\/(runtime|vendor|widgets)\//.test(specifier)
    ? ROOTS.map((root) => root + specifier).findLast(existsSync)
    : undefined;
