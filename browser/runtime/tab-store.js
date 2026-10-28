/* What this window keeps for the page until the tab closes. storage.js says what belongs
   here rather than in the page's other stores; the prepaint opens it, scoped to the page,
   before the first paint, since it reads the tab's memory then too (prepaint.js).

   It loads in any document (portable-api.js). A document Leaf did not compose has no
   prepaint and so no store, and a widget there keeps nothing: each read answers null and
   each write is refused, as a store the browser has switched off answers. */
/** @type {LeafStore} */
export const tabStore = document.documentElement.lfStorage?.tabStore ?? {
  read: () => ({ available: false, value: null }),
  get: () => null,
  set: () => false,
  where: (key) => ({ store: "session", key }),
  keys: () => [],
};
