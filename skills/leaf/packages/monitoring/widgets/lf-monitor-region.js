/* One monitoring zone is a normal reading region; its zone attribute belongs only to
   the package grid's placement and does not create another scroll-state owner. */
import {
  arrangeReadingElement,
  once,
  registerArrangedElement,
} from "/runtime/widget-api.js";

const direct = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

customElements.define(
  "lf-monitor-region",
  class extends HTMLElement {
    #arrangement = null;

    connectedCallback() {
      if (!once(this)) {
        const content = this.querySelector(":scope > .lf-pane-content");
        const body = this.querySelector(":scope > .lf-pane-content > .lf-pane-body");
        this.#arrangement = registerArrangedElement({
          owner: this,
          content,
          body,
          regions: [{ id: this.id, host: this, body }],
        });
        return;
      }
      const header = direct(this, "header");
      const footer = direct(this, "footer");
      this.setAttribute("role", "region");
      this.setAttribute("aria-label", this.getAttribute("label"));
      this.#arrangement = arrangeReadingElement({
        owner: this,
        kind: "pane",
        header,
        footer,
        regions: [{ id: this.id, host: this }],
      }).arrangement;
    }

    disconnectedCallback() {
      this.#arrangement?.cleanup();
      this.#arrangement = null;
    }
  },
);
