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
    reportsFor("import {createSemanticApplication} from '/vendor/browser-runtime.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "const {createSemanticApplication} = await import('/vendor/browser-runtime.js')",
    ).length,
    1,
  );
  assert.equal(
    reportsFor("export {createSemanticApplication} from '/vendor/browser-runtime.js'")
      .length,
    1,
  );
  assert.equal(
    reportsFor(
      "export {createSemanticApplication as make} from '/vendor/browser-runtime.js'",
    ).length,
    1,
  );
  assert.equal(reportsFor("export * from '/vendor/browser-runtime.js'").length, 1);
  assert.equal(
    reportsFor("export * as browser from '/vendor/browser-runtime.js'").length,
    1,
  );
  assert.deepEqual(
    reportsFor(
      "import {createSemanticApplication} from '/vendor/browser-runtime.js'",
      "skills/leaf/assets/runtime/semantic-state.js",
    ),
    [],
  );
});

// The type check reads the facade's served path as the framework's source, and a
// relative path as the compiled facade, whose types are blanked.
test("the browser framework's facade is imported by its served path", () => {
  assert.deepEqual(reportsFor("import {signal} from '../vendor/browser-runtime.js'"), [
    "Import the browser framework's facade by its served path, /vendor/browser-runtime.js.",
  ]);
  assert.deepEqual(reportsFor("import {signal} from '/vendor/browser-runtime.js'"), []);
});

// The modules behind the facade are its own, so the facade is the only edge into the
// framework: a deep path is refused whatever it names, semantic-state.js included.
test("a module behind the browser framework's facade is not an import path", () => {
  const facade =
    "Import browser framework capabilities from its facade, vendor/browser-runtime.js.";
  for (const source of [
    "import {createApplicationPublisher} from '../vendor/browser-runtime/snapshot.js'",
    "import {createSemanticApplication} from '../vendor/browser-runtime/application.js'",
    "export {createSemanticApplication} from '../vendor/browser-runtime/application.js'",
    "const {createSemanticApplication} = await import('../vendor/browser-runtime/application.js')",
  ]) {
    assert.deepEqual(reportsFor(source), [facade]);
    assert.deepEqual(
      reportsFor(source, "skills/leaf/assets/runtime/semantic-state.js"),
      [facade],
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
