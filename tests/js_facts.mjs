// What the suite's Python tests read out of JavaScript and TypeScript modules, from the
// parsed module rather than its text, so a statement wrapped across lines, quoted
// differently or commented out reads as the module means it. One command per reading:
//
//   node tests/js_facts.mjs keydown FILE...   `name:line` of every keydown listener
//   node tests/js_facts.mjs exports FILE...   {file: {names, default}} per module
//   node tests/js_facts.mjs imports FILE...   {file: {reads, stars}} names read elsewhere
//   node tests/js_facts.mjs queries FILE...   {file: [selector]} handed to DOM queries
//   node tests/js_facts.mjs literals FILE...  {file: {constants, calls}} literal values
//   node tests/js_facts.mjs presses FILE...   {file: [press]} each press and its dressing
//
// Every module is read with oxc, which parses JavaScript and TypeScript, the language
// chosen by the file's extension, into one ESTree, so a TypeScript module's exported
// types and interfaces are exports like its values.
import { existsSync, readFileSync, statSync } from "node:fs";
import { basename, dirname, join, relative } from "node:path";
import { parseSync } from "oxc-parser";
import { Tokenizer } from "parse5";
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
    for (const comment of comments)
      for (const [, specifier, name] of comment.value.matchAll(COMMENT_TYPE))
        take(specifier, name ?? "*");
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

// The calls that dress an element, and which argument holds the classes they give it.
const CLASS_ARGUMENT = {
  offer: 1,
  el: 1,
  offerElement: 1,
  offered: 0,
  offerAction: 1,
  offeredAction: 1,
  offerActionElement: 2,
  selectableOffer: 1,
  selectableOffered: 1,
  copyControl: 0,
};
// The builders that give an element a role's face (prepaint.js, `ACTION_FACES`), and
// the calls that make an element of the tag they are handed first.
const ROLE_BUILDERS = new Set(["offerAction", "offeredAction", "offerActionElement"]);
const MAKERS = new Set(["offer", "el", "createElement"]);

const callee = (node) =>
  node?.type !== "CallExpression"
    ? null
    : node.callee.type === "Identifier"
      ? node.callee.name
      : method(node);

// The names a binding pattern declares.
function declared(pattern) {
  switch (pattern?.type) {
    case "Identifier":
      return [pattern.name];
    case "ObjectPattern":
      return pattern.properties.flatMap((p) => declared(p.argument ?? p.value));
    case "ArrayPattern":
      return pattern.elements.flatMap(declared);
    case "RestElement":
      return declared(pattern.argument);
    case "AssignmentPattern":
      return declared(pattern.left);
    default:
      return [];
  }
}

// The node that declares `name` where `node` reads it, by the lexical scopes around
// `node`: a variable's declarator, or a function or class declaration. A parameter, an
// import, a destructured or loop binding, and a global declare nothing to follow.
function declaration(name, node, parents) {
  for (let at = parents.get(node); at; at = parents.get(at)) {
    if (/Function/.test(at.type) && at.params.some((p) => declared(p).includes(name)))
      return null;
    if (at.type === "CatchClause" && declared(at.param).includes(name)) return null;
    const head = at.type.startsWith("For") ? (at.init ?? at.left) : null;
    if (head?.declarations?.some((d) => declared(d.id).includes(name))) return null;
    const statements =
      at.type === "SwitchCase" ? at.consequent : Array.isArray(at.body) ? at.body : [];
    for (let statement of statements) {
      if (statement.type.startsWith("Export")) statement = statement.declaration;
      if (statement?.type === "ImportDeclaration")
        if (statement.specifiers.some((s) => s.local.name === name)) return null;
      if (/^(Function|Class)Declaration$/.test(statement?.type))
        if (statement.id?.name === name) return statement;
      for (const declarator of statement?.declarations ?? [])
        if (declared(declarator.id).includes(name))
          return declarator.id.type === "Identifier" ? declarator : null;
    }
  }
  return null;
}

