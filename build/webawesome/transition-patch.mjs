/* Adapt the pinned library's open watchers to the shared transition owner.
 * Discover them from their watch('open') declarations, not component names.
 * Guard every continuation, including pre-animation updateComplete, and bind
 * public show/hide promises to that same owner instead of obsolete after-events.
 * Other animation callers honor the primitive's superseded result too. */
import { parse } from "acorn";

function walk(node, visit) {
  if (!node || typeof node !== "object") return;
  if (node.type) visit(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach((child) => walk(child, visit));
    else if (value && typeof value === "object") walk(value, visit);
  }
}

export function patchTransitions(source) {
  if (!source.includes("animateWithClass")) return source;
  const ast = parse(source, { ecmaVersion: "latest", sourceType: "module" });
  const handlers = new Set();
  walk(ast, (node) => {
    if (node.type !== "CallExpression" || node.callee.name !== "__decorateClass")
      return;
    const [decorators, , key] = node.arguments;
    if (
      decorators.type === "ArrayExpression" &&
      decorators.elements.some(
        (decorator) =>
          decorator?.callee?.name === "watch" &&
          decorator.arguments[0]?.value === "open",
      )
    )
      handlers.add(key.value);
  });
  const owned = [];
  let handler;
  walk(ast, (node) => {
    if (node.type !== "MethodDefinition" || !handlers.has(node.key.name)) return;
    let animated = false;
    walk(node.value.body, (child) => {
      if (child.callee?.name === "animateWithClass") animated = true;
    });
    if (animated) {
      owned.push(node.value.body);
      handler = node.key.name;
    }
  });
  const inside = (node) =>
    owned.some((body) => node.start > body.start && node.end < body.end);
  const edits = [];
  for (const body of owned) {
    edits.push([
      body.start + 1,
      body.start + 1,
      "\nreturn runTransition(this, async transition => {",
    ]);
    edits.push([body.end - 1, body.end - 1, "\n});\n"]);
  }
  walk(ast, (node) => {
    if (node.type === "FunctionDeclaration" && node.id.name === "animateWithClass") {
      edits.push([
        node.start,
        node.end,
        'import { animateWithClass } from "leaf-wa-transitions";',
      ]);
    }
    if (
      node.type === "ExpressionStatement" &&
      node.expression.type === "AwaitExpression"
    ) {
      const call = node.expression.argument;
      if (call.callee?.name === "animateWithClass") {
        const args = call.arguments.map((argument) =>
          source.slice(argument.start, argument.end),
        );
        if (inside(node)) args.push("transition");
        edits.push([
          node.start,
          node.end,
          `if (!(await animateWithClass(${args.join(", ")}))) return;`,
        ]);
      } else if (inside(node)) {
        edits.push([node.end, node.end, "\nif (!transition.current) return;"]);
      }
    }
    if (
      owned.length &&
      node.type === "ReturnStatement" &&
      node.argument?.callee?.name === "waitForEvent"
    ) {
      const event = node.argument.arguments[1]?.value;
      if (event === "wa-after-show" || event === "wa-after-hide") {
        edits.push([
          node.start,
          node.end,
          `return waitForTransition(this, () => this.${handler}());`,
        ]);
      }
    }
  });
  if (!edits.length) return source;
  edits.sort((a, b) => b[0] - a[0]);
  for (const [start, end, replacement] of edits)
    source = source.slice(0, start) + replacement + source.slice(end);
  if (owned.length)
    source =
      'import { runTransition, waitForTransition } from "leaf-wa-transitions";\n' +
      source;
  return source;
}
