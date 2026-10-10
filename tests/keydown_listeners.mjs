// The `keydown` listeners in the files named on the command line, as `name:line`, one
// per line: every `addEventListener` call whose event type is the literal "keydown", or
// the variable of an enclosing `for (… of [...])` whose array lists "keydown". Read from
// the parsed module, so a call wrapped across lines, or registered for several types in
// one loop, counts as written (tests/test_interact_layer.py).
import { readFileSync } from "node:fs";
import { basename } from "node:path";
import { parse } from "acorn";

const found = [];
for (const file of process.argv.slice(2)) {
  const ast = parse(readFileSync(file, "utf8"), {
    ecmaVersion: "latest",
    sourceType: "module",
    locations: true,
  });
  const visit = (node, loops) => {
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
    if (
      node.type === "CallExpression" && node.callee.type === "MemberExpression"
        ? node.callee.property.name === "addEventListener"
        : node.type === "CallExpression" && node.callee.name === "addEventListener"
    ) {
      const [type] = node.arguments;
      const keydown =
        (type?.type === "Literal" && type.value === "keydown") ||
        (type?.type === "Identifier" && inner.get(type.name)?.includes("keydown"));
      if (keydown) found.push(`${basename(file)}:${node.loc.start.line}`);
    }
    for (const value of Object.values(node)) {
      if (Array.isArray(value)) for (const child of value) visit(child, inner);
      else if (value && typeof value.type === "string") visit(value, inner);
    }
  };
  visit(ast, new Map());
}
process.stdout.write(found.join("\n"));