// What a name read at `node` is bound to: a variable's initial value, a declared
// function or class, or, for `this.name`, the field or the assignment to it in the
// enclosing class.
function bound(node, parents) {
  if (node?.type === "Identifier") {
    const found = declaration(node.name, node, parents);
    return found?.type === "VariableDeclarator" ? found.init : found;
  }
  if (node?.type !== "MemberExpression" || node.object.type !== "ThisExpression")
    return null;
  const name = node.property.name;
  let body = parents.get(node);
  while (body && body.type !== "ClassBody") body = parents.get(body);
  if (!body) return null;
  const field = body.body.find(
    (member) => member.type === "PropertyDefinition" && member.key.name === name,
  );
  if (field?.value) return field.value;
  let assigned = null;
  walk(body, (n) => {
    if (
      n.type === "AssignmentExpression" &&
      n.left.type === "MemberExpression" &&
      n.left.object.type === "ThisExpression" &&
      n.left.property.name === name
    )
      assigned ??= n.right;
  });
  return assigned;
}

// The whole words an expression's string value can hold, through templates,
// conditions, concatenation, Lit's `classMap` and the constants it names. A word that
// touches a dynamic part or a join, as in `"lf-react" + "-icon"` or `lf-${kind}`, is
// unknown and left out.
function words(node, parents, seen = new Set()) {
  switch (node?.type) {
    case "Literal":
      return typeof node.value === "string" ? joined([node.value]) : [];
    case "TemplateLiteral":
      return joined(
        node.quasis.flatMap((quasi, i) => [
          quasi.value.cooked ?? quasi.value.raw,
          node.expressions[i],
        ]),
        parents,
        seen,
      );
    case "BinaryExpression": {
      const operands = (n) =>
        n.type === "BinaryExpression" && n.operator === "+"
          ? [...operands(n.left), ...operands(n.right)]
          : [n.type === "Literal" && typeof n.value === "string" ? n.value : n];
      return node.operator === "+" ? joined(operands(node), parents, seen) : [];
    }
    case "ConditionalExpression":
    case "LogicalExpression":
      return [node.consequent ?? node.left, node.alternate ?? node.right].flatMap((e) =>
        words(e, parents, seen),
      );
    case "CallExpression":
      // Lit's `classMap({name: on})` sets each name whose value isn't literally false.
      return callee(node) !== "classMap"
        ? []
        : (node.arguments[0]?.properties ?? [])
            .filter(
              (p) => !p.computed && !(p.value?.type === "Literal" && !p.value.value),
            )
            .flatMap((p) => joined([String(p.key.name ?? p.key.value)]));
    case "Identifier":
      if (seen.has(node)) return [];
      seen.add(node);
      return words(bound(node, parents), parents, seen);
    default:
      return [];
  }
}

// The whole words of text joined, in order, from static strings and the expressions
// between them. An expression counts only where whitespace or an end stands on both
// sides of it, and a string's edge word only where it ends the text or meets whitespace.
function joined(parts, parents, seen) {
  const run = parts.filter((part) => part !== undefined && part !== "");
  const open = (part, edge) =>
    part === undefined || (typeof part === "string" && edge.test(part));
  return run.flatMap((part, i) => {
    const [before, after] = [run[i - 1], run[i + 1]];
    if (typeof part !== "string")
      return open(before, /\s$/) && open(after, /^\s/)
        ? words(part, parents, seen)
        : [];
    const list = part.split(/\s+/);
    if (before !== undefined && !/^\s/.test(part)) list.shift();
    if (after !== undefined && !/\s$/.test(part)) list.pop();
    return list.filter(Boolean);
  });
}

const classNames = (values) => values.filter((name) => /^[\w-]+$/.test(name));

