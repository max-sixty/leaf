/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * freezes them, and replaces one private signal synchronously. This module does
 * not derive activity, reconcile receipts, or perform transport and rendering.
 */
import { computed, signal } from "@preact/signals-core";

export type Immutable<T> = T extends object
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

function immutable<T>(value: T): Immutable<T> {
  if (value !== null && typeof value === "object") {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
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
