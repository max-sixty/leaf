/* A visual part inside a scroller of the widget's own shadow stage, whose content fits
 * until the test grows it. */
import { once, registerVisualParts, shadowStage } from "/runtime/widget-api.js";

customElements.define(
  "lf-test-shadow-scroller",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.style.display = "block";
      const port = document.createElement("div");
      port.className = "port";
      port.style.cssText = "height: 160px; overflow-y: auto";
      const content = document.createElement("div");
      content.className = "content";
      content.style.cssText = "height: 100px; padding-top: 20px";
      const part = document.createElement("div");
      part.className = "part";
      part.style.cssText = "width: 120px; height: 60px; background: #dcfce7";
      content.append(part);
      port.append(content);
      shadowStage(this, [port]);
      this.visualRegistration = registerVisualParts(this, () => [
        { id: "part", element: part, label: "A part in a scroller" },
      ]);
    }
  },
);
