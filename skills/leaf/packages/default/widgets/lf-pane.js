/* A pane is one stable reading region. Its host includes direct furniture so focus in
   the header or footer still selects the pane; only its generated body scrolls. */
import {
  arrangeReadingElement,
  once,
  registerArrangedElement,
  relabel,
} from "/runtime/widget-api.js";

const direct = (owner, tag) =>
  [...owner.children].find((child) => child.tagName === tag.toUpperCase()) ?? null;

customElements.define(
  "lf-pane",
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
      let header = direct(this, "header");
      const footer = direct(this, "footer");
      if (!header) {
        header = document.createElement("header");
        header.dataset.lfGen = "1";
        const label = document.createElement("span");
        relabel(label, this.getAttribute("label"), { says: true });
        header.append(label);
      }
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
