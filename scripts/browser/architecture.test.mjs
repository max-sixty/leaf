import assert from "node:assert/strict";
import test from "node:test";
import { parse } from "acorn";
import { semanticStoreOwnershipRule } from "../../eslint.config.mjs";

function reportsFor(source, filename = "skills/leaf/assets/runtime/example-store.js") {
  const reports = [];
  const visitors = semanticStoreOwnershipRule.create({
    filename,
    report(finding) {
      reports.push(finding.message);
    },
  });
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    visitors[node.type]?.(node);
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) value.forEach(visit);
      else if (value?.type) visit(value);
    }
  };
  visit(parse(source, { ecmaVersion: "latest", sourceType: "module" }));
  return reports;
}

test("semantic publisher ownership closes every browser framework import path", () => {
  assert.equal(
    reportsFor("import {createSemanticApplication} from '../vendor/browser-runtime.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "const {createSemanticApplication} = await import('../vendor/browser-runtime.js')",
    ).length,
    1,
  );
  assert.equal(reportsFor("export * from '../vendor/browser-runtime.js'").length, 1);
  assert.equal(
    reportsFor("export * as browser from '../vendor/browser-runtime.js'").length,
    1,
  );
  assert.deepEqual(
    reportsFor(
      "import {createSemanticApplication} from '../vendor/browser-runtime.js'",
      "skills/leaf/assets/runtime/semantic-state.js",
    ),
    [],
  );
});
