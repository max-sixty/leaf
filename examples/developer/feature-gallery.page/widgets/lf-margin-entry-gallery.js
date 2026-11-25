/* The exhibit and its contributed margin entry share one live Lit view. */
import { render } from "/vendor/lit.js";
import { createView } from "../margin-entry-gallery-view.js";
import { registerContribution, whileConnected } from "/runtime/widget-api.js";
import { once } from "/runtime/lib/once.js";

customElements.define(
  "lf-margin-entry-gallery",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      const initial = createView(this);
      render(initial.render(), this);
      whileConnected(this, () => {
        const projection = this.#registerProjection(initial.result);
        return () => projection.unregister();
      });
    }

    #registerProjection(result) {
      const projection = registerContribution({
        key: `gallery-projection:${this.id}`,
        target: () => this,
        read: () => ({
          subject: "Margin entry projection",
          entries: [
            {
              key: "inspect-projection",
              icon: "question",
              label: "Inspect projection",
              context: "Compact face · full row",
              behavior: "disclosure",
              rank: "reading",
              relation: { kind: "element", id: result.id, expanded: !result.hidden },
            },
          ],
          readings: [],
        }),
        activate: () => {
          result.hidden = !result.hidden;
          projection.update({ immediate: true });
        },
      });
      return projection;
    }
  },
);
