/* Revision-bound widget identity captured before a content module upgrades the DOM.

   A controller receives no caller-supplied declaration or scope. Leaf records the
   authored owner, its declared ancestors, and exhibit fence while the revision's
   markup is still intact. Later physical reparenting is layout;
   semantic commands keep using this captured document coordinate. A data renderer may
   replace a widget node while preserving its authored id; that replacement takes the
   descriptor the adopted reading holds under the id.

   Each id's descriptor has one home, the application state's `document.descriptors`,
   which a reading changes only as the page adopts it, so one the page refuses leaves
   no descriptor behind. What this module keeps is each captured element's own
   descriptor, beside the element and gone with it. A message's markup is bound when
   each wording is prepared, before the thread mounts it, so a module connecting
   there finds its widget at once. */
import { untracked } from "/vendor/signals-core.js";
import { runtime } from "../state/context.js";
import { declaredElements, exhibits } from "../state/registry.js";
import { isElementName } from "../state/registry-contract.js";
import { authoredParents } from "./projection/authored.js";
import { readPart } from "../state/semantic-state.js";

/** @typedef {import("../state/semantic-application.js").WidgetDescriptor} WidgetDescriptor */
/** @type {WeakMap<Element, WidgetDescriptor>} */
const byElement = new WeakMap();
const adoptedDescriptors = readPart((root) => root.document.descriptors);

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

// Whether an element stands strictly inside an `exhibit` widget in the authored
// document, so what it holds is quoted material rather than controls (`quoted` below).
// The exhibit itself is no mention, as the server reads it (`structure.quoted_in`);
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
  for (const element of declaredElements(root)) {
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

// Each staged descriptor on the element it stands for, before insertion can connect
// the element's custom element.
/** @param {ReturnType<typeof stageWidgetDescriptors>["bindings"]} bindings */
export function bindWidgetDescriptors(bindings) {
  for (const { element, descriptor } of bindings) byElement.set(element, descriptor);
}

/** @param {Element} owner */
export function widgetDescriptor(owner) {
  const captured = byElement.get(owner);
  if (captured) return captured;
  // An element's descriptor is bound for its life, so a reader's paint doesn't follow
  // the adopted descriptors through this read.
  const replacement = untracked(adoptedDescriptors).get(owner.id);
  if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
  byElement.set(owner, replacement);
  return replacement;
}

// Mention, not use: a widget inside one the registry marks `exhibit` is quoted
// material, whose change a version comparison doesn't mark (features/version.js). A module asks
// the same of the exhibit's `data-lf-exhibit` mark before wiring anything that would
// carry input back (a choose path, a drag grip), so an exhibit never takes the user's
// edits. The answer is the one its controller's actions read, the descriptor's, or the
// same rule for an element with no descriptor.
/** @param {Element} element */
export const quoted = (element) =>
  widgetDescriptor(element)?.quoted ?? quotedBy(element);

/** @param {Element} owner @param {WidgetDescriptor} descriptor */
export const descriptorStillMatches = (owner, descriptor) =>
  owner.id === descriptor.id && owner.localName === descriptor.tag;
