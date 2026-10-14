/* `runtime/widget-api.js` and the `references/module-*.md` files describe one surface.

   The module is the helper surface package behavior modules import; the references,
   read below as one text, are that surface's documentation for package authors. Every export is one of two kinds,
   read from the module's own source: an export below the module's `// Internal:`
   comment serves Leaf's bundled packages and kernel widgets alone, and every other
   export is the authoring API, which the reference documents. So:

   - an authoring export is named in the reference's code, as a code span it begins,
     a call, or an import in a code example;
   - an internal export is named nowhere in the reference's code, and a bundled package
     or kernel widget imports it (a name only the render gate's probes read belongs in
     check-api.js, and a name nothing reads is deleted);
   - a helper the reference calls, as a code span beginning `name(`, is an export,
     unless `name` is an option or hook the reference's own code gives as an object
     key or method, or a member, object key or parameter the runtime uses and no runtime
     module exports: a controller's method, a hook a widget implements, a callback. */

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

// Each export's name and whether it stands below the `// Internal:` comment.
function surface() {
  const comments = [];
  const program = parseModule(
    read(join(SKILL, "assets/runtime/widget-api.js")),
    comments,
  );
  const markers = comments.filter((c) => c.value.trim().startsWith("Internal:"));
  assert.equal(markers.length, 1, "widget-api.js has one `// Internal:` comment");
  const exports = new Map();
  for (const node of program.body) {
    if (node.type !== "ExportNamedDeclaration") continue;
    const internal = node.start > markers[0].end;
    for (const spec of node.specifiers) exports.set(spec.exported.name, internal);
    const declared = node.declaration;
    if (declared?.id) exports.set(declared.id.name, internal);
    for (const each of declared?.declarations ?? [])
      exports.set(each.id.name, internal);
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

// The names modules under `dir` import from `/runtime/widget-api.js`, including the
// module scripts of its HTML pages.
function importsUnder(dir) {
  const found = new Set();
  const files = readdirSync(dir, { recursive: true }).filter(
    (name) => !name.split("/").includes("vendor"),
  );
  const modules = [
    ...files
      .filter((name) => name.endsWith(".js"))
      .map((name) => read(join(dir, name))),
    ...files
      .filter((name) => name.endsWith(".html"))
      .flatMap((name) =>
        [
          ...read(join(dir, name)).matchAll(
            /<script\b[^>]*type="module"[^>]*>(.*?)<\/script>/gs,
          ),
        ].map((found) => found[1]),
      ),
  ];
  for (const code of modules)
    for (const node of parseModule(code).body)
      if (node.type === "ImportDeclaration" && node.source.value === API)
        for (const spec of node.specifiers)
          if (spec.type === "ImportSpecifier") found.add(spec.imported.name);
  return found;
}

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
  for (const path of scripts(join(SKILL, "assets/runtime"))) {
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

test("every authoring export is documented in the module references", () => {
  const names = documented(referenceCode());
  const missing = [...surface()]
    .filter(([name, internal]) => !internal && !names.has(name))
    .map(([name]) => name);
  assert.deepEqual(
    missing,
    [],
    "document these in a module-*.md reference, or move them below widget-api.js's " +
      "`// Internal:` comment if only Leaf's bundled packages use them",
  );
});

test("every internal export is undocumented and has a bundled importer", () => {
  const names = documented(referenceCode());
  const bundled = new Set([
    ...importsUnder(join(SKILL, "packages")),
    ...importsUnder(join(SKILL, "assets/widgets")),
  ]);
  const internal = [...surface()]
    .filter(([, internal]) => internal)
    .map(([name]) => name);
  assert.deepEqual(
    internal.filter((name) => names.has(name)),
    [],
    "a documented export is authoring API; move it above `// Internal:`",
  );
  assert.deepEqual(
    internal.filter((name) => !bundled.has(name)),
    [],
    "no bundled package or kernel widget imports these; delete them, or move what only " +
      "the render gate reads to check-api.js",
  );
});

test("every name a behavior module imports is exported", () => {
  const exported = surface();
  const imported = new Set(
    [
      "skills/leaf/packages",
      "skills/leaf/assets/widgets",
      "examples",
      "tests/fixtures",
      "tests/browser",
    ].flatMap((dir) => [...importsUnder(join(ROOT, dir))]),
  );
  assert.ok(imported.has("once"), "no import read");
  assert.deepEqual(
    [...imported].filter((name) => !exported.has(name)),
    [],
    "behavior modules import these, and widget-api.js does not export them",
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
