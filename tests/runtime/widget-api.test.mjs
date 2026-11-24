/* Every export of widget-api.js is a supported package capability. These checks
   keep that surface and its authoring references together: module-authoring.md lists
   every export under the section that describes it ("Functions"), and the checks hold
   that list to the exports and each entry to its section. The module loader, exercised
   by browser tests, owns whether a package's imports actually exist.

   The library of shared web code (browser/runtime/lib/) is not part of that surface:
   each module documents itself, and the references name only its directory. The one
   check here holds the list that admits a package's import of a library module to
   the directory. */

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

const REFERENCES = join(SKILL, "references");

// A text's code: inline spans outside code blocks, and the code blocks.
function codeOf(text) {
  const blocks = text.match(/^```.*?^```/gms) ?? [];
  const prose = blocks.reduce((rest, block) => rest.replace(block, ""), text);
  const spans = (prose.match(/`[^`]+`/g) ?? []).map((span) =>
    span.slice(1, -1).replace(/\s+/g, " "),
  );
  return { blocks, spans, code: [...spans, ...blocks].join("\n") };
}

function referenceCode() {
  const text = readdirSync(REFERENCES)
    .filter((name) => /^module-.*\.md$/.test(name))
    .map((name) => read(join(REFERENCES, name)))
    .join("\n");
  const { blocks, spans, code } = codeOf(text);
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

// The index of functions in module-authoring.md, "Functions": each list item names a
// section and the exports that section describes, under a line naming the file that
// holds the section.
function functionIndex() {
  const text = read(join(REFERENCES, "module-authoring.md"));
  const start = text.indexOf("\n### Functions\n");
  const index = text.slice(start, text.indexOf("\n### ", start + 1));
  const entries = [];
  let file = "module-authoring.md";
  for (const part of index.split(/\n\n+/)) {
    if (part.startsWith("In this file")) file = "module-authoring.md";
    file = part.match(/^In \[(module-[a-z-]+\.md)\]/)?.[1] ?? file;
    // An item's lines join, so a title or a list of names that wraps reads whole.
    for (const item of part.split(/\n(?=- )/)) {
      const entry = item.replace(/\s+/g, " ").match(/^- "([^"]+)": (.*)$/);
      if (!entry) continue;
      const names = [...entry[2].matchAll(/`([A-Za-z_$][\w$]*)`/g)];
      entries.push({ file, heading: entry[1], names: names.map((name) => name[1]) });
    }
  }
  return entries;
}

// A section of a reference: from its heading to the next heading of its level or
// above, outside code blocks.
function sectionOf(file, heading) {
  const section = [];
  let level = 0;
  let fenced = false;
  for (const line of read(join(REFERENCES, file)).split("\n")) {
    if (line.startsWith("```")) fenced = !fenced;
    const depth = fenced ? 0 : (line.match(/^(#+) /)?.[1].length ?? 0);
    if (level && depth && depth <= level) break;
    if (!level && depth && line.slice(depth + 1) === heading) level = depth;
    if (level) section.push(line);
  }
  return level ? section.join("\n") : null;
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

test("a page or package may import every module of the library", () => {
  const kernel = JSON.parse(read(join(ROOT, "browser/runtime/kernel-registry.json")));
  const library = "/runtime/lib/";
  assert.deepEqual(
    kernel["$public-modules"].paths
      .filter((path) => path.startsWith(library))
      .toSorted(),
    readdirSync(join(ROOT, "browser/runtime/lib"))
      .filter((name) => name.endsWith(".js"))
      .map((name) => library + name)
      .toSorted(),
    "`$public-modules` in kernel-registry.json lists exactly the modules of browser/runtime/lib/",
  );
});

test("the function index lists every public export once", () => {
  assert.deepEqual(
    functionIndex()
      .flatMap((entry) => entry.names)
      .toSorted(),
    [...surface()].toSorted(),
    'module-authoring.md, "Functions", lists exactly the exports of widget-api.js',
  );
});

test("each indexed function is described in the section its entry names", () => {
  const missing = [];
  for (const { file, heading, names } of functionIndex()) {
    const section = sectionOf(file, heading);
    if (section === null) {
      missing.push(`${file} has no section "${heading}"`);
      continue;
    }
    const words = new Set(codeOf(section).code.match(/[A-Za-z_$][\w$]*/g));
    for (const name of names)
      if (!words.has(name))
        missing.push(`${file}, "${heading}", names no ${name} in its code`);
  }
  assert.deepEqual(
    missing,
    [],
    "each index entry points at the section that describes its functions",
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
