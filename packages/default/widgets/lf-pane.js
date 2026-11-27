/* A pane is one named reading region: an optional header, exactly one body element, and
   an optional footer, all authored. The theme lays them out and decides whether the body
   scrolls; this module marks the body as the region and itself as the region's host
   (module-scroll-and-motion.md, "Reading regions"), so reading keys, travel and
   continuity find the place whichever box scrolls it. The module reads only which child
   is which, so a revision edits inside them in place (`lfPatch`) and the browser's
   scroll anchoring keeps the reader's place in the body, which a pane replaced whole
   would lose. A revision that replaces the body marks the new one, which takes the
   region. */
import { keeps } from "/runtime/lib/keeps.js";

customElements.define(
  "lf-pane",
  class extends HTMLElement {
    static lfPatch = "members";
    #children = new MutationObserver(() => this.#mark());

    constructor() {
      super();
      this.#children.observe(this, { childList: true });
    }

    connectedCallback() {
      keeps(this, "role", "region");
      keeps(this, "aria-label", this.getAttribute("label"));
      keeps(this, "data-lf-scroll-host", "body");
      this.#mark();
    }

    #mark() {
      const body = [...this.children].find((child) => !child.matches("header, footer"));
      keeps(body, "data-lf-scroll", "body");
    }
  },
);
