/* What `architecture/import-layers` refuses (eslint.config.mjs): a runtime module that
   names a module of a layer above its own, by an import or by a type its JSDoc names,
   and a module that stands in no layer. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { importLayersRule } from "../../eslint.config.mjs";
import { ruleReports } from "./lint-rule.mjs";

const at = (name) =>
  fileURLToPath(new URL(`../../browser/runtime/${name}`, import.meta.url));

// How many times the rule reports on `code` in the runtime module `name`.
const reports = (code, name = "records/current-target.js") =>
  ruleReports(importLayersRule, code, { filename: at(name) }).length;

test("a module that names a layer above its own is refused, however it names it", () => {
  for (const code of [
    'import { notice } from "../annotations/preview.js";',
    'const preview = () => import("../annotations/preview.js");',
    'export { notice } from "../annotations/preview.js";',
    'export * from "../annotations/preview.js";',
    '/** @param {import("../annotations/preview.js").Read} read */\nexport const f = (read) => read;',
    '/** @import { Read } from "../annotations/preview.js" */',
    '/** @import {\n *   Read,\n *   Preview,\n * } from "../annotations/preview.js" */',
    // A property of an object typedef, and a template's constraint, which
    // dependency-cruiser's JSDoc reader passed over.
    '/** @typedef {Object} Options\n * @property {import("../annotations/preview.js").Read} read */',
    '/** @template {import("../annotations/preview.js").Read} R @param {R} read */\nexport const f = (read) => read;',
    "// import('../annotations/preview.js') names it in a line comment too.",
  ])
    assert.equal(reports(code), 1, code);
});

test("a module names its own layer, the layers below it and what stands outside them", () => {
  for (const code of [
    'import { allThreads } from "./thread/state.js";',
    'import { focused } from "../dom/focus.js";',
    'import { keeps } from "../lib/keeps.js";',
    'import { html } from "/vendor/lit.js";',
    '/** @typedef {import("../../types/domain.js").Thread} Thread */',
    'import kernel from "../state/kernel-registry.json" with { type: "json" };',
    '/** @import { Command } from "../dom/keyboard/bindings.js" */',
    // A specifier the code computes is the loaders' (eslint.config.mjs, `ownerBoundary`).
    "const load = (path) => import(path);",
  ])
    assert.equal(reports(code), 0, code);
  // An entry point names any layer, and the bottom layer only itself.
  assert.equal(reports('import "./panel/floating-panel.js";', "widget-api.js"), 0);
  assert.equal(
    reports('import { inChrome } from "./ui-marks.js";', "base/voice.js"),
    0,
  );
  assert.equal(reports('import { x } from "../base/voice.js";', "lib/keeps.js"), 0);
  assert.equal(reports('import { x } from "../dom/focus.js";', "lib/keeps.js"), 1);
});

test("a module that stands in no layer is refused", () => {
  assert.equal(reports("export const x = 1;", "stray.js"), 1);
  assert.equal(reports("export const x = 1;", "widget-api.js"), 0);
});
