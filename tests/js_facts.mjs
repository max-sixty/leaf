// What the suite's Python tests read out of JavaScript and TypeScript modules, from the
// parsed module rather than its text, so a statement wrapped across lines, quoted
// differently or commented out reads as the module means it. One command per reading:
//
//   node tests/js_facts.mjs keydown FILE...   `name:line` of every keydown listener
//   node tests/js_facts.mjs exports FILE...   {file: {names, default}} per module
//   node tests/js_facts.mjs imports FILE...   {file: {reads, stars}} names read elsewhere
//   node tests/js_facts.mjs queries FILE...   {file: [selector]} handed to DOM queries
//   node tests/js_facts.mjs literals FILE...  {file: {constants, calls}} literal values
//
// Every module is read with oxc, which parses JavaScript and TypeScript, the language
// chosen by the file's extension, into one ESTree, so a TypeScript module's exported
// types and interfaces are exports like its values.
import { existsSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";
import { parseSync } from "oxc-parser";
import { served } from "./served-paths.mjs";

const [command, ...files] = process.argv.slice(2);

function parse(file) {
  const parsed = parseSync(file, readFileSync(file, "utf8"), { sourceType: "module" });
  if (parsed.errors.length) throw new Error(`${file}: ${parsed.errors[0].message}`);
  return parsed;
}

const tree = (file) => parse(file).program;

// The 1-based line a node starts on; oxc gives offsets only.
const line = (file, node) =>
  readFileSync(file, "utf8").slice(0, node.start).split("\n").length;

// Every node below `node`, each with the `for (… of [...])` loop variables in scope and
// its parent.
function walk(node, visit, loops = new Map(), parent = null) {
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
  visit(node, inner, parent);
  for (const value of Object.values(node)) {
    if (Array.isArray(value))
      for (const child of value) walk(child, visit, inner, node);
    else if (value && typeof value.type === "string") walk(value, visit, inner, node);
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
        found.push(`${basename(file)}:${line(file, node)}`);
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
      if (declaration?.id) names.add(name(declaration.id));
    }
    if (names.delete("default")) hasDefault = true;
    read[file] = { names: [...names].sort(), default: hasDefault };
  }
  return JSON.stringify(read);
}

// The file a module specifier in `file` names, relative to the working directory, or
// null for a package, a builtin, or a path that holds no file. A relative specifier may
// leave out its extension or name a TypeScript module by its `.js` output, as
// TypeScript resolves it; a root-absolute one is the file a served page answers with
// (`served-paths.mjs`), or one of the render gate's probes under `/checks/`.
function resolve(file, specifier) {
  const path = specifier.startsWith(".")
    ? join(dirname(file), specifier)
    : specifier.startsWith("/checks/")
      ? join("src/leaf/render-checks", specifier.slice("/checks/".length))
      : served(specifier);
  if (!path) return null;
  const found = [
    path,
    path.replace(/\.js$/, ".ts"),
    path.replace(/\.js$/, ".d.ts"),
    `${path}.ts`,
    `${path}.js`,
    join(path, "index.ts"),
    join(path, "index.js"),
  ].find((candidate) => existsSync(candidate) && statSync(candidate).isFile());
  return found ? relative(".", found) : null;
}

// The string a specifier spells, or null where it is computed.
const spelled = (node) =>
  node?.type === "TemplateLiteral" && node.expressions.length === 0
    ? node.quasis[0].value.cooked
    : node?.type === "Literal" && typeof node.value === "string"
      ? node.value
      : null;

