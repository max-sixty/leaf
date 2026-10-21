/** Leaf's one Solid runtime, shared by kernel views and build-free packages.
 *
 * Keeping the graph, renderer and tagged templates in one module makes every
 * reactive reading participate in the same ownership and scheduling system.
 */
export const solidPath = "vendor/solid.js";

export const solidNamespace = () =>
  [
    'export { createSignal, createMemo, createRoot, createEffect, createTrackedEffect, flush, untrack, For, Show, onCleanup } from "solid-js";',
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
