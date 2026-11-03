// What the suite's Python tests read out of JavaScript and TypeScript modules, from the
// parsed module rather than its text, so a statement wrapped across lines, quoted
// differently or commented out reads as the module means it. One command per reading:
//
//   node tests/js_facts.mjs keydown FILE...   `name:line` of every keydown listener
//   node tests/js_facts.mjs exports FILE...   {file: {names, default}} per module
//   node tests/js_facts.mjs queries FILE...   {file: [selector]} handed to DOM queries
//   node tests/js_facts.mjs literals FILE...  {file: {constants, calls}} literal values
//   node tests/js_facts.mjs presses FILE...   {file: [press]} each press and its dressing
//
// Every module is read with oxc, which parses JavaScript and TypeScript, the language
// chosen by the file's extension, into one ESTree, so a TypeScript module's exported
// types and interfaces are exports like its values.
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parseSync } from "oxc-parser";
import { Tokenizer } from "parse5";

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

// The builders that give an element a role's face (control-faces.js, `ACTION_FACES`), and
// the calls that make an element of the tag they are handed first.
// `roleElement` is element-markers.js's own writer behind them, and `actionClass` the
// role's face a pure template writes into its `class` (control-faces.js).
const ROLE_BUILDERS = new Set([
  "offerAction",
  "offeredAction",
  "offerActionElement",
  "offerContentElement",
  "roleElement",
  "actionClass",
]);
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
// conditions, concatenation and the constants it names. A word that touches a dynamic
// part or a join, as in `"lf-react" + "-icon"` or `lf-${kind}`, is unknown and left
// out.
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

// Whether a role's builder dresses what `node` hands an element. At `depth` above 0
// the functions it calls are followed too, that many steps.
function dressing(node, parents, depth) {
  let role = false;
  const calls = [];
  walk(node, (n) => {
    if (ROLE_BUILDERS.has(callee(n))) role = true;
    if (depth > 0 && n.callee?.type === "Identifier") calls.push(n.callee);
  });
  return (
    role || calls.some((name) => dressing(bound(name, parents), parents, depth - 1))
  );
}

// Every press a module builds: `{line, site, kind, built}`, where `built` says how a
// role's builder dresses it, or is null.
//
// - "template": a `<button>`, or an element whose `role` is "button", in a template
//   literal or an HTML string, read with parse5's tokenizer so quoting holds, each
//   `${…}` standing in as a marker, or whose element part makes it a selectable
//   button (`selectableOffered("button", …)`). A role dresses it from an expression in
//   its element part: "role in its tag" when a builder is called there, or the
//   selectable offer names its face, "role through a name" when the part names a
//   directive kept in a constant, or a callback handed to `ref`, whose binding calls
//   one, directly or through a function it calls.
// - "made": a "button" made by `offer`, `el` or `createElement`; "role as it is made"
//   when it is made as the element of `offerActionElement` or `offerContentElement`,
//   or the variable that holds it, and only it, is later handed to one.
// - "selectable": a selectable button, `selectableOffer("button", …)`; "role as it is
//   made" when it names its face (the fourth argument). A selectable offer of another
//   role, such as a tab, chooses rather than presses, as a native choice does, and is
//   no press.
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
    const dressed = [];
    const rebinding = [];
    walk(program, (node, _loops, parent) => {
      parents.set(node, parent);
      if (ROLE_BUILDERS.has(callee(node)) && node.arguments[0]?.type === "Identifier")
        dressed.push(node);
      if (node.type === "AssignmentExpression" && node.left.type === "Identifier")
        rebinding.push(node);
    });
    // A binding holds one element only when it is never given another: a `const`, or
    // a `let` or `var` no assignment names. Dressing through any other could dress an
    // element the name held before or after the one being read.
    const holdsOne = (binding) =>
      parents.get(binding)?.kind === "const" ||
      !rebinding.some((a) => declaration(a.left.name, a, parents) === binding);
    const found = [];
    const press = (start, end, kind, built) =>
      found.push({
        line: source.slice(0, start).split("\n").length,
        site: source.slice(start, Math.min(end, start + 100)).replace(/\s+/g, " "),
        kind,
        built: built || null,
      });
    // The role builders' calls handed the variable a made element is bound to.
    const dressedLater = (binding) =>
      !binding || !holdsOne(binding)
        ? []
        : dressed.filter(
            (call) => declaration(call.arguments[0].name, call, parents) === binding,
          );
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
        const binding = bindingOf(node);
        const later = dressedLater(binding);
        const asMade =
          (ROLE_BUILDERS.has(callee(parent)) && parent.arguments[0] === node) ||
          later.length > 0;
        press(node.start, node.end, "made", asMade && "role as it is made");
      }
      if (name === "selectableOffer" && words(args[0], parents).includes("button"))
        press(
          node.start,
          node.end,
          "selectable",
          words(args[3], parents).length > 0 && "role as it is made",
        );
      if (name === "copyControl" && node.callee.type === "Identifier") {
        const option = (name) => args[1]?.properties?.find((p) => p.key?.name === name);
        const role = option("role") && words(option("role").value, parents).length;
        press(
          node.start,
          node.end,
          "copy control",
          role ? "role in its options" : option("trigger") && "trigger in its options",
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
      if (MAKERS.has(callee(made))) press(node.start, node.end, "scripted role", null);
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
    // The element part: an expression standing in the tag as an attribute name.
    const parts = attrs.flatMap((attr) => marked(attr.name));
    // A selectable offer gives the element its role, and its face (the third argument).
    const selectable = parts.filter(
      (part) =>
        callee(part) === "selectableOffered" &&
        words(part.arguments[0], parents).includes("button"),
    );
    const asButton = valueWords(role?.value ?? "").includes("button");
    if (tagName !== "button" && !asButton && !selectable.length) return;
    const classValue = attrs.find((attr) => attr.name === "class")?.value ?? "";
    // A pure template writes a role's face into its class (`actionClass`).
    const facedClass = marked(classValue).some((part) => dressing(part, parents, 0));
    const facedOffer = selectable.some(
      (part) => words(part.arguments[2], parents).length > 0,
    );
    const handed = parts.flatMap((part) => {
      const names = [];
      walk(part, (n) => {
        if (callee(n) === "ref") names.push(n.arguments[0]);
      });
      return [part, ...names].filter((n) => bound(n, parents));
    });
    press(
      inSource(location.startOffset),
      inSource(location.endOffset - 1) + 1,
      "template",
      parts.some((part) => dressing(part, parents, 0)) || facedClass || facedOffer
        ? "role in its tag"
        : handed.some((name) => dressing(bound(name, parents), parents, 1)) &&
            "role through a name",
    );
  };
  // The tokenizer calls a handler for every kind of token; only start tags matter.
  const handler = new Proxy(
    { onStartTag },
    { get: (own, name) => own[name] ?? (() => {}) },
  );
  new Tokenizer({ sourceCodeLocationInfo: true }, handler).write(markup, true);
}

const commands = { keydown, exports, queries, literals, presses };
if (!commands[command])
  throw new Error(`usage: js_facts.mjs ${Object.keys(commands).join("|")} FILE...`);
process.stdout.write(commands[command]());
