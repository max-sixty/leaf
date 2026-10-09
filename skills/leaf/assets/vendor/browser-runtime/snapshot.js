/**
 * One immutable snapshot publication primitive, independent of Leaf's folds.
 *
 * The application owner prepares complete, validated serializable candidates and
 * assigns their semantic epochs. Publication takes ownership of those values,
 * freezes them, and replaces one private signal synchronously. This module does
 * not derive activity, reconcile receipts, or perform transport and rendering.
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

export function createApplicationPublisher                               (initial   ) {
  const root = signal(immutable(initial));
  return Object.freeze({
    read: ()               => root.value,
    publish(candidate   )               {
      root.value = immutable(candidate);
      return root.peek();
    },
    select   (derive                               )                                {
      const selected = computed(() => immutable(derive(root.value)));
      return Object.freeze({
        read: ()               => selected.value,
        subscribe: (listener                               ) =>
          selected.subscribe(listener),
      });
    },
  });
}
// Generated from build/browser/snapshot.ts by npm run build:browser.
