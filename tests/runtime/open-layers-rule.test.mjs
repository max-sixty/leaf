/* What `architecture/open-layers` refuses (eslint.config.mjs).

   Whether a node is an open native layer, or stands in one, is layer-stack.js's
   question, so a selector naming the open state is refused wherever it is asked, and
   a selector about anything else passes. eslint lives in pre-commit's environment,
   not this one, so the rule's visitors run here over acorn's tree, which is the
   ESTree eslint hands them. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { openLayersRule } from "../../eslint.config.mjs";

const at = (path) => fileURLToPath(new URL(`../../${path}`, import.meta.url));

// How many times the rule reports on `code` in `file`.
function reports(code, file = "skills/leaf/assets/runtime/probe.js") {
  let count = 0;
  const visitors = openLayersRule.create({
    filename: at(file),
    options: [["skills/leaf/assets/runtime/keyboard/layer-stack.js"]],
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

test("a selector asking for the open state is refused", () => {
  for (const code of [
    'menu.matches(":popover-open");',
    'node.closest("dialog[open]");',
    'node.closest(":popover-open, dialog:modal");',
    'view.matches(":modal");',
    'document.querySelectorAll(":popover-open");',
    "root.querySelector(`${tag}:popover-open`);",
  ])
    assert.equal(reports(code), 1, code);
});

test("other selectors, and the owner, pass", () => {
  for (const code of [
    'node.closest("dialog");',
    'row.closest(".lf-queue-done:not([open])");',
    'box.querySelector(":scope > .lf-thread[open]");',
    'el.matches("[popover]");',
    "isNativeLayer(menu);",
  ])
    assert.equal(reports(code), 0, code);
  assert.equal(
    reports(
      'node.matches(":modal");',
      "skills/leaf/assets/runtime/keyboard/layer-stack.js",
    ),
    0,
  );
});
