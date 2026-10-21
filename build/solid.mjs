/** Leaf's one Solid runtime, shared by kernel views and build-free packages.
 *
 * Keeping the graph, renderer and tagged templates in one module makes every
 * reactive reading participate in the same ownership and scheduling system.
 */
import { parse } from "acorn";
import { adapt } from "./vendor.mjs";

export const solidPath = "vendor/solid.js";

/** Keep native focus, editing and iframe state when Solid reorders retained nodes. */
export function preserveSolidMoves(source) {
  const edits = [];
  const visit = (node) => {
    if (!node || typeof node !== "object") return;
    if (
      node.type === "CallExpression" &&
      node.callee.type === "MemberExpression" &&
      !node.callee.computed &&
      node.callee.property.name === "insertBefore"
    ) {
      const parent = source.slice(node.callee.object.start, node.callee.object.end);
      const args = node.arguments.map((argument) =>
        source.slice(argument.start, argument.end),
      );
      edits.push([node.start, node.end, `leafMove(${parent}, ${args.join(", ")})`]);
      return;
    }
    for (const value of Object.values(node))
      if (Array.isArray(value)) value.forEach(visit);
      else if (value?.type) visit(value);
  };
  visit(parse(source, { ecmaVersion: "latest", sourceType: "module" }));
  if (!edits.length)
    throw new Error("Solid renderer has no node insertions to preserve");
  for (const [start, end, replacement] of edits.sort((a, b) => b[0] - a[0]))
    source = source.slice(0, start) + replacement + source.slice(end);
  return 'import { move as leafMove } from "/runtime/dom-move.js";\n' + source;
}

export const solidMoves = () =>
  adapt([
    {
      file: /@solidjs[/\\]web[/\\]dist[/\\]web\.js$/,
      edit: preserveSolidMoves,
    },
  ]);

export const solidNamespace = () =>
  [
    'export { createSignal, createMemo, createRoot, createEffect, createTrackedEffect, createProjection, flush, untrack, For, Show, onCleanup } from "solid-js";',
    'export { render, insert, spread } from "@solidjs/web";',
    'export { default, default as solidHtml } from "@solidjs/html";',
  ].join("\n");

export function solidModule(root) {
  return {
    name: "leaf-solid",
    setup(build) {
      build.onResolve({ filter: /^leaf:solid$/ }, () => ({
        path: "solid",
        namespace: "leaf-solid",
      }));
      build.onLoad({ filter: /.*/, namespace: "leaf-solid" }, () => ({
        contents: solidNamespace(),
        resolveDir: root,
      }));
    },
  };
}
