/* Revision-bound widget identity captured before a content module upgrades the DOM.

   A controller receives no caller-supplied declaration or scope. Leaf records the
   authored owner, its declared ancestors, exhibit fence, and direct request offers
   while the revision's markup is still intact. Later physical reparenting is layout;
   semantic commands keep using this captured document coordinate. */
import { runtime } from "./context.js";
import { applicationState } from "./semantic-state.js";
import { authoredParents } from "./projection/authored.js";
import {
  captureTargetReference,
  resolveTargetReference,
  targetReferenceBoundary,
} from "./target-references.js";

const byElement = new WeakMap();
const referenceBoundaryByElement = new WeakMap();

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

const requestOffers = (element, declaration) => {
  const offers = declaration["x-request"]?.offers ?? {};
  const captured = [];
  for (const child of element.children) {
    const attribute = offers[child.localName];
    const verb = attribute && child.getAttribute(attribute);
    if (verb) captured.push({ tag: child.localName, attribute, verb });
  }
  return captured;
};

const requestBindings = (element, declaration) => {
  const attributes = new Set(
    Object.values(declaration["x-request"]?.verbs ?? {}).flatMap((request) =>
      Object.values(request.bind ?? {}),
    ),
  );
  return Object.fromEntries(
    [...attributes].map((attribute) => [attribute, element.getAttribute(attribute)]),
  );
};

const quotedBy = (element) => {
  for (let node = element; node; node = parentOf(node))
    if (runtime.registry[node.localName]?.["x-exhibit"]) return true;
  return false;
};

export function captureWidgetDescriptors(
  root = document,
  documentContext = { kind: "page", revision: runtime.currentRevision },
) {
  const captured = new Map();
  const referenceBoundary =
    documentContext.kind === "thread"
      ? targetReferenceBoundary(root.children)
      : root.matches?.("main")
        ? root
        : root.querySelector("main");
  for (const element of candidates(root)) {
    if (!element.id || byElement.has(element)) continue;
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
      bindings: requestBindings(element, declaration),
      offers: requestOffers(element, declaration),
    };
    byElement.set(element, descriptor);
    referenceBoundaryByElement.set(element, referenceBoundary);
    captured.set(element.id, descriptor);
  }
  if (captured.size) applicationState.captureDescriptors(captured);
}

export const widgetDescriptor = (owner) => byElement.get(owner) ?? null;

export function captureWidgetReference(owner, target) {
  const boundary = referenceBoundaryByElement.get(owner);
  const reference = captureTargetReference(boundary, target);
  const resolution = resolveTargetReference(boundary, reference);
  if (resolution.status !== "resolved" || resolution.element !== target)
    throw new TypeError(
      `leaf: target reference is ${resolution.status} in its authored document`,
    );
  return reference;
}

export const resolveWidgetReference = (owner, reference) =>
  resolveTargetReference(referenceBoundaryByElement.get(owner), reference);

export function descriptorStillMatches(owner, descriptor) {
  if (owner.id !== descriptor.id || owner.localName !== descriptor.tag) return false;
  if (
    Object.entries(descriptor.bindings).some(
      ([attribute, value]) => owner.getAttribute(attribute) !== value,
    )
  )
    return false;
  const currentOffers = requestOffers(owner, descriptor.declaration).sort(
    (left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)),
  );
  const capturedOffers = [...descriptor.offers].sort((left, right) =>
    JSON.stringify(left).localeCompare(JSON.stringify(right)),
  );
  return JSON.stringify(currentOffers) === JSON.stringify(capturedOffers);
}
