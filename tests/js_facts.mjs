// What the suite's Python tests read out of JavaScript and TypeScript modules, from the
// parsed module rather than its text, so a statement wrapped across lines, quoted
// differently or commented out reads as the module means it. One command per reading:
//
//   node tests/js_facts.mjs keydown FILE...   `name:line` of every keydown listener
//   node tests/js_facts.mjs exports FILE...   {file: {names, default}} per module
//   node tests/js_facts.mjs queries FILE...   {file: [selector]} handed to DOM queries
//   node tests/js_facts.mjs literals FILE...  {file: {constants, calls}} string literals
//
// Every module is read with acorn. A TypeScript module is read once amaro has blanked
// its types in place, so what it exports is what it runs: a type, which nothing runs,
// is not counted.
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "acorn";
import amaro from "amaro";

const [command, ...files] = process.argv.slice(2);

function tree(file) {
  let source = readFileSync(file, "utf8");
  if (file.endsWith(".ts"))
    source = amaro.transformSync(source, { mode: "strip-only" }).code;
  return parse(source, {
    ecmaVersion: "latest",
    sourceType: "module",
    locations: true,
  });
}

// Every node below `node`, each with the `for (… of [...])` loop variables in scope.
function walk(node, visit, loops = new Map()) {
  if (!node || typeof node.type !== "string") return;
  let inner = loops;
  if (
    node.type === "ForOfStatement" &&
    node.right.type === "ArrayExpression" &&
    node.left.type === "VariableDeclaration"
  ) {
    const name = node.left.declarations[0].id.name;
    const types = node.right.elements.map((element) => element?.value);
    inner = new Map(loops).set(name, types);
  }
  visit(node, inner);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) for (const child of value) walk(child, visit, inner);
    else if (value && typeof value.type === "string") walk(value, visit, inner);
  }
}

const method = (node) =>
  node.type === "CallExpression" &&
  node.callee.type === "MemberExpression" &&
  !node.callee.computed
    ? node.callee.property.name
    : null;

// A string argument as the runtime would build it: a template's expressions become `_`,
// a name no selector, property or attribute is spelled with.
function text(node) {
  if (node?.type === "Literal" && typeof node.value === "string") return node.value;
  if (node?.type === "TemplateLiteral")
    return node.quasis.map((quasi) => quasi.value.cooked).join("_");
  return null;
}

// The `keydown` listeners: every `addEventListener` call whose event type is the
// literal "keydown", or the variable of an enclosing `for (… of [...])` whose array
// lists "keydown" (tests/*/test_interact_layer.py).
function keydown() {
  const found = [];
  for (const file of files)
    walk(tree(file), (node, loops) => {
      const listens =
        method(node) === "addEventListener" ||
        (node.type === "CallExpression" && node.callee.name === "addEventListener");
      if (!listens) return;
      const [type] = node.arguments;
      if (
        (type?.type === "Literal" && type.value === "keydown") ||
        (type?.type === "Identifier" && loops.get(type.name)?.includes("keydown"))
      )
        found.push(`${basename(file)}:${node.loc.start.line}`);
    });
  return found.join("\n");
}

// The names each module exports, and whether it has a default export. A re-export
// counts as the re-exporting module's own; `export *` names nothing.
function exports() {
  const read = {};
  const name = (node) => node.name ?? node.value;
  for (const file of files) {
    const names = new Set();
    let hasDefault = false;
    for (const statement of tree(file).body) {
      if (statement.type === "ExportDefaultDeclaration") hasDefault = true;
      if (statement.type === "ExportAllDeclaration" && statement.exported)
        names.add(name(statement.exported));
      if (statement.type !== "ExportNamedDeclaration") continue;
      for (const specifier of statement.specifiers) names.add(name(specifier.exported));
      const declaration = statement.declaration;
      if (declaration?.type === "VariableDeclaration")
        for (const { id } of declaration.declarations)
          if (id.type === "Identifier") names.add(id.name);
      if (declaration?.id) names.add(declaration.id.name);
    }
    if (names.delete("default")) hasDefault = true;
    read[file] = { names: [...names].sort(), default: hasDefault };
  }
  return JSON.stringify(read);
}

const QUERIES = new Set(["querySelector", "querySelectorAll", "closest", "matches"]);

// The selector each DOM query is handed as a literal or template.
function queries() {
  const read = {};
  for (const file of files) {
    const selectors = [];
    walk(tree(file), (node) => {
      if (!QUERIES.has(method(node))) return;
      const selector = text(node.arguments[0]);
      if (selector !== null) selectors.push(selector);
    });
    read[file] = selectors;
  }
  return JSON.stringify(read);
}

// Each module's string constants, top-level `const NAME = "…"` and the members of a
// top-level object literal (`NAME.key`, `Object.freeze` included), and the string
// first argument of each method call, by method name.
function literals() {
  const read = {};
  for (const file of files) {
    const constants = {};
    const calls = {};
    for (let statement of tree(file).body) {
      if (statement.type === "ExportNamedDeclaration")
        statement = statement.declaration;
      if (statement?.type !== "VariableDeclaration") continue;
      for (const { id, init } of statement.declarations) {
        if (id.type !== "Identifier") continue;
        const object =
          init?.type === "CallExpression" && method(init) === "freeze"
            ? init.arguments[0]
            : init;
        if (text(object) !== null) constants[id.name] = text(object);
        if (object?.type !== "ObjectExpression") continue;
        for (const property of object.properties)
          if (property.type === "Property" && !property.computed)
            if (text(property.value) !== null)
              constants[`${id.name}.${property.key.name ?? property.key.value}`] = text(
                property.value,
              );
      }
    }
    walk(tree(file), (node) => {
      const name = method(node);
      const argument = name && text(node.arguments[0]);
      if (argument !== null && argument !== undefined)
        (calls[name] ??= []).push(argument);
    });
    read[file] = { constants, calls };
  }
  return JSON.stringify(read);
}

const commands = { keydown, exports, queries, literals };
if (!commands[command])
  throw new Error(`usage: js_facts.mjs ${Object.keys(commands).join("|")} FILE...`);
process.stdout.write(commands[command]());
