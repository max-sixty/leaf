/* Every export of widget-api.js is a supported package capability. These checks
   keep that surface and its authoring references together. The module loader,
   exercised by browser tests, owns whether a package's imports actually exist. */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "acorn";

const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SKILL = join(ROOT, "skills/leaf");
const API = "/runtime/widget-api.js";

const read = (path) => readFileSync(path, "utf8");
const parseModule = (code, onComment) =>
  parse(code, { ecmaVersion: "latest", sourceType: "module", onComment });
const scripts = (dir) =>
  readdirSync(dir, { recursive: true })
    .filter((name) => name.endsWith(".js") && !name.split("/").includes("vendor"))
    .map((name) => join(dir, name));

// widget-api.js's exports, the portable ones it re-exports whole included.
function surface(module = "widget-api.js") {
  const program = parseModule(read(join(ROOT, "browser/runtime", module)));
  const exports = new Set();
  for (const node of program.body) {
    if (node.type === "ExportAllDeclaration")
      for (const name of surface(node.source.value.replace(/^\.\//, "")))
        exports.add(name);
    if (node.type !== "ExportNamedDeclaration") continue;
    for (const spec of node.specifiers) exports.add(spec.exported.name);
    const declared = node.declaration;
    if (declared?.id) exports.add(declared.id.name);
    for (const each of declared?.declarations ?? []) exports.add(each.id.name);
  }
  return exports;
}

// The reference's code: inline spans outside code blocks, and the code blocks.
function referenceCode() {
  const references = join(SKILL, "references");
  const text = readdirSync(references)
    .filter((name) => /^module-.*\.md$/.test(name))
    .map((name) => read(join(references, name)))
    .join("\n");
  const blocks = text.match(/^```.*?^```/gms) ?? [];
  const prose = blocks.reduce((rest, block) => rest.replace(block, ""), text);
  const spans = (prose.match(/`[^`]+`/g) ?? []).map((span) =>
    span.slice(1, -1).replace(/\s+/g, " "),
  );
  const code = [...spans, ...blocks].join("\n");
  const imported = new Set(
    blocks.flatMap((block) =>
      [...block.matchAll(/import\s*\{([^}]*)\}\s*from\s*"([^"]+)"/g)]
        .filter((found) => found[2] === API)
        .flatMap((found) => found[1].split(",").map((name) => name.trim()))
        .filter(Boolean),
    ),
  );
  // Names the reference's own code gives as an object's key or shorthand, or defines
  // as a method in an example: an option or hook a widget supplies. A method's head
  // stands on one line, so a span that calls a helper does not read as a method
  // definition because the next span opens a brace.
  const members = new Set(
    [
      ...code.matchAll(/([A-Za-z_$][\w$]*)\s*:/g),
      ...code.matchAll(/^[ \t]*([A-Za-z_$][\w$]*)\([^)\n]*\)[ \t]*\{/gm),
      ...[...code.matchAll(/\{([^{}]*)\}/g)].flatMap((found) =>
        found[1].split(",").map((part) => part.trim().match(/^([A-Za-z_$][\w$]*)$/)),
      ),
    ]
      .filter(Boolean)
      .map((found) => found[1]),
  );
  return { spans, code, imported, members };
}

const leading = (span) => span.match(/^[A-Za-z_$][\w$]*/)?.[0];
const documented = ({ spans, code, imported }) => {
  const names = new Set([...spans.map(leading).filter(Boolean), ...imported]);
  for (const call of code.matchAll(/(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(/g))
    names.add(call[1]);
  return names;
};

// The names runtime modules export, and every name the runtime reads or defines as a
// member, method, object key or parameter.
function runtimeNames() {
  const exports = new Set();
  const members = new Set();
  const walk = (node) => {
    if (!node || typeof node.type !== "string") return;
    if (node.type === "MemberExpression" && !node.computed)
      members.add(node.property.name);
    if (
      ["Property", "MethodDefinition", "PropertyDefinition"].includes(node.type) &&
      node.key.type === "Identifier"
    )
      members.add(node.key.name);
    if (/Function/.test(node.type))
      for (const param of node.params)
        if (param.type === "Identifier") members.add(param.name);
    for (const value of Object.values(node))
      for (const child of Array.isArray(value) ? value : [value]) walk(child);
  };
  for (const path of scripts(join(ROOT, "browser/runtime"))) {
    if (path.endsWith("/widget-api.js")) continue;
    const program = parseModule(read(path));
    for (const node of program.body) {
      if (node.type !== "ExportNamedDeclaration") continue;
      for (const spec of node.specifiers) exports.add(spec.exported.name);
      if (node.declaration?.id) exports.add(node.declaration.id.name);
      for (const each of node.declaration?.declarations ?? [])
        if (each.id.type === "Identifier") exports.add(each.id.name);
    }
    walk(program);
  }
  return { exports, members };
}

test("every public export is documented in the module references", () => {
  const names = documented(referenceCode());
  assert.deepEqual(
    [...surface()].filter((name) => !names.has(name)),
    [],
    "document every package capability in a module-*.md reference",
  );
});

test("every helper the module references call is exported", () => {
  const exported = surface();
  const reference = referenceCode();
  const runtime = runtimeNames();
  const called = new Set(
    reference.spans
      .map((span) => span.match(/^([A-Za-z_$][\w$]*)\((?!-)/)?.[1])
      .filter(Boolean),
  );
  // A name a runtime module exports is a helper, whatever else the runtime calls so.
  const member = (name) =>
    reference.members.has(name) ||
    (runtime.members.has(name) && !runtime.exports.has(name));
  assert.deepEqual(
    [...called].filter((name) => !exported.has(name) && !member(name)),
    [],
    "the module references call these, and widget-api.js does not export them",
  );
  assert.deepEqual(
    [...reference.imported].filter((name) => !exported.has(name)),
    [],
    "the module references' examples import these from widget-api.js, which does not export them",
  );
});
