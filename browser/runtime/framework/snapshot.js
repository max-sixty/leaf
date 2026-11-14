// @ts-check
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
 * Sharing is what makes identity mean "unchanged": a subtree whose contents did not
 * move comes back as the object the last reading held. A fold hands back what it made
 * last time for a step whose inputs held still (kept.js), and sharing a fold's result
 * (`shareFold`) answers such a subtree from the last time it shared it, so a
 * publication costs what it changed rather than what the page holds. So a selection is a `computed` compared by
 * identity, and a reader subscribed to one part of the reading hears only that part
 * change. A selection shares its own derived value against its previous one by the
 * same rule, and one derived from another selection (`select`'s `from`) is derived
 * again only when that one moves. Native Preact computed values and effects own
 * dependency tracking. Derivations read their supplied immutable root, and subscriber
 * callbacks run untracked so notifying a consumer cannot make its reads dependencies
 * of the publisher.
 */
import {
  computed,
  signal,
  untracked as signalUntracked,
} from "/vendor/signals-core.js";

/**
 * @template T
 * @typedef {T extends ReadonlyMap<infer K, infer V>
 *   ? ReadonlyMap<Immutable<K>, Immutable<V>>
 *   : T extends ReadonlySet<infer V>
 *     ? ReadonlySet<Immutable<V>>
 *     : T extends object
 *       ? { readonly [K in keyof T]: Immutable<T[K]> }
 *       : T} Immutable
 */

/**
 * @typedef {{
 *   readonly document: unknown;
 *   readonly authoritative: unknown;
 *   readonly unresolved: readonly unknown[];
 *   readonly effective: unknown;
 *   readonly semanticEpoch: number;
 * }} ApplicationSnapshot
 */

/**
 * @template T
 * @typedef {{
 *   read(): T;
 *   subscribe(listener: (value: T, round?: object) => unknown): () => void;
 * }} SnapshotReading
 */

export { signalUntracked as untracked };

// Publications take ownership of mutable producer values; previously secured
// subtrees retain identity and need no further traversal.
/** @type {WeakSet<object>} */
const secured = new WeakSet();
/** @template T @param {T} value @returns {Immutable<T>} */
function immutable(value) {
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
  return /** @type {Immutable<T>} */ (value);
}

/** @param {object} value */
const plain = (value) => {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};

// Give `object` its own data property `key`, defined rather than assigned: a JSON field
// named `__proto__` is an own property, and assigning it would set the object's
// prototype instead.
/** @param {Record<string, unknown>} object @param {string} key @param {unknown} value */
export const defineOwn = (object, key, value) =>
  Object.defineProperty(object, key, {
    value,
    writable: true,
    enumerable: true,
    configurable: true,
  });

/**
 * `next`, with every subtree deep-equal to the matching one in `prior` replaced by
 * `prior`'s. Plain objects, arrays, Maps and Sets compare by contents (a Map or Set by
 * its entries in order, an object by its keys in any order); anything else by identity.
 * An array's item that `prior`'s array holds at any index stays as it is.
 * Returns `prior` itself when the two are equal, and `next` itself when nothing in it
 * could be shared, so neither input is copied or mutated needlessly.
 *
 * @template T
 * @param {unknown} prior
 * @param {T} next
 * @returns {T}
 */
export const share = (prior, next) => shared(prior, next, null);

// What each subtree of a fold's result was last shared as, where that was another
// value: a subtree shared as itself was published as itself, so meeting it again it is
// that value.
/** @type {WeakMap<object, unknown>} */
const foldShared = new WeakMap();

/**
 * `share` for a fold's result, which hands back unchanged the subtrees it made before
 * from inputs that held still (kept.js). A subtree met again against the value it was
 * shared as is answered at once, without its contents being read: the fold owns the
 * subtree and never changes it, and the value it was shared as is frozen once
 * published. Only the application's fold may pass a value here.
 *
 * @template T
 * @param {unknown} prior
 * @param {T} next
 * @returns {T}
 */
export const shareFold = (prior, next) => shared(prior, next, foldShared);

/**
 * @template T
 * @param {unknown} prior
 * @param {T} next
 * @param {WeakMap<object, unknown> | null} kept what each subtree was last shared as
 * @returns {T}
 */
function shared(prior, next, kept) {
  if (Object.is(prior, next)) return next;
  if (
    prior === null ||
    next === null ||
    typeof prior !== "object" ||
    typeof next !== "object"
  )
    return next;
  if (kept?.get(next) === prior) return /** @type {T} */ (prior);
  const result = compared(prior, next, kept);
  if (kept && result !== next) kept.set(next, result);
  return result;
}

/**
 * `shared` for two objects not shared before.
 *
 * @template {object} T
 * @param {object} prior
 * @param {T} next
 * @param {WeakMap<object, unknown> | null} kept
 * @returns {T}
 */
function compared(prior, next, kept) {
  if (Array.isArray(next)) {
    if (!Array.isArray(prior)) return next;
    // An item the prior list holds anywhere is already shared, so a list that gained,
    // lost or reordered items compares each item that moved by identity, not contents.
    /** @type {Set<unknown> | undefined} */
    let held;
    const children = next.map((child, index) =>
      child !== prior[index] &&
      child !== null &&
      typeof child === "object" &&
      (held ??= new Set(prior)).has(child)
        ? child
        : shared(prior[index], child, kept),
    );
    if (
      prior.length === next.length &&
      children.every((child, index) => child === prior[index])
    )
      return /** @type {T} */ (prior);
    return /** @type {T} */ (
      children.every((child, index) => child === next[index]) ? next : children
    );
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(
      ([key, child]) =>
        /** @type {const} */ ([
          key,
          prior.has(key) ? shared(prior.get(key), child, kept) : child,
        ]),
    );
    if (
      priorKeys.length === entries.length &&
      entries.every(
        ([key, child], index) => key === priorKeys[index] && child === prior.get(key),
      )
    )
      return /** @type {T} */ (prior);
    return /** @type {T} */ (
      entries.every(([key, child]) => child === next.get(key)) ? next : new Map(entries)
    );
  }
  if (next instanceof Set) {
    if (!(prior instanceof Set)) return next;
    const priorMembers = [...prior];
    const members = [...next].map((child, index) =>
      shared(priorMembers[index], child, kept),
    );
    if (
      priorMembers.length === members.length &&
      members.every((child, index) => child === priorMembers[index])
    )
      return /** @type {T} */ (prior);
    return /** @type {T} */ (
      members.every((child) => next.has(child)) ? next : new Set(members)
    );
  }
  if (
    !plain(next) ||
    !plain(prior) ||
    Array.isArray(prior) ||
    prior instanceof Map ||
    prior instanceof Set
  )
    return next;
  const before = /** @type {Record<string, unknown>} */ (prior);
  const after = /** @type {Record<string, unknown>} */ (next);
  const keys = Object.keys(after);
  const children = keys.map((key) =>
    Object.hasOwn(before, key) ? shared(before[key], after[key], kept) : after[key],
  );
  if (
    keys.length === Object.keys(before).length &&
    keys.every(
      (key, index) => Object.hasOwn(before, key) && children[index] === before[key],
    )
  )
    return /** @type {T} */ (prior);
  if (keys.every((key, index) => children[index] === after[key])) return next;
  /** @type {Record<string, unknown>} */
  const copy =
    Object.getPrototypeOf(next) === null ? /* @__PURE__ */ Object.create(null) : {};
  keys.forEach((key, index) => defineOwn(copy, key, children[index]));
  return /** @type {T} */ (copy);
}

/** @template {ApplicationSnapshot} S @param {S} initial */
export function createApplicationPublisher(initial) {
  const root = signal(immutable(initial));
  return Object.freeze({
    /** @returns {Immutable<S>} */
    read: () => root.value,
    // The root without subscribing or collecting, for the owner computing what it
    // publishes next.
    /** @returns {Immutable<S>} */
    peek: () => root.peek(),
    /** @param {S} candidate @returns {Immutable<S>} */
    publish(candidate) {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    /**
     * A selection of the root, or of `from`, another selection, which it then reads in
     * the root's place, so it is derived again only when that one moves rather than on
     * every publication.
     *
     * @template T
     * @template [F=Immutable<S>]
     * @param {(snapshot: F) => T} derive
     * @param {SnapshotReading<F>} [from]
     * @returns {SnapshotReading<Immutable<T>>}
     */
    select(derive, from) {
      /** @type {unknown} */
      let prior;
      const selected = computed(() => {
        const value = from ? from.read() : /** @type {F} */ (root.value);
        return signalUntracked(() => (prior = immutable(share(prior, derive(value)))));
      });
      /** @type {SnapshotReading<Immutable<T>>} */
      const reading = Object.freeze({
        /** @returns {Immutable<T>} */
        read: () => selected.value,
        /** @param {(value: Immutable<T>) => void} listener */
        subscribe: (listener) =>
          selected.subscribe((value) => signalUntracked(() => listener(value))),
      });
      return reading;
    },
  });
}
