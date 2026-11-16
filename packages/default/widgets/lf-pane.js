/* A pane is one named reading region: an optional header, exactly one body element, and
   an optional footer, all authored. The theme lays them out and decides whether the body
   scrolls; this module names the region by the heading in its header, as any element
   is named (`addressableName`), where its author gave it no `aria-label` instead, and
   registers its body, so reading keys, travel
   and continuity find the place whichever box scrolls it. The module reads only which
   child is which, so a revision edits inside them in place (`x-patch: members`) and the
   browser's scroll anchoring keeps the reader's place in the body, which a pane
   replaced whole would lose. A revision that replaces the body re-registers the region
   under the same id. */
import {
  addressableName,
  keeps,
  once,
  registerReadingRegion,
  whileConnected,
} from "/runtime/widget-api.js";

/** @param {HTMLElement} pane */
const bodyOf = (pane) =>
  [...pane.children].find((child) => !child.matches("header, footer")) ?? null;

customElements.define(
  "lf-pane",
  class extends HTMLElement {
    /** @type {Element | null} */
    #body = null;
    /** @type {(() => void) | null} */
    #stop = null;
    #children = new MutationObserver(() => this.#register());
    // The `aria-label` this module wrote, told apart from one the author gave.
    /** @type {string | null} */
    #named = null;

    connectedCallback() {
      keeps(this, "role", "region");
      const label = this.getAttribute("aria-label");
      if (label === null || label === this.#named) {
        this.#named = addressableName(this) || null;
        keeps(this, "aria-label", this.#named);
      }
      if (!once(this)) return;
      whileConnected(this, () => {
        this.#register();
        this.#children.observe(this, { childList: true });
        return () => {
          this.#children.disconnect();
          this.#stop?.();
          this.#stop = null;
          this.#body = null;
        };
      });
    }

    #register() {
      const body = bodyOf(this);
      if (body === this.#body) return;
      this.#stop?.();
      this.#body = body;
      this.#stop = body
        ? registerReadingRegion({ id: this.id, host: this, body })
        : null;
    }
  },
);
