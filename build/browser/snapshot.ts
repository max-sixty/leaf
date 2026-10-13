/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * shares every subtree equal to the current reading's, freezes them, and replaces one
 * private signal synchronously. This module does not derive activity, reconcile
 * receipts, or perform transport and rendering.
 *
 * Sharing is what makes identity mean "unchanged": a fold rebuilds its whole result on
 * every publication, and a subtree whose contents did not move comes back as the
 * object the last reading held. So a selection is a `computed` compared by identity,
 * and a reader subscribed to one part of the reading hears only that part change. A
 * selection shares its own derived value against its previous one by the same rule.
 */
import { computed, signal } from "@preact/signals-core";

export type Immutable<T> =
  T extends ReadonlyMap<infer K, infer V>
    ? ReadonlyMap<Immutable<K>, Immutable<V>>
    : T extends ReadonlySet<infer V>
      ? ReadonlySet<Immutable<V>>
      : T extends object
        ? { readonly [K in keyof T]: Immutable<T[K]> }
        : T;

interface ApplicationSnapshot {
  readonly document: unknown;
  readonly authoritative: unknown;
  readonly unresolved: readonly unknown[];
  readonly effective: unknown;
  readonly semanticEpoch: number;
}

interface SnapshotReading<T> {
  read(): T;
  subscribe(listener: (value: T) => void): () => void;
}

// Object.freeze says nothing about descendants or Map/Set entries. Only values this
// owner has secured can skip traversal when a publication reuses an existing subtree.
const secured = new WeakSet<object>();

function immutable<T>(value: T, normalized = new WeakMap<object, object>()): Immutable<T> {
  if (value !== null && typeof value === "object" && !secured.has(value)) {
    const known = normalized.get(value);
    if (known) return known as Immutable<T>;
    let result: object = value;
    const refuse = () => {
      throw new TypeError("Application snapshots are read-only");
    };
    if (value instanceof Map) {
      const entries = [...value].map(([key, child]) => [
        immutable(key, normalized), immutable(child, normalized),
      ] as const);
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
      ] as const);
      if (children.some(([, child, next]) => child !== next)) {
        // A frozen collection needs replacement; copy its frozen ancestors only
        // where that replacement cannot be written into the original wrapper.
        const target = Object.isFrozen(value)
          ? Array.isArray(value) ? [...value] : { ...value }
          : value;
        for (const [key, child, next] of children)
          if (child !== next) (target as Record<string, unknown>)[key] = next;
        result = target;
      }
    }
    Object.freeze(result);
    secured.add(result);
    normalized.set(value, result);
    return result as Immutable<T>;
  }
  return value as Immutable<T>;
}

const plain = (value: object) => {
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
export function share<T>(prior: unknown, next: T): T {
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
      return prior as T;
    return (children.every((child, index) => child === next[index])
      ? next
      : children) as T;
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(([key, child]) => [
      key,
      prior.has(key) ? share(prior.get(key), child) : child,
    ] as const);
    if (
      priorKeys.length === entries.length &&
      entries.every(([key, child], index) =>
        key === priorKeys[index] && child === prior.get(key))
    )
      return prior as T;
    return (entries.every(([key, child]) => child === next.get(key))
      ? next
      : new Map(entries)) as T;
  }
  if (next instanceof Set) {
    if (!(prior instanceof Set)) return next;
    const priorMembers = [...prior];
    const members = [...next].map((child, index) => share(priorMembers[index], child));
    if (
      priorMembers.length === members.length &&
      members.every((child, index) => child === priorMembers[index])
    )
      return prior as T;
    return (members.every((child) => next.has(child)) ? next : new Set(members)) as T;
  }
  if (!plain(next) || !plain(prior) || Array.isArray(prior) || prior instanceof Map
    || prior instanceof Set)
    return next;
  const before = prior as Record<string, unknown>;
  const after = next as Record<string, unknown>;
  const keys = Object.keys(after);
  const children = keys.map((key) =>
    Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key]);
  if (
    keys.length === Object.keys(before).length &&
    keys.every((key, index) => Object.hasOwn(before, key) && children[index] === before[key])
  )
    return prior as T;
  if (keys.every((key, index) => children[index] === after[key])) return next;
  const copy: Record<string, unknown> = Object.getPrototypeOf(next) === null
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
  return copy as T;
}

export function createApplicationPublisher<S extends ApplicationSnapshot>(initial: S) {
  const root = signal(immutable(initial));
  return Object.freeze({
    read: (): Immutable<S> => root.value,
    publish(candidate: S): Immutable<S> {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select<T>(derive: (snapshot: Immutable<S>) => T): SnapshotReading<Immutable<T>> {
      let prior: unknown;
      const selected = computed(
        () => (prior = immutable(share(prior, derive(root.value)))),
      );
      return Object.freeze({
        read: (): Immutable<T> => selected.value,
        subscribe: (listener: (value: Immutable<T>) => void) =>
          selected.subscribe(listener),
      });
    },
  });
}
