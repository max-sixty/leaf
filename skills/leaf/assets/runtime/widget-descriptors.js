/* Revision-bound widget identity captured before a content module upgrades the DOM.

   A controller receives no caller-supplied declaration or scope. Leaf records the
   authored owner, its declared ancestors, and exhibit fence while the revision's
   markup is still intact. Later physical reparenting is layout;
   semantic commands keep using this captured document coordinate. A data renderer may
   replace a widget node while preserving its authored id; that replacement reuses the
   same revision-bound descriptor.

   The binding also answers the other way, id to element, for the layer's own paint:
   a message's frozen markup is bound when it is prepared, before the thread mounts
   it, so what the projection paints on it arrives with the node. */
import { runtime } from "./context.js";
import { authoredParents } from "./projection/authored.js";
import { elementById } from "./passages.js";

const byElement = new WeakMap();
const byId = new Map();
const elements = new Map();

const declaredTags = () =>
  Object.keys(runtime.registry).filter((tag) => !tag.startsWith("$"));

const candidates = (root) => {
  const tags = declaredTags();
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root.nodeType === Node.ELEMENT_NODE && root.matches(selector))
    found.unshift(root);
  return found;
};

const parentOf = (element) => authoredParents.get(element) ?? element.parentElement;

const declaredAncestors = (element) => {
  const ancestors = [];
  for (let parent = parentOf(element); parent; parent = parentOf(parent))
    if (parent.id && runtime.registry[parent.localName])
      ancestors.push({ id: parent.id, tag: parent.localName });
  return ancestors;
};

const quotedBy = (element) => {
  for (let node = element; node; node = parentOf(node))
    if (runtime.registry[node.localName]?.["x-exhibit"]) return true;
  return false;
};

export function stageWidgetDescriptors(
  root = document,
  documentContext = { kind: "page", revision: runtime.currentRevision },
) {
  const captured = new Map();
  const bindings = [];
  for (const element of candidates(root)) {
    if (!element.id) continue;
    const standing = byElement.get(element);
    if (
      standing &&
      standing.document.kind === documentContext.kind &&
      (documentContext.kind === "thread" ||
        standing.document.revision === documentContext.revision)
    ) {
      captured.set(element.id, standing);
      continue;
    }
    const declaration = structuredClone(runtime.registry[element.localName]);
    const ancestors = declaredAncestors(element);
    const descriptor = {
      id: element.id,
      tag: element.localName,
      document: structuredClone(documentContext),
      declaration,
      parent: ancestors[0] ?? null,
      ancestors,
      quoted: quotedBy(element),
    };
    bindings.push({ element, descriptor });
    captured.set(element.id, descriptor);
  }
  return Object.freeze({
    descriptors: captured,
    bindings: Object.freeze(bindings),
  });
}

export function commitWidgetDescriptors(stage, retired = new Set()) {
  // A revision that rewrites a widget's authored markup retires the descriptor taken
  // from the markup it replaced. The id survives the revision and the element does not,
  // so the id-keyed readings are the ones that would otherwise answer for a document
  // nobody is reading; the element-keyed ones leave with their elements.
  for (const id of retired) {
    byId.delete(id);
    elements.delete(id);
  }
  for (const { element, descriptor } of stage.bindings) {
    byElement.set(element, descriptor);
    byId.set(descriptor.id, descriptor);
    elements.set(descriptor.id, element);
  }
}

// The element standing for a widget id: the one the document holds under it, else the
// bound node not yet mounted (a message's frozen markup before the thread places it).
export const widgetElement = (id) => elementById(id) ?? elements.get(id) ?? null;

export function widgetDescriptor(owner) {
  const captured = byElement.get(owner);
  if (captured) return captured;
  const replacement = byId.get(owner.id);
  if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
  byElement.set(owner, replacement);
  return replacement;
}

export const descriptorStillMatches = (owner, descriptor) =>
  owner.id === descriptor.id && owner.localName === descriptor.tag;
