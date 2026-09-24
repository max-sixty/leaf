/* Revision-bound widget identity captured before a content module upgrades the DOM.

   A controller receives no caller-supplied declaration or scope. Leaf records the
   authored owner, its declared ancestors, exhibit fence, and direct request offers
   while the revision's markup is still intact. Later physical reparenting is layout;
   semantic commands keep using this captured document coordinate. A data renderer may
   replace a widget node while preserving its authored id; that replacement reuses the
   same revision-bound descriptor. */
import { runtime } from "./context.js";
import { authoredParents } from "./projection/authored.js";

const byElement = new WeakMap();
const byId = new Map();

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
  if (declaration["x-request"]?.records) return {};
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
      bindings: requestBindings(element, declaration),
      offers: requestOffers(element, declaration),
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
  for (const id of retired) byId.delete(id);
  for (const { element, descriptor } of stage.bindings) {
    byElement.set(element, descriptor);
    byId.set(descriptor.id, descriptor);
  }
}

export function widgetDescriptor(owner) {
  const captured = byElement.get(owner);
  if (captured) return captured;
  const replacement = byId.get(owner.id);
  if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
  byElement.set(owner, replacement);
  return replacement;
}

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
