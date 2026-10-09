/* A registered visual with staged reveals and explicit render-gate faults.
 * Every case shares the drawing and inventory; configuration changes only the
 * initial part visibility, opening fill, or a deliberately invalid surface. */
import { once, registerVisualParts } from "/runtime/widget-api.js";

export function defineVisualFixture({
  staged = false,
  openingFill = "#dbeafe",
  repairFillOnReveal = false,
  outsideSurfaceFor = null,
} = {}) {
  customElements.define(
    "lf-test-visual",
    class extends HTMLElement {
      connectedCallback() {
        if (!once(this)) return;
        this.innerHTML = `<svg viewBox="0 0 240 120" width="240" height="120">
      <g id="outer">
        <rect id="outer-surface" x="10" y="10" width="220" height="100" rx="8"
              fill="${openingFill}" stroke="#2563eb" stroke-width="2"></rect>
        <line id="outer-decoration" x1="25" y1="36" x2="215" y2="36"
              stroke="#2563eb" stroke-width="2"></line>
        <g id="inner">
          <path d="M120 44 L158 76 L120 104 L82 76 Z"
                fill="#fef3c7"></path>
          <line x1="100" y1="76" x2="140" y2="76"
                stroke="#d97706" stroke-width="2"></line>
        </g>
      </g>
    </svg>
    <div id="html" style="width: 220px; padding: 8px;">
      <span id="html-surface" style="display: inline-block; border-radius: 12px; padding: 4px 10px; background: #dbeafe;">HTML surface</span>
      <span id="html-decoration"> · decoration</span>
    </div>`;
        const outer = this.querySelector("#outer");
        const inner = this.querySelector("#inner");
        const outerSurface = this.querySelector("#outer-surface");
        const html = this.querySelector("#html");
        const htmlSurface = this.querySelector("#html-surface");
        this.parts = [
          {
            id: "outer",
            element: outer,
            surface:
              this.id === outsideSurfaceFor
                ? document.querySelector("#title")
                : outerSurface,
            label: "Outer store",
          },
          { id: "inner", element: inner, label: "Inner decision" },
          { id: "html", element: html, surface: htmlSurface, label: "HTML target" },
        ];
        if (staged) inner.style.display = "none";
        this.visualRegistration = registerVisualParts(
          this,
          () =>
            staged
              ? this.parts.filter(
                  (part) => part.id !== "inner" || inner.style.display !== "none",
                )
              : this.parts,
          staged
            ? {
                reveal: (id) => {
                  if (id !== "inner") return;
                  inner.style.display = "";
                  if (repairFillOnReveal) outerSurface.setAttribute("fill", "#dbeafe");
                  this.visualRegistration.update();
                },
              }
            : {},
        );
        this.redraw = () => {
          outerSurface.setAttribute("rx", "28");
          this.visualRegistration.update();
        };
      }
    },
  );
}
