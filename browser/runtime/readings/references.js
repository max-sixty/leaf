// Compiled from references.ts by build/typescript.mjs; edit that file.
/* Resolve an id an element gives in that element's authored scope: a registry-declared
   relation, which navigation and typed widget inputs share, and any address a package
   module looks up (anchor-resolution.js, `elementNamed`). */
import { registry } from "../state/registry.js";
import { authoredScope, elementById, pageDocument } from "./passages.js";

// Package code hands `navigateToDatum` the `refers` attribute to follow, so an
// undeclared one is that code's error, thrown at the call rather than read as a
// reference to nothing. An input's `reference` attribute is declared by composition
// (Python's `registry.contract.complete_declarations`), so its reader asks nothing here.
export function requireReference(owner, attribute) {
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.refers ?? {}, attribute)
  )
    throw new TypeError(
      `navigateToDatum ${owner.localName} attribute ${String(attribute)} is not declared by refers`,
    );
}

// The element an id that `from` gives names: in the authored document `from` stands in
// first, so a widget in a message finds its message's element before a page element
// with the same id, as the server's request check does, and then in the page beside
// it, which a message's widget may name. Leaf's own surfaces hold nothing it names
// beyond `from`'s message.
export function authoredElement(id, from) {
  const scope = authoredScope(from);
  const page = pageDocument();
  return elementById(id, scope) ?? (scope === page ? null : elementById(id, page));
}

// The element a `refers` attribute names, by id, as the owner gives it. A mounted
// input supplies its captured value: its binding stays fixed while the producer
// instance may change.
export function referencedProjection(
  owner,
  attribute,
  id = owner.getAttribute(attribute),
) {
  return id ? authoredElement(id, owner) : null;
}
