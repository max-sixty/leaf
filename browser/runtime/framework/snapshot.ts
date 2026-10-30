/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * shares every subtree equal to the current reading's, freezes them, and replaces one
 * private signal synchronously. Producers leave Map/Set values extensible so this
 * owner can secure their mutation methods in place. This module does not derive
 * activity, reconcile receipts, or perform transport and rendering.
 *
 * Sharing is what makes identity mean "unchanged": a fold rebuilds its whole result on
 * every publication, and a subtree whose contents did not move comes back as the
 * object the last reading held. So a selection is a `computed` compared by identity,
 * and a reader subscribed to one part of the reading hears only that part change. A
 * selection shares its own derived value against its previous one by the same rule.
 * Native Preact computed values and effects own dependency tracking. Derivations read
 * their supplied immutable root, and subscriber callbacks run untracked so notifying
 * a consumer cannot make its reads dependencies of the publisher.
 */
import {
  computed,
  signal,
  untracked as signalUntracked,
} from "/vendor/signals-core.js";

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
  subscribe(listener: (value: T, round?: object) => unknown): () => void;
}

export { signalUntracked as untracked };

// Publications take ownership of mutable producer values; previously secured
// subtrees retain identity and need no further traversal.
const secured = new WeakSet<object>();
function immutable<T>(value: T): Immutable<T> {
  if (value !== null && typeof value === "object" && !secured.has(value)) {
    if (value instanceof Map) {
      for (const [key, child] of value) {
        immutable(key);
        immutable(child);
      }
    } else if (value instanceof Set) {
      for (const child of value) immutable(child);
    } else {
      for (const child of Object.values(value)) immutable(child);
    }
    if (value instanceof Map || value instanceof Set) {
      const refuse = () => {
        throw new TypeError("Application snapshots are read-only");
      };
      for (const name of value instanceof Map
        ? ["set", "delete", "clear"]
        : ["add", "delete", "clear"])
        Object.defineProperty(value, name, { value: refuse });
    }
    Object.freeze(value);
    secured.add(value);
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
    return (
      children.every((child, index) => child === next[index]) ? next : children
    ) as T;
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(
      ([key, child]) =>
        [key, prior.has(key) ? share(prior.get(key), child) : child] as const,
    );
    if (
      priorKeys.length === entries.length &&
      entries.every(
        ([key, child], index) => key === priorKeys[index] && child === prior.get(key),
      )
    )
      return prior as T;
    return (
      entries.every(([key, child]) => child === next.get(key)) ? next : new Map(entries)
    ) as T;
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
  if (
    !plain(next) ||
    !plain(prior) ||
    Array.isArray(prior) ||
    prior instanceof Map ||
    prior instanceof Set
  )
    return next;
  const before = prior as Record<string, unknown>;
  const after = next as Record<string, unknown>;
  const keys = Object.keys(after);
  const children = keys.map((key) =>
    Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key],
  );
  if (
    keys.length === Object.keys(before).length &&
    keys.every(
      (key, index) => Object.hasOwn(before, key) && children[index] === before[key],
    )
  )
    return prior as T;
  if (keys.every((key, index) => children[index] === after[key])) return next;
  const copy: Record<string, unknown> =
    Object.getPrototypeOf(next) === null ? Object.create(null) : {};
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
    read: () => root.value,
    // The root without subscribing or collecting, for the owner computing what it
    // publishes next.
    peek: () => root.peek(),
    publish(candidate: S) {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select<T>(derive: (snapshot: Immutable<S>) => T): SnapshotReading<Immutable<T>> {
      let prior: unknown;
      const selected = computed(() => {
        const value = root.value;
        return signalUntracked(() => (prior = immutable(share(prior, derive(value)))));
      });
      const reading: SnapshotReading<Immutable<T>> = Object.freeze({
        read: () => selected.value,
        subscribe: (listener: (value: Immutable<T>) => void) =>
          selected.subscribe((value) => signalUntracked(() => listener(value))),
      });
      return reading;
    },
  });
}
