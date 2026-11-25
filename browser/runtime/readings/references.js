/* Resolve an id an element gives in that element's authored scope: a registry-declared
   relation, which typed widget inputs read, and an address a view names
   (anchor-resolution.js, `elementNamed`). An input's `reference` attribute is declared
   by composition (Python's `registry.contract.complete_declarations`). */
import { authoredScope, elementById, pageDocument } from "./passages.js";

// The element an id that `from` gives names: in the authored document `from` stands in
// first, so a widget in a message finds its message's element before a page element
// with the same id, as the server's request check does, and then in the page beside
// it, which a message's widget may name. Leaf's own surfaces hold nothing it names
// beyond `from`'s message.
/** @param {string} id @param {Node} from */
export function authoredElement(id, from) {
  const scope = authoredScope(from);
  const page = pageDocument();
  return (
    (scope ? elementById(id, scope) : null) ??
    (scope === page || !page ? null : elementById(id, page))
  );
}

// The element a `refers` attribute names, by id, as the owner gives it. A mounted
// input supplies its captured value: its binding stays fixed while the producer
// instance may change.
/** @param {Element} owner @param {string} attribute @param {string | null} [id] */
export function referencedProjection(
  owner,
  attribute,
  id = owner.getAttribute(attribute),
) {
  return id ? authoredElement(id, owner) : null;
}
