/* Stable references to authored DOM targets, and the one candidate walk used by
 * pointer and keyboard targeting.
 *
 * An authored id is the exact identity when one exists. Anonymous elements use a
 * structural path from a caller-owned root or its nearest id-bearing ancestor. Each
 * step records only its tag, never words, labels, style, or a sibling ordinal. A unique
 * path survives unrelated insertion and reordering. An indistinguishable path makes
 * resolution ambiguous instead of moving the reference to whichever node now occupies
 * an ordinal.
 *
 * Resolution is deliberately three-valued. Only `resolved` carries an element;
 * `detached` means no candidate remains and `ambiguous` means the current DOM cannot
 * prove which candidate owns the reference. Callers must not choose one in either
 * unresolved state. */
import { elementFromPointAcross } from "./passages.js";
import { under, upFrom } from "./shadow.js";

const GENERATED = ".lf-ui, [data-lf-gen]";
const BOUNDARY = Symbol("target-reference-boundary");

const isElement = (value) => value?.nodeType === Node.ELEMENT_NODE;

function requireElement(value, name) {
  if (!isElement(value)) throw new TypeError(`leaf: ${name} must be an Element`);
}

const isBoundary = (value) => value?.kind === BOUNDARY;

export function targetReferenceBoundary(nodes) {
  const roots = [...nodes];
  if (!roots.length || roots.some((node) => !isElement(node)))
    throw new TypeError("leaf: a target boundary needs authored Element roots");
  return Object.freeze({ kind: BOUNDARY, roots: Object.freeze(roots) });
}

function requireRoot(value) {
  if (!isElement(value) && !isBoundary(value))
    throw new TypeError("leaf: target root must be an Element");
}

const rootContains = (root, element) =>
  isBoundary(root)
    ? root.roots.some((candidate) => under(element, candidate))
    : under(element, root);

const isRoot = (root, element) =>
  isBoundary(root) ? root.roots.includes(element) : root === element;

function childrenIn(element, tree) {
  const parent = tree === "shadow" ? element.shadowRoot : element;
  return parent
    ? [...parent.children].filter((child) => !child.matches(GENERATED))
    : [];
}

function generatedBelow(element, root) {
  for (
    let current = element;
    current && !isRoot(root, current);
    current = upFrom(current)
  )
    if (current.matches(GENERATED)) return true;
  return false;
}

function sourceElement(source) {
  if (isElement(source)) return source;
  if (Number.isFinite(source?.x) && Number.isFinite(source?.y))
    return elementFromPointAcross(source.x, source.y);
  throw new TypeError("leaf: a target source must be an Element or an {x, y} point");
}

// Nearest first, through every authored ancestor up to the supplied boundary. A point
// and a focused element differ only in how the first node is found; they take this same
// unbounded walk thereafter.
export function targetCandidates(root, source) {
  requireRoot(root);
  const start = sourceElement(source);
  if (!start || !rootContains(root, start)) return [];

  const candidates = [];
  for (let current = start; current; current = upFrom(current)) {
    if (!generatedBelow(current, root)) candidates.push(current);
    if (isRoot(root, current)) return candidates;
  }
  return [];
}

function parentStep(element) {
  if (element.parentElement) return { parent: element.parentElement, tree: "light" };
  const root = element.getRootNode();
  if (root instanceof ShadowRoot && root.host)
    return { parent: root.host, tree: "shadow" };
  return null;
}

export function captureTargetReference(root, target) {
  requireRoot(root);
  requireElement(target, "target");
  if (!targetCandidates(root, target).includes(target))
    throw new TypeError(
      "leaf: a target must be authored content under its target root",
    );

  if (target.id) return { kind: "id", id: target.id };

  const path = [];
  for (let current = target; !isRoot(root, current);) {
    if (current !== target && current.id)
      return { kind: "structure", anchor: current.id, path };
    const relation = parentStep(current);
    if (!relation) throw new TypeError("leaf: a target must be under its target root");
    path.unshift({ tree: relation.tree, tag: current.localName });
    current = relation.parent;
  }
  if (isBoundary(root)) {
    const top = targetCandidates(root, target).at(-1);
    if (top !== target && top.id) return { kind: "structure", anchor: top.id, path };
    path.unshift({ tree: "light", tag: top.localName });
  }
  return { kind: "structure", path };
}

function elementsUnder(root) {
  const elements = [];
  const visit = (element) => {
    if (element !== root && element.matches(GENERATED)) return;
    elements.push(element);
    for (const child of childrenIn(element, "light")) visit(child);
    for (const child of childrenIn(element, "shadow")) visit(child);
  };
  for (const element of isBoundary(root) ? root.roots : [root]) visit(element);
  return elements;
}

const resolved = (element) => ({ status: "resolved", element });
const detached = () => ({ status: "detached" });
const ambiguous = () => ({ status: "ambiguous" });

const matchingId = (root, id) =>
  elementsUnder(root).filter((element) => element.id === id);

export function resolveTargetReference(root, reference) {
  requireRoot(root);
  if (reference?.kind === "id" && typeof reference.id === "string") {
    const matches = matchingId(root, reference.id);
    if (!matches.length) return detached();
    return matches.length === 1 ? resolved(matches[0]) : ambiguous();
  }

  if (reference?.kind !== "structure" || !Array.isArray(reference.path))
    throw new TypeError("leaf: invalid target reference");

  if (isBoundary(root) && !("anchor" in reference) && !reference.path.length)
    return detached();

  let candidates = [root];
  if ("anchor" in reference) {
    if (typeof reference.anchor !== "string")
      throw new TypeError("leaf: invalid structural target reference");
    candidates = matchingId(root, reference.anchor);
    if (!candidates.length) return detached();
    if (candidates.length > 1) return ambiguous();
  }
  for (const step of reference.path) {
    if (
      !step ||
      (step.tree !== "light" && step.tree !== "shadow") ||
      typeof step.tag !== "string"
    )
      throw new TypeError("leaf: invalid structural target reference");
    candidates = candidates.flatMap((parent) =>
      (isBoundary(parent)
        ? step.tree === "light"
          ? parent.roots
          : []
        : childrenIn(parent, step.tree)
      ).filter((child) => child.localName === step.tag && !child.id),
    );
    if (!candidates.length) return detached();
  }
  return candidates.length === 1 ? resolved(candidates[0]) : ambiguous();
}
