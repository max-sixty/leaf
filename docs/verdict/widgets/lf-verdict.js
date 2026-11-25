import { html, render } from "/vendor/lit.js";

const LABELS = { ship: "Ship", hold: "Hold" };

customElements.define(
  "lf-verdict",
  class extends HTMLElement {
    set state({ decide }) {
      const button = ([value, label]) =>
        html`<button
          type="button"
          aria-pressed=${decide.value === value}
          aria-disabled=${!decide.available}
          @click=${() => this.press(value)}
        >
          ${label}
        </button>`;
      render(Object.entries(LABELS).map(button), this);
    }

    press(value) {
      const action = { verb: "decide", detail: { value } };
      this.dispatchEvent(new CustomEvent("lf-action", { detail: action }));
    }
  },
);
