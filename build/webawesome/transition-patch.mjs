/* Adapt the pinned library's open watchers to the shared transition owner.
 * Discover them from their watch('open') declarations, not component names.
 * Guard animation continuations and bind
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
  // A timed close must settle the consumer's feedback wait on completion OR
  // supersession. Keep the earlier user-close route, with one cleanup callback.
  walk(ast, (node) => {
    if (node.type !== "BlockStatement") return;
    for (let i = 0; i < node.body.length - 1; i++) {
      const first = node.body[i],
        next = node.body[i + 1];
      const promise = first.expression?.right;
      const executor = promise?.arguments?.[0];
      const listener = executor?.body?.body?.[0]?.expression;
      const timer = next.expression?.right;
      const timerBody = timer?.arguments?.[0]?.body;
      if (
        promise?.type !== "NewExpression" ||
        promise.callee.name !== "Promise" ||
        listener?.callee?.property?.name !== "addEventListener" ||
        listener.arguments[0]?.value !== "wa-after-hide" ||
        timer?.callee?.property?.name !== "setTimeout" ||
        !timerBody
      )
        continue;
      const hide = timerBody.body.find(
        (statement) =>
          statement.expression?.type === "AwaitExpression" &&
          statement.expression.argument.callee?.property?.name === "hide",
      );
      if (!hide) continue;
      const target = source.slice(
        listener.callee.object.start,
        listener.callee.object.end,
      );
      const hideTarget = hide.expression.argument.callee.object;
      if (source.slice(hideTarget.start, hideTarget.end) !== target) continue;
      const closed = listener.arguments[1].body;
      const timedClose =
        source.slice(next.start, hide.end) +
        "\nfinishClose();" +
        source.slice(hide.end, next.end);
      edits.push([
        executor.body.start + 1,
        next.end,
        `let finished = false;
        const finishClose = () => {
          if (finished) return;
          finished = true;
          ${target}.removeEventListener("wa-after-hide", finishClose);
          ${source.slice(closed.start + 1, closed.end - 1)}
        };
        ${target}.addEventListener("wa-after-hide", finishClose, {once:true});
        ${timedClose}
        });`,
      ]);
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
