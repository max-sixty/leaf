/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * freezes them, and replaces one private signal synchronously. This module does
 * not derive activity, reconcile receipts, or perform transport and rendering.
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

export interface ApplicationSnapshot {
  readonly document: unknown;
  readonly authoritative: unknown;
  readonly unresolved: readonly unknown[];
  readonly effective: unknown;
  readonly semanticEpoch: number;
}

export interface SnapshotReading<T> {
  read(): T;
  subscribe(listener: (value: T) => void): () => void;
}

// Object.freeze says nothing about descendants or Map/Set entries. Only values this
// owner has secured can skip traversal when a publication reuses a standing subtree.
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

export function createApplicationPublisher<S extends ApplicationSnapshot>(initial: S) {
  const root = signal(immutable(initial));
  return Object.freeze({
    read: (): Immutable<S> => root.value,
    publish(candidate: S): Immutable<S> {
      root.value = immutable(candidate);
      return root.peek();
    },
    select<T>(derive: (snapshot: Immutable<S>) => T): SnapshotReading<Immutable<T>> {
      const selected = computed(() => immutable(derive(root.value)));
      return Object.freeze({
        read: (): Immutable<T> => selected.value,
        subscribe: (listener: (value: Immutable<T>) => void) =>
          selected.subscribe(listener),
      });
    },
  });
}
