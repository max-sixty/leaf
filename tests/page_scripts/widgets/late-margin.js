/* A project widget that claims margin room only after its held request returns.
 * The Python case owns that response, so arrival is ordered rather than timed. */
import { once } from "/runtime/widget-api.js";

customElements.define(
  "lf-callout",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      fetch("/margin-width").then(() =>
        document.body.style.setProperty("--lf-taken-r", "160px"),
      );
    }
  },
);
