/* What this window keeps for the page until the tab closes. storage.js says what belongs
   here rather than in the page's other stores; the prepaint opens it, scoped to the page,
   before the first paint, since it reads the tab's memory then too (prepaint.js).

   It is the runtime's. A widget keeps its own tab state through the library
   (lib/tab-memory.js), over the same `sessionStorage` under the same page scope. A
   document Leaf did not compose has no prepaint and so no store: each read answers null
   and each write is refused, as a store the browser has switched off answers. */

/** @type {LeafStore} */
export const tabStore = window.lfStorage?.tabStore ?? {
  read: () => ({ available: false, value: null }),
  get: () => null,
  set: () => false,
  where: (key) => ({ store: "session", key }),
  keys: () => [],
};
