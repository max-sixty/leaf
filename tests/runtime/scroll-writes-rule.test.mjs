/* What `architecture/scroll-writes` refuses of a script's own scroll write
   (eslint.config.mjs). */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { scrollWritesRule } from "../../eslint.config.mjs";
import { ruleReports } from "./lint-rule.mjs";

const at = (path) => fileURLToPath(new URL(`../../${path}`, import.meta.url));
const restorer = "browser/runtime/records/carry.js";

// How many times the rule reports on `code`.
const reports = (code, file = "packages/default/widgets/probe.js") =>
  ruleReports(scrollWritesRule, code, {
    filename: at(file),
    options: [[restorer]],
  }).length;

test("an assigned scroll offset is refused, but for a file the option names", () => {
  for (const code of ["box.scrollTop = 40;", "box.scrollLeft += by;"]) {
    assert.equal(reports(code), 1, code);
    assert.equal(reports(code, restorer), 0, code);
  }
});

test("a scroll call that writes out its options says how it moves the box", () => {
  for (const code of [
    "box.scrollTo({ top: 40 });",
    "box.scrollBy({ left: by });",
    "window.scroll({ [axis]: to });",
    "scrollTo({ top: 40 });",
    // Two offsets can't say it.
    "box.scrollTo(0, 40);",
    "scrollBy(0, by);",
  ]) {
    assert.equal(reports(code), 1, code);
    assert.equal(reports(code, restorer), 1, code);
  }
  for (const code of [
    'box.scrollTo({ top: 40, behavior: "instant" });',
    'box.scrollBy({ left: by, behavior: reduced ? "instant" : "smooth" });',
    'box.scrollTo({ ...at, "behavior": "instant" });',
    // Options a call is handed are their writer's, and a traversal's `scroll()` is
    // no element's.
    "box.scrollTo(options);",
    "box.scrollTo({ ...options });",
    "event.scroll();",
  ])
    assert.equal(reports(code), 0, code);
});
