/* What `architecture/standing-reads` refuses: a raw reading of focus outside focus.js (eslint.config.mjs). eslint lives in pre-commit's environment, so the
   rule's visitors run here over acorn's tree, which is the ESTree eslint hands them. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { standingReadsRule } from "../../eslint.config.mjs";

const runtime = (name) =>
  fileURLToPath(new URL(`../../skills/leaf/assets/runtime/${name}`, import.meta.url));

// How many times the rule reports on `code` in `file`.
function reports(code, file = runtime("probe.js")) {
  let count = 0;
  const visitors = standingReadsRule.create({
    filename: file,
    options: [["skills/leaf/assets/runtime/focus.js"]],
    report: () => (count += 1),
  });
  const walk = (node) => {
    visitors[node.type]?.(node);
    for (const value of Object.values(node))
      for (const child of Array.isArray(value) ? value : [value])
        if (child && typeof child.type === "string") walk(child);
  };
  walk(parse(code, { ecmaVersion: "latest", sourceType: "module" }));
  return count;
}

test("a raw reading of the document's focus is refused outside the owner", () => {
  assert.equal(reports("const at = document.activeElement;"), 1);
  assert.equal(reports("if (box.contains(document.activeElement)) go();"), 1);
  assert.equal(reports("const at = document.activeElement;", runtime("focus.js")), 0);
});

test("a shadow root's or another document's reading is refused too", () => {
  for (const code of [
    "const at = this.shadowRoot.activeElement;",
    "const at = this.getRootNode().activeElement;",
    "const at = node.ownerDocument.activeElement;",
  ])
    assert.equal(reports(code), 1, code);
});

test("a frame's own document is its page's question", () => {
  for (const code of [
    "const at = frame.contentDocument.activeElement;",
    "const at = focused(document);",
  ])
    assert.equal(reports(code), 0, code);
});
