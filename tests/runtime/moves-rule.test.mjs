/* What `architecture/moves` refuses as a plain insertion of a node that may already
   stand somewhere (eslint.config.mjs). eslint lives in pre-commit's environment, so the
   rule's visitors run here over acorn's tree, which is the ESTree eslint hands them. */

import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";
import { movesRule } from "../../eslint.config.mjs";

const filename = fileURLToPath(
  new URL("../../skills/leaf/assets/runtime/probe.js", import.meta.url),
);

// How many times the rule reports on `code`.
function reports(code, file = filename) {
  let count = 0;
  const visitors = movesRule.create({
    filename: file,
    options: [["skills/leaf/assets/runtime/dom-move.js"]],
    sourceCode: { getText: (node) => code.slice(node.start, node.end) },
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

test("placing a node that may stand elsewhere is refused", () => {
  for (const code of [
    // The response bar's seats before they went through `move`.
    "if (bar.parentElement !== parent) parent.append(bar);",
    "if (bar.parentNode !== outlet) outlet.append(bar);",
    "if (frame.contains(floating)) frame.before(floating);",
    "if (last.nextElementSibling !== root) last.after(root);",
    "chip.parentElement !== seat && seat.replaceChildren(chip);",
    "a.insertBefore(node, b);",
    "a.moveBefore(node, b);",
  ])
    assert.equal(reports(code), 1, code);
});

test("placing a new node, or one the condition does not place, is admitted", () => {
  for (const code of [
    "parent.append(node);",
    "a.insertBefore(document.createElement('div'), b);",
    "a.insertBefore(template.content.cloneNode(true), b);",
    // A node out of the document holds no focus to lose.
    "if (!seat.isConnected) root.append(seat);",
    "if (other.parentNode) parent.append(node);",
    "if (bar.parentNode !== outlet) later(() => outlet.append(bar));",
  ])
    assert.equal(reports(code), 0, code);
});

test("the mover itself may call the platform's movers", () => {
  const mover = fileURLToPath(
    new URL("../../skills/leaf/assets/runtime/dom-move.js", import.meta.url),
  );
  assert.equal(reports("parent.moveBefore(node, before);", mover), 0);
});