// Whether a role's builder dresses what `node` hands an element, and the classes the
// calls in it give the element, read from each call's class argument (`CLASS_ARGUMENT`).
// At `depth` above 0 the functions it calls are followed too, that many steps.
function dressing(node, parents, depth) {
  const found = { role: false, classes: [] };
  const calls = [];
  walk(node, (n) => {
    const name = callee(n);
    if (ROLE_BUILDERS.has(name)) found.role = true;
    if (Object.hasOwn(CLASS_ARGUMENT, name))
      found.classes.push(...words(n.arguments[CLASS_ARGUMENT[name]], parents));
    if (depth > 0 && n.callee?.type === "Identifier") calls.push(n.callee);
  });
  for (const name of calls) {
    const inner = dressing(bound(name, parents), parents, depth - 1);
    found.role ||= inner.role;
    found.classes.push(...inner.classes);
  }
  return found;
}

// Every press a module builds: `{line, site, kind, built, classes}`, where `built` says
// how a role's builder dresses it, or is null, and `classes` are the classes it is built
// with, read only where a class is given (`class`, a class argument, `className`).
//
// - "template": a `<button>`, or an element whose `role` is "button", in a template
//   literal or an HTML string, read with parse5's tokenizer so quoting holds, each
//   `${…}` standing in as a marker. A role dresses it from an expression in its
//   element part: "role in its tag" when a builder is called there, "role through a
//   name" when the part names a directive kept in a constant, or a callback handed to
//   `ref`, whose binding calls one, directly or through a function it calls.
// - "made": a "button" made by `offer`, `el` or `createElement`, with the `className`
//   later given to the variable it is bound to; "role as it is made" when it is made
//   as `offerActionElement`'s element.
// - "copy control": a `copyControl(…)`, "role in its options" when they name a role,
//   "trigger in its options" when they hand it a trigger, a press read on its own.
// - "scripted role": an element a module makes, bound in scope, and gives the role
//   "button" with `setAttribute`, `keeps` or `keepsAttribute`. An element the code was
//   handed, as a margin entry's host writer is, can't be followed and isn't read.
function presses() {
  const read = {};
  for (const file of files) {
    const source = readFileSync(file, "utf8");
    const program = tree(file);
    const parents = new Map();
    const assigned = [];
    walk(program, (node, _loops, parent) => {
      parents.set(node, parent);
      if (
        node.type === "AssignmentExpression" &&
        node.left.type === "MemberExpression" &&
        node.left.property.name === "className" &&
        node.left.object.type === "Identifier"
      )
        assigned.push(node);
    });
    const found = [];
    const press = (start, end, kind, built, values) =>
      found.push({
        line: source.slice(0, start).split("\n").length,
        site: source.slice(start, Math.min(end, start + 100)).replace(/\s+/g, " "),
        kind,
        built: built || null,
        classes: classNames(values),
      });
    // The classes given to the variable a made element is bound to, after it is made;
    // none where the element is bound to nothing this module declares.
    const givenLater = (binding) =>
      !binding
        ? []
        : assigned
            .filter((a) => declaration(a.left.object.name, a, parents) === binding)
            .flatMap((a) => words(a.right, parents));
    const bindingOf = (made) => {
      const parent = parents.get(made);
      if (parent?.type === "VariableDeclarator" && parent.init === made) return parent;
      if (parent?.type === "AssignmentExpression" && parent.left.type === "Identifier")
        return declaration(parent.left.name, parent, parents);
      return null;
    };
    walk(program, (node) => {
      if (
        node.type === "TemplateLiteral" ||
        (node.type === "Literal" && typeof node.value === "string")
      )
        templatePresses(node, parents, press);
      const name = callee(node);
      const args = node.arguments ?? [];
      if (MAKERS.has(name) && words(args[0], parents).includes("button")) {
        const parent = parents.get(node);
        const asMade =
          ROLE_BUILDERS.has(callee(parent)) && parent.arguments[0] === node;
        press(node.start, node.end, "made", asMade && "role as it is made", [
          ...words(args[CLASS_ARGUMENT[name]], parents),
          ...givenLater(bindingOf(node)),
        ]);
      }
      if (name === "copyControl" && node.callee.type === "Identifier") {
        const option = (name) =>
          args[1]?.properties?.find((p) => p.key?.name === name);
        const role = option("role") && words(option("role").value, parents).length;
        press(
          node.start,
          node.end,
          "copy control",
          role ? "role in its options" : option("trigger") && "trigger in its options",
          [...words(args[0], parents)],
        );
      }
      const receiver =
        name === "setAttribute" &&
        text(args[0]) === "role" &&
        text(args[1]) === "button"
          ? node.callee.object
          : ["keeps", "keepsAttribute"].includes(name) &&
              text(args[1]) === "role" &&
              text(args[2]) === "button"
            ? args[0]
            : null;
      const binding =
        receiver?.type === "Identifier"
          ? declaration(receiver.name, receiver, parents)
          : null;
      const made = binding?.init;
      if (MAKERS.has(callee(made)))
        press(node.start, node.end, "scripted role", null, [
          ...words(made.arguments[CLASS_ARGUMENT[callee(made)]], parents),
          ...givenLater(binding),
        ]);
    });
    read[file] = found;
  }
  return JSON.stringify(read);
}

