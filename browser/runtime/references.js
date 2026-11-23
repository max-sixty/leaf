/* Resolve registry-declared element relations in the owner's authored scope.
   Navigation and typed widget inputs share this one reading. */
import { registry } from "./registry.js";
import { authoredScope, elementById, pageDocument } from "./passages.js";

// Package code hands `navigateToDatum` the `refers` attribute to follow, so an
// undeclared one is that code's error, thrown at the call rather than read as a
// reference to nothing. An input's `reference` attribute is declared by composition
// (Python's `registry.contract.complete_declarations`), so its reader asks nothing here.
/** @param {Element} owner @param {string} attribute */
export function requireReference(owner, attribute) {
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.refers ?? {}, attribute)
  )
    throw new TypeError(
      `navigateToDatum ${owner.localName} attribute ${String(attribute)} is not declared by refers`,
    );
}

// The element a `refers` attribute names, by id: in the owner's own authored document
// first, so a widget in a message finds its message's element before a page element
// with the same id, as the server's request check does, and then in the page beside
// it, which a message's widget may name. A mounted input supplies its captured value:
// its binding stays fixed while the producer instance may change.
/** @param {Element} owner @param {string} attribute @param {string | null} [id] */
export function referencedProjection(
  owner,
  attribute,
  id = owner.getAttribute(attribute),
) {
  if (!id) return null;
  const scope = authoredScope(owner);
  const page = pageDocument();
  return (
    (scope ? elementById(id, scope) : null) ??
    (scope === page || !page ? null : elementById(id, page))
  );
}
