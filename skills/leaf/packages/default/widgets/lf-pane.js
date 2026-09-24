/* A pane is one named reading region: an optional header, exactly one body element, and
   an optional footer, all authored. The theme lays them out and decides whether the body
   scrolls; this module names the region and registers its body, so reading keys, travel
   and continuity find the place whichever box scrolls it. A revision that replaces the
   body re-registers the region under the same id. */
import { once, registerReadingRegion } from "/runtime/widget-api.js";

const bodyOf = (pane) =>
  [...pane.children].find((child) => !child.matches("header, footer")) ?? null;

customElements.define(
  "lf-pane",
  class extends HTMLElement {
    #body = null;
    #stop = null;
    #children = new MutationObserver(() => this.#register());

    connectedCallback() {
      this.setAttribute("role", "region");
      this.setAttribute("aria-label", this.getAttribute("label"));
      this.#register();
      this.#children.observe(this, { childList: true });
      once(this);
    }

    disconnectedCallback() {
      this.#children.disconnect();
      this.#stop?.();
      this.#stop = null;
      this.#body = null;
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