// The presses a template literal or an HTML string holds (`presses`, "template").
function templatePresses(node, parents, press) {
  const expressions = node.expressions ?? [];
  // Where each run of the markup starts in the markup and in the module's source. The
  // markup is the text Lit receives, escapes cooked, so an escape before a tag in its
  // run moves the tag's site by the characters the escape saves.
  const runs = [];
  let markup = "";
  if (node.type === "Literal") {
    runs.push([0, node.start + 1]);
    markup = node.value;
  } else
    node.quasis.forEach((quasi, i) => {
      runs.push([markup.length, quasi.start]);
      markup +=
        (quasi.value.cooked ?? quasi.value.raw) +
        (i < expressions.length ? `lfexpr${i}z` : "");
    });
  if (!/<[a-z]/i.test(markup)) return;
  const inSource = (offset) => {
    const [start, from] = runs.findLast(([at]) => at <= offset);
    return from + offset - start;
  };
  const marked = (value) =>
    [...value.matchAll(/lfexpr(\d+)z/g)].map((match) => expressions[match[1]]);
  // The whole words of an attribute's value, its text joined with the expressions its
  // markers stand for.
  const valueWords = (value) =>
    joined(
      value.split(/(lfexpr\d+z)/).map((piece, i) => (i % 2 ? marked(piece)[0] : piece)),
      parents,
      new Set(),
    );
  const onStartTag = ({ tagName, attrs, location }) => {
    const role = attrs.find((attr) => attr.name === "role");
    const asButton = valueWords(role?.value ?? "").includes("button");
    if (tagName !== "button" && !asButton) return;
    const classes = valueWords(
      attrs.find((attr) => attr.name === "class")?.value ?? "",
    );
    // The element part: an expression standing in the tag as an attribute name.
    const parts = attrs.flatMap((attr) => marked(attr.name));
    const handed = parts.flatMap((part) => {
      const names = [];
      walk(part, (n) => {
        if (callee(n) === "ref") names.push(n.arguments[0]);
      });
      return [part, ...names].filter((n) => bound(n, parents));
    });
    const direct = parts.map((part) => dressing(part, parents, 0));
    const named = handed.map((name) => dressing(bound(name, parents), parents, 1));
    press(
      inSource(location.startOffset),
      inSource(location.endOffset - 1) + 1,
      "template",
      direct.some((d) => d.role)
        ? "role in its tag"
        : named.some((d) => d.role) && "role through a name",
      [...classes, ...[...direct, ...named].flatMap((d) => d.classes)],
    );
  };
  // The tokenizer calls a handler for every kind of token; only start tags matter.
  const handler = new Proxy(
    { onStartTag },
    { get: (own, name) => own[name] ?? (() => {}) },
  );
  new Tokenizer({ sourceCodeLocationInfo: true }, handler).write(markup, true);
}

const commands = { keydown, exports, imports, queries, literals, presses };
if (!commands[command])
  throw new Error(`usage: js_facts.mjs ${Object.keys(commands).join("|")} FILE...`);
process.stdout.write(commands[command]());
