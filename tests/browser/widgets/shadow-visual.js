/* A clipped shadow-root visual whose drawn surface extends past its host.
 * The fixture preserves separate SVG and host bounds for visual-aim checks. */
import { once, registerVisualParts, shadowStage } from "/runtime/widget-api.js";

customElements.define(
  "lf-test-shadow-visual",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      Object.assign(this.style, {
        display: "block",
        width: "100px",
        height: "60px",
        overflow: "hidden",
      });
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 220 60");
      svg.setAttribute("width", "220");
      svg.setAttribute("height", "60");
      svg.style.cssText = "display: block; max-width: none";
      svg.innerHTML = `<rect id="wide-surface" x="10" y="10" width="200" height="40"
      rx="8" fill="#dcfce7" stroke="#16a34a" stroke-width="2"></rect>`;
      shadowStage(this, [svg]);
      const surface = this.shadowRoot.querySelector("#wide-surface");
      this.visualRegistration = registerVisualParts(this, () => [
        { id: "wide", element: surface, label: "Clipped wide surface" },
      ]);
    }
  },
);
