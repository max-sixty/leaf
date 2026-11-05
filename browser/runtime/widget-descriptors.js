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

/** @typedef {import("./framework/application.js").WidgetDescriptor} WidgetDescriptor */
/** @type {WeakMap<Element, WidgetDescriptor>} */
const byElement = new WeakMap();
/** @type {Map<string, WidgetDescriptor>} */
const byId = new Map();
/** @type {Map<string, Element>} */
const elements = new Map();

const declaredTags = () => elementDeclarations().map(([tag]) => tag);

/** @param {Document | Element | DocumentFragment} root */
const candidates = (root) => {
  const tags = declaredTags();
  if (!tags.length) return [];
  const selector = tags.join(",");
  const found = [...root.querySelectorAll(selector)];
  if (root instanceof Element && root.matches(selector)) found.unshift(root);
  return found;
};

/** @param {Element} element @returns {Element | null} */
const parentOf = (element) =>
  authoredParents.has(element) ? authoredParents.get(element) : element.parentElement;

/** @param {Element} element */
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
/** @param {Element} element */
const quotedBy = (element) => {
  for (let node = parentOf(element); node; node = parentOf(node))
    if (exhibits(node, runtime.registry[node.localName])) return true;
  return false;
};

/** @param {Document | Element | DocumentFragment} [root]
 * @param {WidgetDescriptor["document"]} [documentContext] */
export function stageWidgetDescriptors(
  root = document,
  documentContext = { kind: "page", revision: runtime.currentRevision },
) {
  /** @type {Map<string, WidgetDescriptor>} */
  const captured = new Map();
  /** @type {{element: Element, descriptor: WidgetDescriptor}[]} */
  const bindings = [];
  for (const element of candidates(root)) {
    if (!element.id) continue;
    const existing = byElement.get(element);
    if (
      existing &&
      existing.document.kind === documentContext.kind &&
      (documentContext.kind === "thread" ||
        (existing.document.kind === "page" &&
          existing.document.revision === documentContext.revision))
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
    bindings.push({ element, descriptor });
    captured.set(element.id, descriptor);
  }
  return Object.freeze({
    descriptors: captured,
    bindings: Object.freeze(bindings),
  });
}

/** @param {Pick<ReturnType<typeof stageWidgetDescriptors>, "bindings">} stage @param {Set<string>} [retired] */
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
/** @param {string} id */
export const widgetElement = (id) => elementById(id) ?? elements.get(id) ?? null;

/** @param {Element} owner */
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
/** @param {Element} element */
export const quoted = (element) =>
  widgetDescriptor(element)?.quoted ?? quotedBy(element);

/** @param {Element} owner @param {WidgetDescriptor} descriptor */
export const descriptorStillMatches = (owner, descriptor) =>
  owner.id === descriptor.id && owner.localName === descriptor.tag;
