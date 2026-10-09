/* What `architecture/layer-returns` admits as a layer's return (eslint.config.mjs).

   A hand-back stands only in a landing's own synchronous body, a close's `close`
   places nothing, and a return written out by hand after a hide is a layer return.
   eslint itself lives in pre-commit's environment, not this one, so the rule's
   visitors run here over acorn's tree, which is the ESTree eslint hands them. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { layerReturnsRule } from "../../eslint.config.mjs";

const filename = fileURLToPath(
  new URL("../../skills/leaf/assets/runtime/probe.js", import.meta.url),
);

// How many times the rule reports on `code`.
function reports(code) {
  let count = 0;
  const visitors = layerReturnsRule.create({
    filename,
    options: [],
    report: () => (count += 1),
  });
  const walk = (node, parent) => {
    node.parent = parent;
    visitors[node.type]?.(node);
    for (const [key, value] of Object.entries(node)) {
      if (key === "parent") continue;
      for (const child of Array.isArray(value) ? value : [value])
        if (child && typeof child.type === "string") walk(child, node);
    }
  };
  walk(parse(code, { ecmaVersion: "latest", sourceType: "module" }), null);
  return count;
}

test("a landing's own body may hand the user back", () => {
  for (const code of [
    "closeLayer(() => a.remove(), () => handBack(a));",
    "closeLayer(hide, open && (() => handBack(a)));",
    "closeLayer(hide, standing ? () => handBack(a) : letGo);",
    "const land = layerLanding((a) => handBack(a));",
    "closeLayer(() => (box.hidden = true), () => focusDestination(a, 'return'));",
    "focusDestination(a, 'return');",
    "box.addEventListener('x', () => box.hidePopover()); focusDestination(a, 'return');",
  ])
    assert.equal(reports(code), 0, code);
});

test("a return anywhere else is refused", () => {
  for (const code of [
    "export const landOnThing = (a) => handBack(a);",
    "closeLayer(() => handBack(a), null);",
    "closeLayer(() => focusDestination(a, 'return'));",
    "closeLayer(() => letGo());",
    "closeLayer(hide, handBack(a));",
    "closeLayer(hide, () => setTimeout(() => handBack(a)));",
    "closeLayer(hide, () => closeLayer(() => handBack(a)));",
    "layerLanding(async () => { await null; handBack(a); });",
    "import { handBack as back } from './focus.js'; back(a);",
    "run(handBack);",
    "function f(d, a) { d.close(); focusDestination(a, 'return'); }",
    "function f(b, a) { b.hidden = true; if (a) focusDestination(a, 'return'); }",
    "import { focusDestination as put } from './focus.js';" +
      " function f(b, a) { b.style.display = 'none'; put(a, 'return'); }",
  ])
    assert.equal(reports(code), 1, code);
});
