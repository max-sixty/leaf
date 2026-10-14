import assert from "node:assert/strict";
import test from "node:test";
import { widgetImports } from "/runtime/widget-imports.js";

test("declared creations prepare shadow rules before any child exists", () => {
  const scope = document.createElement("main");
  scope.innerHTML = '<lf-nursery id="nursery"></lf-nursery>';
  const registry = {
    "lf-nursery": { "x-upgrade": true },
    "lf-seedling": { "x-shadow": true },
  };
  assert.deepEqual(widgetImports(scope, registry), {
    initializers: [],
    modules: ["lf-nursery"],
    shadow: false,
  });

  registry["lf-nursery"]["x-state"] = {
    sow: { creates: { child: "lf-seedling", words: "label" } },
  };
  assert.deepEqual(widgetImports(scope, registry), {
    initializers: [],
    modules: ["lf-nursery"],
    shadow: true,
  });
});
