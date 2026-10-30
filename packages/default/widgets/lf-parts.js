/* lf-parts: a page's parts, each with a Layout of its own, one on screen at a time. The
 * tab set's module draws and runs them (lf-tabs.js, `TabSet`), which says how they differ
 * from a tab set. */
import { TabSet } from "./lf-tabs.js";

customElements.define(
  "lf-parts",
  class extends TabSet {
    static parts = true;
  },
);
