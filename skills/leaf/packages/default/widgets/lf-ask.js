/* An Ask with exactly one heading and one answer surface exposes those as shared
   furniture and content slots. Its body participates in bounded allocation when that
   body registers an arrangement; other Asks retain ordinary authored document flow. */
import {
  arrangeReadingElement,
  once,
  registerArrangedElement,
} from "/runtime/widget-api.js";

const heading = (node) => node.matches("h1, h2, h3, h4, h5, h6");

customElements.define(
  "lf-ask",
  class extends HTMLElement {
    #arrangement = null;

    connectedCallback() {
      if (!once(this)) {
        const content = this.querySelector(":scope > .lf-arranged-content");
        if (content)
          this.#arrangement = registerArrangedElement({ owner: this, content });
        return;
      }
      const children = [...this.children];
      if (children.length !== 2 || !heading(children[0])) return;
      this.#arrangement = arrangeReadingElement({
        owner: this,
        kind: "workspace",
        header: children[0],
      }).arrangement;
    }

    disconnectedCallback() {
      this.#arrangement?.cleanup();
      this.#arrangement = null;
    }
  },
);
