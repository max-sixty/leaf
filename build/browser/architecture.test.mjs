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
  assert.equal(
    reportsFor("export {createSemanticApplication} from '../vendor/browser-runtime.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "export {createSemanticApplication as make} from '../vendor/browser-runtime.js'",
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

// The raw publisher is private to every module, semantic-state.js included, so it
// carries the other message on each path the named one is read along.
test("the raw publisher stays private on every path that names it", () => {
  const raw = "The raw publisher is private to the semantic application.";
  for (const source of [
    "import {createApplicationPublisher} from '../vendor/browser-runtime.js'",
    "export {createApplicationPublisher} from '../vendor/browser-runtime.js'",
  ]) {
    assert.deepEqual(reportsFor(source), [raw]);
    assert.deepEqual(
      reportsFor(source, "skills/leaf/assets/runtime/semantic-state.js"),
      [raw],
    );
  }
});

// `export * as ns from` is an ExportAllDeclaration carrying `exported`, not an
// ExportNamedDeclaration holding an ExportNamespaceSpecifier, so the namespace arm the
// rule used to keep beside its named arm could not run. The whole-namespace reexport is
// read above; this states the parse shape that leaves one reader of it.
test("a namespace reexport is one declaration, not a named one with a specifier", () => {
  const [node] = parse("export * as browser from './x.js'", {
    ecmaVersion: "latest",
    sourceType: "module",
  }).body;
  assert.equal(node.type, "ExportAllDeclaration");
  assert.equal(node.exported.name, "browser");
});
