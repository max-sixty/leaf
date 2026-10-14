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
import { computed, signal } from "./signals-core.js";























// The readings a caller is collecting (`collectReads`), each with the first value it
// gave. A reading records itself when read, after its own derivation, whose reads of
// the root are the selection's rather than the caller's.
let collecting                                                = null;
function collected   (reading                    , read         )    {
  const outer = collecting;
  collecting = null;
  let value   ;
  try {
    value = read();
  } finally {
    collecting = outer;
  }
  if (outer && !outer.has(reading)) outer.set(reading, value);
  return value;
}

/**
 * Run `run`, collecting every selection of a publication it reads synchronously, with
 * the value it read. A watcher subscribes to exactly these, so it repaints when a part
 * its paint read moves and for nothing else.
 * Only reads of the publication count: a paint also reads and writes private signals,
 * such as where the user stands, and subscribing it to those would have a paint that
 * moves focus repaint itself. Reading the root whole inside `run` throws, since every
 * publication moves the root: a paint that read it would repaint on every publication,
 * however little of it the paint draws, so it reads its parts through selections. A
 * failure still returns what was read before it.
 */
export function collectReads   (
  run         ,
)                                                                                          {
  const outer = collecting;
  const reads = new Map                                   ();
  collecting = reads;
  try {
    return { reads, value: run() };
  } catch (error) {
    return { reads, error };
  } finally {
    collecting = outer;
  }
}

/**
 * Run `run` outside any collection. An owner nested in a collected run, such as a widget
 * a paint mounts, which connects and reads its own reading inside that paint, follows
 * what it reads itself; collecting those reads would have the paint repaint for every
 * nested owner's state, and throw where the owner reads the root whole.
 */
export function untracked   (run         )    {
  const outer = collecting;
  collecting = null;
  try {
    return run();
  } finally {
    collecting = outer;
  }
}

// Object.freeze says nothing about descendants or Map/Set entries. Only values this
// owner has secured can skip traversal when a publication reuses an existing subtree.
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
    read: ()               => {
      if (collecting)
        throw new Error(
          "a collected read took the whole publication; select the part it needs",
        );
      return root.value;
    },
    // The root without subscribing or collecting, for the owner computing what it
    // publishes next.
    peek: ()               => root.peek(),
    publish(candidate   )               {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select   (derive                               )                                {
      let prior         ;
      const selected = computed(
        () => (prior = immutable(share(prior, derive(root.value)))),
      );
      const reading                                = Object.freeze({
        read: ()               => collected(reading, () => selected.value),
        subscribe: (listener                               ) =>
          selected.subscribe(listener),
      });
      return reading;
    },
  });
}
// Generated from build/browser/snapshot.ts by build/browser/build.mjs.
