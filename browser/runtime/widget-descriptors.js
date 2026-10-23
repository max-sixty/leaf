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
import { elementDeclarations, exhibits } from "./registry.js";
import { isElementName } from "./registry-contract.js";
import { authoredParents } from "./projection/authored.js";
import { elementById } from "./passages.js";
import { initialOrigin, initialParent, initialSource } from "./initial-render.js";

const byElement = new WeakMap();
const byId = new Map();
const elements = new Map();

const declaredTags = () => elementDeclarations().map(([tag]) => tag);

const candidates = (root) => {
  const tags = declaredTags();
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root.nodeType === Node.ELEMENT_NODE && root.matches(selector))
    found.unshift(root);
  return found;
};

const parentOf = (element) => {
  if (authoredParents.has(element)) return authoredParents.get(element);
  if (element.parentElement) return element.parentElement;
  // A copied arriving root is detached, although its authored coordinate was
  // captured against the parent it will join before insertion. Only that outer
  // edge leaves the reconstructed source tree; descendants use its own ancestry.
  const live = initialOrigin(element);
  return authoredParents.has(live) ? authoredParents.get(live) : initialParent(live);
};

const declaredAncestors = (element) => {
  const ancestors = [];
  for (let parent = parentOf(element); parent; parent = parentOf(parent))
    if (
      parent.id &&
      isElementName(parent.localName) &&
      runtime.registry[parent.localName]
    )
      ancestors.push({ id: parent.id, tag: parent.localName });
  return ancestors;
};

// Whether an element stands strictly inside an x-exhibit widget in the authored
// document, so what it holds is quoted material rather than controls (`quoted` below).
// The exhibit itself is no mention, as the server reads it (`obligations.quoted_in`);
// `tests/exhibit_cases.json` holds both runtimes to one set of cases. Asked of
// authored parents, so a widget layout has moved still answers for where it was
// written.
const quotedBy = (element) => {
  for (let node = parentOf(element); node; node = parentOf(node))
    if (exhibits(node, runtime.registry[node.localName])) return true;
  return false;
};

/** @param {Document | Element | DocumentFragment} [root]
 * @param {{kind: "page" | "thread", revision?: number, thread?: string, message?: string}} [documentContext] */
export function stageWidgetDescriptors(
  root = document,
  documentContext = { kind: "page", revision: runtime.currentRevision },
) {
  const captured = new Map();
  const bindings = [];
  for (const element of candidates(initialSource(root))) {
    if (!element.id) continue;
    const live = initialOrigin(element);
    const existing = byElement.get(live);
    if (
      existing &&
      existing.document.kind === documentContext.kind &&
      (documentContext.kind === "thread" ||
        existing.document.revision === documentContext.revision)
    ) {
      captured.set(element.id, existing);
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
    bindings.push({ element: live, descriptor });
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

// Mention, not use: a widget inside one the registry marks x-exhibit is quoted
// material. An interactive widget consults this before wiring anything that would carry
// input back (a choose path, a drag grip), so an exhibit never takes the user's edits.
// Presentational upgrades and view state run regardless — a quoted diagram still
// renders, a quoted settled group still collapses. The answer is the one its
// controller's actions read, the descriptor's, or the same rule for an element with
// no descriptor.
export const quoted = (element) =>
  widgetDescriptor(element)?.quoted ?? quotedBy(element);

export const descriptorStillMatches = (owner, descriptor) =>
  owner.id === descriptor.id && owner.localName === descriptor.tag;
