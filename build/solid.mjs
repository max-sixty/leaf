/** Leaf's one Solid runtime, shared by kernel views and build-free packages.
 *
 * Keeping the graph, renderer and tagged templates in one module makes every
 * reactive reading participate in the same ownership and scheduling system.
 */
import { parse } from "acorn";
import { adapt, seam } from "./vendor.mjs";

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

/** Retained custom elements may leave and return without ending their view.
 * Solid's event registry must enumerate containers for newly delegated event
 * types, but must not keep a detached container (and its entire graph) alive.
 * Weak state and weak enumeration preserve synchronous event registration.
 */
export function weakSolidContainers(source) {
  source = seam(
    source,
    "const delegatedContainers = new Map();",
    `
const delegatedContainers = new WeakMap();
const delegatedContainerRefs = new Set();
const finalizedContainers = new FinalizationRegistry(ref => delegatedContainerRefs.delete(ref));
function* liveDelegatedContainers() {
  for (const ref of delegatedContainerRefs) {
    const container = ref.deref();
    if (!container) { delegatedContainerRefs.delete(ref); continue; }
    const state = delegatedContainers.get(container);
    if (state) yield [container, state];
  }
}`,
    "Solid delegated container retention",
  );
  source = seam(
    source,
    "delegatedContainers.forEach((state, container) => attachDelegatedEvent(name, container, state));",
    "for (const [container, state] of liveDelegatedContainers()) attachDelegatedEvent(name, container, state);",
    "Solid delegated container enumeration",
  );
  source = seam(
    source,
    "for (const [container, state] of delegatedContainers)",
    "for (const [container, state] of liveDelegatedContainers())",
    "Solid hydration container enumeration",
  );
  source = seam(
    source,
    "if (!state) delegatedContainers.set(container, state = {",
    `if (!state) {
    const ref = new WeakRef(container);
    delegatedContainerRefs.add(ref);
    finalizedContainers.register(container, ref, ref);
    delegatedContainers.set(container, state = { ref,`,
    "Solid weak event registration",
  );
  source = seam(
    source,
    "handlers: new Map()\n  });",
    "handlers: new Map()\n  });\n  }",
    "Solid weak registration state",
  );
  source = seam(
    source,
    "delegatedContainers.delete(container);",
    "finalizedContainers.unregister(state.ref); delegatedContainerRefs.delete(state.ref); delegatedContainers.delete(container);",
    "Solid event retirement",
  );
  return source;
}

/** State-bearing form props also read native state: input changes precede a paint,
 * and one spread may rerun for another prop on the same control. Avoid rewriting a
 * value/checked state that the user or an earlier binding has already installed.
 */
export function quietSolidForms(source) {
  source = seam(
    source,
    'else node[prop] = value ?? "";',
    'else if (node[prop] !== String(value ?? "")) node[prop] = value ?? "";',
    "Solid native field value",
  );
  source = seam(
    source,
    "} else node[prop] = value;\n    reclaimAttribute",
    "} else if (node[prop] !== value) node[prop] = value;\n    reclaimAttribute",
    "Solid native control state",
  );
  source = seam(
    source,
    "else p.value = v, p.selectedIndex",
    "else (p.value != v && (p.value = v)), p.selectedIndex",
    "Solid select value",
  );
  return source;
}

/** Import templates into the live custom-element registry before refs run. Keep
 * each traversal local and snapshot its original nodes: a shared walker both retains the last detached tree and
 * lets a template mounted by a ref overwrite its enclosing traversal's cursor.
 * Refs may also mount children, which must not enter the enclosing static walk.
 */
export function solidTemplates(source) {
  source = seam(
    source,
    "node.template.content.firstChild.cloneNode(true)",
    "document.importNode(node.template.content.firstChild, true)",
    "Solid custom element upgrade before refs",
  );
  source = seam(
    source,
    "const walker = document.createTreeWalker(document, 129);",
    `
  const templateCursor = root => {
    const walker = document.createTreeWalker(root, 129);
    const nodes = [];
    for (let node; node = walker.nextNode();) nodes.push(node);
    return nodes[Symbol.iterator]();
  };`,
    "Solid template cursor lifetime",
  );
  source = seam(
    source,
    "walker.currentNode = element;",
    "const walker = templateCursor(element);",
    "Solid reentrant template traversal",
  );
  source = seam(
    source,
    "const domNode = walker.nextNode();",
    "const domNode = walker.next().value;",
    "Solid template traversal snapshot",
  );
  source = seam(
    source,
    "walker.currentNode = domNode;",
    "",
    "Solid inserted subtree traversal",
  );
  source = seam(
    source,
    "document.createTreeWalker(domNode.content, 129)",
    "templateCursor(domNode.content)",
    "Solid nested template traversal",
  );
  return seam(
    source,
    "document.createTreeWalker(element.content, 129)",
    "templateCursor(element.content)",
    "Solid template content traversal",
  );
}

export const solidMoves = () =>
  adapt([
    {
      file: /@solidjs[/\\]web[/\\]dist[/\\]web\.js$/,
      edit: (source) =>
        quietSolidForms(weakSolidContainers(preserveSolidMoves(source))),
    },
    {
      file: /@solidjs[/\\]html[/\\]dist[/\\]html\.js$/,
      edit: solidTemplates,
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
