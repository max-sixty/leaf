/* What `architecture/import-layers` refuses (eslint.config.mjs): a runtime module that
   names a module of a layer above its own, by an import or by a type its JSDoc names,
   and a module that stands in no layer. */

import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import config, { importLayersRule } from "../../eslint.config.mjs";
import { ruleReports } from "./lint-rule.mjs";

const at = (name) =>
  fileURLToPath(new URL(`../../browser/runtime/${name}`, import.meta.url));

// How many times the rule reports on `code` in the runtime module `name`.
const reports = (code, name = "records/current-target.js") =>
  ruleReports(importLayersRule, code, { filename: at(name) }).length;

test("a module that names a layer above its own is refused, however it names it", () => {
  for (const code of [
    'import { mountPreviews } from "../annotations/preview.js";',
    'const preview = () => import("../annotations/preview.js");',
    'export { mountPreviews } from "../annotations/preview.js";',
    'export * from "../annotations/preview.js";',
    // The same module by the path a page serves it at, and by one that climbs out of the
    // runtime and back in.
    'import { mountPreviews } from "/runtime/annotations/preview.js";',
    'export { mountPreviews } from "../../runtime/annotations/preview.js";',
    '/** @param {import("../annotations/preview.js").Target} target */\nexport const f = (target) => target;',
    '/** @import { Target } from "../annotations/preview.js" */',
    '/** @import {\n *   Target,\n *   Reading,\n * } from "../annotations/preview.js" */',
    // A property of an object typedef, and a template's constraint.
    '/** @typedef {Object} Options\n * @property {import("../annotations/preview.js").Target} target */',
    '/** @template {import("../annotations/preview.js").Target} T @param {T} target */\nexport const f = (target) => target;',
    // Whitespace between the tokens, a line's break among them.
    '/** @param {import ("../annotations/preview.js").Target} target */\nexport const f = (target) => target;',
    '/** @param {import(\n *   "../annotations/preview.js"\n * ).Target} target */\nexport const f = (target) => target;',
  ])
    assert.equal(reports(code), 1, code);
});

test("a module names its own layer, the layers below it and what stands outside them", () => {
  for (const code of [
    'import { allThreads } from "./thread/state.js";',
    'import { focused } from "../dom/focus.js";',
    'import { keeps } from "../lib/keeps.js";',
    'import { focused } from "/runtime/dom/focus.js";',
    'import { html } from "/vendor/lit.js";',
    'import { probe } from "/checks/probe.js";',
    'import { parse } from "acorn";',
    '/** @typedef {import("../../types/domain.js").Thread} Thread */',
    'import kernel from "../state/kernel-registry.json" with { type: "json" };',
    '/** @import { Command } from "../dom/keyboard/bindings.js" */',
    // A comment that is no JSDoc names no type, whatever it says.
    "// Never import('../annotations/preview.js') here: the margin owns it.",
    '/* import("../annotations/preview.js") would load the overlay. */',
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
  assert.equal(reports('export * from "./annotations/preview.js";', "stray.mjs"), 1);
  assert.equal(reports("export const x = 1;", "widget-api.js"), 0);
});

// The rule eslint.config.mjs sets for `file`, as eslint composes its config objects:
// the last that matches the file and sets the rule wins.
const ruleFor = (file) => {
  let setting;
  for (const block of config)
    if (
      block.rules?.["architecture/import-layers"] !== undefined &&
      (block.files ?? ["**/*"]).some((glob) => path.matchesGlob(file, glob)) &&
      !(block.ignores ?? []).some((glob) => path.matchesGlob(file, glob))
    )
      setting = block.rules["architecture/import-layers"];
  return setting;
};

test("every runtime module is linted for its layer, a .mjs one among them", () => {
  for (const file of [
    "browser/runtime/records/current-target.js",
    "browser/runtime/stray.mjs",
    "browser/runtime/widget-api.js",
  ])
    assert.equal(ruleFor(file), "error", file);
});
