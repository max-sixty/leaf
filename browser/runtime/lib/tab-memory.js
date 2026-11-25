/* What a widget keeps for this tab, such as the view it shows or a setting the user
   chose: `sessionStorage`, under the page's scope where the root states one
   (`data-lf-page-scope`, which Leaf writes), so two pages of one origin keep their own.
   A document that refuses storage, as a live sample's opaque frame does, keeps nothing:
   `get` answers null and `set` does nothing. A null value forgets the key. */
const scoped = (/** @type {string} */ key) =>
  (document.documentElement.dataset.lfPageScope ?? "") + key;

export const tabMemory = {
  /** @param {string} key @returns {string | null} */
  get(key) {
    try {
      return sessionStorage.getItem(scoped(key));
    } catch {
      return null;
    }
  },
  /** @param {string} key @param {string | null} value */
  set(key, value) {
    try {
      if (value === null) sessionStorage.removeItem(scoped(key));
      else sessionStorage.setItem(scoped(key), value);
    } catch {
      // Storage refused: the widget keeps nothing for the tab.
    }
  },
};
