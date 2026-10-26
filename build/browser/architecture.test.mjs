import assert from "node:assert/strict";
import test from "node:test";
import { parse } from "acorn";
import { semanticStoreOwnershipRule } from "../../eslint.config.mjs";

function reportsFor(source, filename = "browser/runtime/example-store.js") {
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
    reportsFor("import {createSemanticApplication} from '/runtime/framework.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "const {createSemanticApplication} = await import('/runtime/framework.js')",
    ).length,
    1,
  );
  assert.equal(
    reportsFor("export {createSemanticApplication} from '/runtime/framework.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "export {createSemanticApplication as make} from '/runtime/framework.js'",
    ).length,
    1,
  );
  assert.equal(reportsFor("export * from '/runtime/framework.js'").length, 1);
  assert.equal(
    reportsFor("export * as browser from '/runtime/framework.js'").length,
    1,
  );
  assert.deepEqual(
    reportsFor(
      "import {createSemanticApplication} from '/runtime/framework.js'",
      "browser/runtime/semantic-state.js",
    ),
    [],
  );
});

// The modules behind the facade are its own, so the facade is the only edge into the
// framework: a deep path is refused whatever it names, semantic-state.js included.
test("a module behind the browser framework's facade is not an import path", () => {
  const facade =
    "Import browser framework capabilities from its facade, runtime/framework.js.";
  for (const source of [
    "import {createApplicationPublisher} from './framework/snapshot.js'",
    "import {createSemanticApplication} from '/runtime/framework/application.js'",
    "export {createSemanticApplication} from './framework/application.js'",
    "const {createSemanticApplication} = await import('./framework/application.js')",
  ]) {
    assert.deepEqual(reportsFor(source), [facade]);
    assert.deepEqual(reportsFor(source, "browser/runtime/semantic-state.js"), [facade]);
  }
  // The facade and the modules behind it reach one another directly.
  for (const filename of [
    "browser/runtime/framework.js",
    "browser/runtime/framework/application.js",
  ])
    assert.deepEqual(
      reportsFor("export {share} from './framework/snapshot.js'", filename),
      [],
    );
});

test("a relative path to the browser framework's facade is the facade", () => {
  assert.equal(
    reportsFor("import {createSemanticApplication} from '../framework.js'").length,
    1,
  );
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
