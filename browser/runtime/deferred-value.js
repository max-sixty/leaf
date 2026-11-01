/* A deferred read belongs to the exact manifest value its host delivered. Keep the
   loader with that value's lifetime rather than importing a page's data services
   into every widget that can display a manifest. Leaf attaches its revision-bound
   loader in data.js; importing or drawing an ordinary value needs no data owner. */
/** @type {WeakMap<object, (key: string) => Promise<unknown>>} */
const loaders = new WeakMap();

/** @param {object} value @param {(key: string) => Promise<unknown>} load */
export function attachDeferredLoader(value, load) {
  loaders.set(value, load);
}

/** @param {object} value @param {string} key */
export async function loadDeferred(value, key) {
  const load = loaders.get(value);
  if (!load)
    throw new Error(`loadDeferred(${key}) needs a source value Leaf delivered`);
  return load(key);
}
