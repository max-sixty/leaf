/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * shares every subtree equal to the standing reading's, freezes them, and replaces one
 * private signal synchronously. This module does not derive activity, reconcile
 * receipts, or perform transport and rendering.
 *
 * Sharing is what makes identity mean "unchanged": a fold rebuilds its whole result on
 * every publication, and a subtree whose contents did not move comes back as the
 * object the last reading held. So a selection is a `computed` compared by identity,
 * and a reader subscribed to one part of the reading hears only that part change. A
 * selection shares its own derived value against its previous one by the same rule.
 */
import { computed, signal } from "./signals-core.js";























// Object.freeze says nothing about descendants or Map/Set entries. Only values this
// owner has secured can skip traversal when a publication reuses a standing subtree.
const secured = new WeakSet        ();

function immutable   (value   , normalized = new WeakMap                ())               {
  if (value !== null && typeof value === "object" && !secured.has(value)) {
    const known = normalized.get(value);
    if (known) return known                ;
    let result         = value;
    const refuse = () => {
      throw new TypeError("Application snapshots are read-only");
    };
    if (value instanceof Map) {
      const entries = [...value].map(([key, child]) => [
        immutable(key, normalized), immutable(child, normalized),
      ]         );
      const map = Object.isExtensible(value) ? value : new Map();
      map.clear();
      for (const [key, child] of entries) map.set(key, child);
      for (const name of ["set", "delete", "clear"])
        Object.defineProperty(map, name, { value: refuse });
      result = map;
    } else if (value instanceof Set) {
      const members = [...value].map((child) => immutable(child, normalized));
      const set = Object.isExtensible(value) ? value : new Set();
      set.clear();
      for (const child of members) set.add(child);
      for (const name of ["add", "delete", "clear"])
        Object.defineProperty(set, name, { value: refuse });
      result = set;
    } else {
      const children = Object.entries(value).map(([key, child]) => [
        key, child, immutable(child, normalized),
      ]         );
      if (children.some(([, child, next]) => child !== next)) {
        // A frozen collection needs replacement; copy its frozen ancestors only
        // where that replacement cannot be written into the original wrapper.
        const target = Object.isFrozen(value)
          ? Array.isArray(value) ? [...value] : { ...value }
          : value;
        for (const [key, child, next] of children)
          if (child !== next) (target                           )[key] = next;
        result = target;
      }
    }
    Object.freeze(result);
    secured.add(result);
    normalized.set(value, result);
    return result                ;
  }
  return value                ;
}

const plain = (value        ) => {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

/**
 * `next`, with every subtree deep-equal to the matching one in `prior` replaced by
 * `prior`'s. Plain objects, arrays, Maps and Sets compare by contents (a Map or Set by
 * its entries in order, an object by its keys in any order); anything else by identity.
 * Returns `prior` itself when the two are equal, and `next` itself when nothing in it
 * could be shared, so neither input is copied or mutated needlessly.
 */
export function share   (prior         , next   )    {
  if (Object.is(prior, next)) return next;
  if (
    prior === null ||
    next === null ||
    typeof prior !== "object" ||
    typeof next !== "object"
  )
    return next;
  if (Array.isArray(next)) {
    if (!Array.isArray(prior)) return next;
    const children = next.map((child, index) => share(prior[index], child));
    if (
      prior.length === next.length &&
      children.every((child, index) => child === prior[index])
    )
      return prior     ;
    return (children.every((child, index) => child === next[index])
      ? next
      : children)     ;
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(([key, child]) => [
      key,
      prior.has(key) ? share(prior.get(key), child) : child,
    ]         );
    if (
      priorKeys.length === entries.length &&
      entries.every(([key, child], index) =>
        key === priorKeys[index] && child === prior.get(key))
    )
      return prior     ;
    return (entries.every(([key, child]) => child === next.get(key))
      ? next
      : new Map(entries))     ;
  }
  if (next instanceof Set) {
    if (!(prior instanceof Set)) return next;
    const priorMembers = [...prior];
    const members = [...next].map((child, index) => share(priorMembers[index], child));
    if (
      priorMembers.length === members.length &&
      members.every((child, index) => child === priorMembers[index])
    )
      return prior     ;
    return (members.every((child) => next.has(child)) ? next : new Set(members))     ;
  }
  if (!plain(next) || !plain(prior) || Array.isArray(prior) || prior instanceof Map
    || prior instanceof Set)
    return next;
  const before = prior                           ;
  const after = next                           ;
  const keys = Object.keys(after);
  const children = keys.map((key) =>
    Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key]);
  if (
    keys.length === Object.keys(before).length &&
    keys.every((key, index) => Object.hasOwn(before, key) && children[index] === before[key])
  )
    return prior     ;
  if (keys.every((key, index) => children[index] === after[key])) return next;
  const copy                          = Object.getPrototypeOf(next) === null
    ? Object.create(null)
    : {};
  // Defined, not assigned: a JSON field named `__proto__` is an own property, and
  // assigning it would set the copy's prototype instead.
  keys.forEach((key, index) =>
    Object.defineProperty(copy, key, {
      value: children[index],
      writable: true,
      enumerable: true,
      configurable: true,
    }),
  );
  return copy     ;
}

export function createApplicationPublisher                               (initial   ) {
  const root = signal(immutable(initial));
  return Object.freeze({
    read: ()               => root.value,
    publish(candidate   )               {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select   (derive                               )                                {
      let prior         ;
      const selected = computed(
        () => (prior = immutable(share(prior, derive(root.value)))),
      );
      return Object.freeze({
        read: ()               => selected.value,
        subscribe: (listener                               ) =>
          selected.subscribe(listener),
      });
    },
  });
}
// Generated from build/browser/snapshot.ts by build/browser/build.mjs.
