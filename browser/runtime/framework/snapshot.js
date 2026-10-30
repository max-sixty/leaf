/* @noformat Generated TypeScript; edit the .ts owner. */
import {
  computed,
  signal,
  untracked as signalUntracked
} from "/vendor/signals-core.js";
const secured = /* @__PURE__ */ new WeakSet();
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
      for (const name of value instanceof Map ? ["set", "delete", "clear"] : ["add", "delete", "clear"])
        Object.defineProperty(value, name, { value: refuse });
    }
    Object.freeze(value);
    secured.add(value);
  }
  return value;
}
const plain = (value) => {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
};
function share(prior, next) {
  if (Object.is(prior, next)) return next;
  if (prior === null || next === null || typeof prior !== "object" || typeof next !== "object")
    return next;
  if (Array.isArray(next)) {
    if (!Array.isArray(prior)) return next;
    const children2 = next.map((child, index) => share(prior[index], child));
    if (prior.length === next.length && children2.every((child, index) => child === prior[index]))
      return prior;
    return children2.every((child, index) => child === next[index]) ? next : children2;
  }
  if (next instanceof Map) {
    if (!(prior instanceof Map)) return next;
    const priorKeys = [...prior.keys()];
    const entries = [...next].map(
      ([key, child]) => [key, prior.has(key) ? share(prior.get(key), child) : child]
    );
    if (priorKeys.length === entries.length && entries.every(
      ([key, child], index) => key === priorKeys[index] && child === prior.get(key)
    ))
      return prior;
    return entries.every(([key, child]) => child === next.get(key)) ? next : new Map(entries);
  }
  if (next instanceof Set) {
    if (!(prior instanceof Set)) return next;
    const priorMembers = [...prior];
    const members = [...next].map((child, index) => share(priorMembers[index], child));
    if (priorMembers.length === members.length && members.every((child, index) => child === priorMembers[index]))
      return prior;
    return members.every((child) => next.has(child)) ? next : new Set(members);
  }
  if (!plain(next) || !plain(prior) || Array.isArray(prior) || prior instanceof Map || prior instanceof Set)
    return next;
  const before = prior;
  const after = next;
  const keys = Object.keys(after);
  const children = keys.map(
    (key) => Object.hasOwn(before, key) ? share(before[key], after[key]) : after[key]
  );
  if (keys.length === Object.keys(before).length && keys.every(
    (key, index) => Object.hasOwn(before, key) && children[index] === before[key]
  ))
    return prior;
  if (keys.every((key, index) => children[index] === after[key])) return next;
  const copy = Object.getPrototypeOf(next) === null ? /* @__PURE__ */ Object.create(null) : {};
  keys.forEach(
    (key, index) => Object.defineProperty(copy, key, {
      value: children[index],
      writable: true,
      enumerable: true,
      configurable: true
    })
  );
  return copy;
}
function createApplicationPublisher(initial) {
  const root = signal(immutable(initial));
  return Object.freeze({
    read: () => root.value,
    // The root without subscribing or collecting, for the owner computing what it
    // publishes next.
    peek: () => root.peek(),
    publish(candidate) {
      root.value = immutable(share(root.peek(), candidate));
      return root.peek();
    },
    select(derive) {
      let prior;
      const selected = computed(() => {
        const value = root.value;
        return signalUntracked(() => prior = immutable(share(prior, derive(value))));
      });
      const reading = Object.freeze({
        read: () => selected.value,
        subscribe: (listener) => selected.subscribe((value) => signalUntracked(() => listener(value)))
      });
      return reading;
    }
  });
}
export {
  createApplicationPublisher,
  share,
  signalUntracked as untracked
};
