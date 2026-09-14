/* Revision-bound widget identity captured before a content module upgrades the DOM.

   A controller receives no caller-supplied declaration or scope. Leaf records the
   authored owner, its declared ancestors, exhibit fence, and direct request offers
   while the revision's markup is still intact. Later physical reparenting is layout;
   semantic commands keep using this captured document coordinate. A data renderer may
   replace a widget node while preserving its authored id; that replacement reuses the
   same revision-bound descriptor and target boundary. */
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
const byId = new Map();
const referenceBoundaryById = new Map();

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

const conditionMatches = (element, when = {}) =>
  Object.entries(when).every(([attribute, values]) =>
    values.some((value) =>
      typeof value === "boolean"
        ? element.hasAttribute(attribute) === value
        : element.getAttribute(attribute) === value,
    ),
  );

function askDescriptor(element, declaration, documentContext) {
  const ask = declaration["x-awaits"];
  if (!ask || ask.rollup || !conditionMatches(element, ask.when)) return null;
  const until = documentContext.kind === "thread" && ask.until;
  const answers =
    until && conditionMatches(element, until.when) ? [until.verb] : ask.answers;
  return {
    answers,
    empty: Object.fromEntries(
      answers.flatMap((verb) => {
        const empty = declaration["x-state"][verb].completion?.empty;
        if (!empty) return [];
        const containers = [...element.querySelectorAll(empty.within)].filter(
          (container) => conditionMatches(container, empty.when),
        );
        return [[verb, containers.length === 1 ? containers[0].id : null]];
      }),
    ),
  };
}

// `boundary` is the document region this markup's target references resolve within.
// It is derived from the markup itself wherever the markup is already standing in that
// region. A live revision activation is the one caller that holds them apart: it reads
// the incoming revision off an inert copy so each widget's declaration is captured
// before a controller can rewrite it, while the references those widgets capture belong
// to the `main` they are about to be patched into.
export function captureWidgetDescriptors(
  root = document,
  documentContext = { kind: "page", revision: runtime.currentRevision },
  boundary = null,
) {
  const captured = new Map();
  const referenceBoundary =
    boundary ??
    (documentContext.kind === "thread"
      ? targetReferenceBoundary(root.children)
      : root.matches?.("main")
        ? root
        : root.querySelector("main"));
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
      ask: askDescriptor(element, declaration, documentContext),
      bindings: requestBindings(element, declaration),
      offers: requestOffers(element, declaration),
    };
    byElement.set(element, descriptor);
    referenceBoundaryByElement.set(element, referenceBoundary);
    byId.set(element.id, descriptor);
    referenceBoundaryById.set(element.id, referenceBoundary);
    captured.set(element.id, descriptor);
  }
  if (captured.size) applicationState.captureDescriptors(captured);
}

// A revision that rewrites a widget's authored markup retires the descriptor taken from
// the markup it replaced. The id survives the revision and the element does not, so the
// id-keyed readings are the ones that would otherwise answer for a document nobody is
// reading; the element-keyed ones leave with their elements.
export function forgetWidgetDescriptors(ids) {
  for (const id of ids) {
    byId.delete(id);
    referenceBoundaryById.delete(id);
  }
}

export function widgetDescriptor(owner) {
  const captured = byElement.get(owner);
  if (captured) return captured;
  const replacement = byId.get(owner.id);
  if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
  byElement.set(owner, replacement);
  referenceBoundaryByElement.set(owner, referenceBoundaryById.get(owner.id));
  return replacement;
}

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
