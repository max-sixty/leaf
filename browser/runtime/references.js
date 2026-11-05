/* Resolve registry-declared element relations in the owner's authored scope.
   Navigation and typed widget inputs share this one reading. */
import { registry } from "./registry.js";
import { authoredScope, elementById, pageDocument } from "./passages.js";

// The verbs that follow an `x-refers` attribute (`navigateToDatum`, `data`) are handed
// it by package code, so an undeclared one is that code's error, thrown at the call
// rather than read as a reference to nothing.
/** @param {string} verb @param {Element} owner @param {string} attribute */
export function requireReference(verb, owner, attribute) {
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute)
  )
    throw new TypeError(
      `${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`,
    );
}

// The element an `x-refers` attribute names. A keyed contract names the member whose
// key holds the value inside the owner's nearest enclosing scope, the scope the
// member's x-unique declares for that key. Any other names an id: in the owner's own
// authored document first, so a widget in a message finds its message's element before
// a page element with the same id, as the server's request check does, and then in the
// page beside it, which a message's widget may name. A mounted input supplies its
// captured value: its binding stays fixed while the producer instance may change.
/** @param {Element} owner @param {string} attribute @param {string | null} [id] */
export function referencedProjection(
  owner,
  attribute,
  id = owner.getAttribute(attribute),
) {
  if (!id) return null;
  const { tag, key } = registry[owner.localName]["x-refers"][attribute];
  if (tag) {
    const within = registry[tag]["x-unique"][key];
    /** @param {Element} element */
    const scopeOf = (element) => element.parentElement?.closest(within) ?? null;
    const scope = scopeOf(owner);
    return (
      [...(scope?.querySelectorAll(tag) ?? [])].find(
        (member) => scopeOf(member) === scope && member.getAttribute(key) === id,
      ) ?? null
    );
  }
  const scope = authoredScope(owner);
  const page = pageDocument();
  return (
    (scope ? elementById(id, scope) : null) ??
    (scope === page || !page ? null : elementById(id, page))
  );
}