// A JSDoc type names an export as `import("…").Name`, or a whole module without a name.
const COMMENT_TYPE = /import\(\s*["'`]([^"'`]+)["'`]\s*\)(?:\.([A-Za-z_$][\w$]*))?/g;
// A JSDoc `@import` tag names exports as an import declaration does: by a braced list,
// whose lines may carry the comment's leading `*`, a namespace, or a default.
const COMMENT_IMPORT =
  /@import\s+(?:\{([^}]*)\}|(\*)\s+as\s+[\w$]+|[\w$]+)\s+from\s+["'`]([^"'`]+)["'`]/g;

// Whether an identifier reads a binding, rather than declaring one, naming a property,
// key or type member, or labelling a statement.
function refers(node, parent) {
  switch (parent.type) {
    case "MemberExpression":
      return parent.object === node || parent.computed;
    case "Property":
    case "PropertyDefinition":
    case "MethodDefinition":
    case "TSPropertySignature":
    case "TSMethodSignature":
      return parent.value === node || parent.computed;
    case "TSQualifiedName":
      return parent.left === node;
    case "VariableDeclarator":
      return parent.init === node;
    case "FunctionDeclaration":
    case "FunctionExpression":
    case "ArrowFunctionExpression":
      return parent.body === node;
    case "AssignmentPattern":
      return parent.right === node;
    case "ExportSpecifier":
      return parent.local === node;
    case "ImportSpecifier":
    case "ImportDefaultSpecifier":
    case "ImportNamespaceSpecifier":
    case "ClassDeclaration":
    case "ClassExpression":
    case "CatchClause":
    case "LabeledStatement":
    case "BreakStatement":
    case "ContinueStatement":
      return false;
    default:
      return true;
  }
}

// Which exports of other modules each module reads, as `[file, name]` pairs, where name
// is an export's name, `default`, or `*` for a use that may read any of them; and the
// modules it re-exports whole (`export * from`), whose names it offers as its own.
//
// A name is read by an import or a re-export naming it, by a TypeScript or JSDoc type
// `import("…").Name`, and through a module namespace, whether `import * as` binds it or
// a dynamic `import()` resolves to it: a member read names the export, destructuring
// names each export it takes, a binding passes the namespace on to its own readers, and
// any other use reads it whole. A binding is followed by its name across the module, so
// a name it shares with another binding there can only read more. A specifier
// `resolve` places nowhere reads nothing. An `import()` of a computed specifier may
// load any module, so each name taken from it is a `[null, name]` pair, which reads
// that name wherever it is exported; taking it whole or its default reads nothing.
function imports() {
  const read = {};
  for (const file of files) {
    const { program, comments } = parse(file);
    const parents = new Map();
    const references = new Map();
    const dynamic = [];
    const types = [];
    walk(program, (node, _loops, parent) => {
      parents.set(node, parent);
      if (node.type === "Identifier" && parent && refers(node, parent)) {
        if (!references.has(node.name)) references.set(node.name, []);
        references.get(node.name).push(node);
      }
      if (node.type === "ImportExpression") dynamic.push(node);
      if (node.type === "TSImportType") types.push(node);
    });

    const found = [];
    const take = (specifier, name) => {
      if (specifier === null) {
        if (name !== "*" && name !== "default") found.push([null, name]);
        return;
      }
      const target = resolve(file, specifier);
      if (target) found.push([target, name]);
    };
    const bound = new Set();
    // A namespace bound to `target`, a declared name or a destructuring pattern.
    const bind = (specifier, target) => {
      if (target?.type === "ObjectPattern")
        for (const property of target.properties)
          take(
            specifier,
            property.type === "Property" && !property.computed
              ? (property.key.name ?? property.key.value)
              : "*",
          );
      else if (target?.type === "Identifier") {
        if (bound.has(`${specifier}\0${target.name}`)) return;
        bound.add(`${specifier}\0${target.name}`);
        for (const reference of references.get(target.name) ?? [])
          use(specifier, reference);
      } else if (target) take(specifier, "*");
    };
    // What the expression `node`, which evaluates to a namespace, takes from it. An
    // expression a namespace passes through whole, such as `await` or one branch of a
    // conditional, is what the namespace is read from; a statement or a condition that
    // only tests it reads nothing.
    const use = (specifier, node) => {
      let parent = parents.get(node);
      while (
        ["ParenthesizedExpression", "AwaitExpression", "LogicalExpression"].includes(
          parent.type,
        ) ||
        (parent.type === "ConditionalExpression" && parent.test !== node)
      ) {
        node = parent;
        parent = parents.get(node);
      }
      if (parent.type === "ExpressionStatement" || parent.test === node) return;
      if (parent.type === "UnaryExpression" && parent.operator === "!") return;
      if (parent.type === "MemberExpression" && parent.object === node) {
        const name = parent.computed ? spelled(parent.property) : parent.property.name;
        const call = parents.get(parent);
        const [handler] = call.callee === parent ? call.arguments : [];
        if (name === "then" && handler?.params)
          return bind(specifier, handler.params[0]);
        return take(specifier, name ?? "*");
      }
      if (parent.type === "TSQualifiedName") return take(specifier, parent.right.name);
      if (parent.type === "VariableDeclarator") return bind(specifier, parent.id);
      if (parent.type === "AssignmentExpression" && parent.right === node)
        return bind(specifier, parent.left);
      take(specifier, "*");
    };

    const stars = [];
    for (const statement of program.body) {
      const source = statement.source?.value;
      if (statement.type === "ImportDeclaration")
        for (const specifier of statement.specifiers)
          if (specifier.type === "ImportNamespaceSpecifier")
            bind(source, specifier.local);
          else if (specifier.type === "ImportDefaultSpecifier") take(source, "default");
          else take(source, specifier.imported.name ?? specifier.imported.value);
      if (statement.type === "ExportNamedDeclaration" && source)
        for (const specifier of statement.specifiers)
          take(source, specifier.local.name ?? specifier.local.value);
      if (statement.type !== "ExportAllDeclaration") continue;
      const target = resolve(file, source);
      if (statement.exported) take(source, "*");
      else if (target) stars.push(target);
    }
    for (const node of dynamic) {
      // Rejection and cleanup handlers keep the fulfilled namespace. Follow the
      // promise before reading its value; these methods aren't module exports.
      let promise = node;
      while (true) {
        const member = parents.get(promise);
        const call = parents.get(member);
        if (
          member?.object !== promise ||
          call?.callee !== member ||
          !["catch", "finally"].includes(method(call))
        )
          break;
        promise = call;
      }
      use(spelled(node.source), promise);
    }
    for (const { source, qualifier } of types) {
      let name = qualifier;
      while (name?.type === "TSQualifiedName") name = name.left;
      take(spelled(source), name?.name ?? "*");
    }
    for (const comment of comments) {
      for (const [, specifier, name] of comment.value.matchAll(COMMENT_TYPE))
        take(specifier, name ?? "*");
      for (const [, names, star, specifier] of comment.value.matchAll(COMMENT_IMPORT)) {
        if (names === undefined) take(specifier, star ? "*" : "default");
        else
          for (const entry of names.replaceAll("*", " ").split(",")) {
            const name = entry.trim().split(/\s+as\s+/)[0];
            if (name) take(specifier, name);
          }
      }
    }
    read[file] = { reads: found, stars };
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
// top-level object literal (`NAME.key`, `Object.freeze` included), and the arguments
// of each method call whose first is a string, by method name: each argument's
// literal value, or null where it is not a literal.
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
    const value = (node) => text(node) ?? (node.type === "Literal" ? node.value : null);
    walk(tree(file), (node) => {
      const name = method(node);
      if (name && text(node.arguments[0]) !== null)
        (calls[name] ??= []).push(node.arguments.map(value));
    });
    read[file] = { constants, calls };
  }
  return JSON.stringify(read);
}

const commands = { keydown, exports, imports, queries, literals };
if (!commands[command])
  throw new Error(`usage: js_facts.mjs ${Object.keys(commands).join("|")} FILE...`);
process.stdout.write(commands[command]());
