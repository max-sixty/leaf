/* lf-trend: a line per series of the table inside it, on one axis, with the table's
 * exact values in a disclosure below. The table is the widget's authored content, slotted
 * into the disclosure, so a reader who opens it reads and comments on the page's own
 * cells. */
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { html, svg } from "/vendor/lit.js";

const WIDTH = 640;
const HEIGHT = 240;
const PAD = 32;
// Room right of the last point for each series' name.
const NAMES = 80;
const COLORS = ["#2f6f9f", "#b5532a", "#4f7d3a", "#7a4f9a"];

customElements.define(
  "lf-trend",
  class extends LeafElement {
    static shadow = true;
    render() {
      const [head, ...rows] = [...this.querySelectorAll("tr")].map((row) =>
        [...row.cells].map((cell) => cell.textContent.trim()),
      );
      const names = head ? head.slice(1) : [];
      const values = rows.map((row) => row.slice(1).map(Number));
      const all = values.flat().filter(Number.isFinite);
      const low = Math.min(0, ...all);
      const high = Math.max(1, ...all);
      const x = (i) => PAD + (i * (WIDTH - PAD - NAMES)) / Math.max(1, rows.length - 1);
      const y = (v) => HEIGHT - PAD - ((v - low) * (HEIGHT - 2 * PAD)) / (high - low);
      const label = this.getAttribute("label") ?? "";
      return html`
        <figure style="margin: 0">
          <svg
            viewBox="0 0 ${WIDTH} ${HEIGHT}"
            role="img"
            aria-label=${label}
            style="width: 100%; height: ${HEIGHT}px; display: block"
          >
            ${rows.map(
              (row, i) =>
                svg`<text x=${x(i)} y=${HEIGHT - 8} font-size="12" text-anchor="middle" fill="currentColor">${row[0]}</text>`,
            )}
            ${names.map(
              (name, s) =>
                svg`<polyline fill="none" stroke=${COLORS[s % COLORS.length]} stroke-width="2.5" points=${values.map((row, i) => `${x(i)},${y(row[s])}`).join(" ")}></polyline>
                <text x=${WIDTH - NAMES + 8} y=${y(values.at(-1)?.[s] ?? 0) + 4} font-size="12" fill=${COLORS[s % COLORS.length]}>${name}</text>`,
            )}
          </svg>
          <figcaption style="height: 20px; line-height: 20px">${label}</figcaption>
        </figure>
        <details>
          <summary style="height: 24px; line-height: 24px">Values</summary>
          <slot></slot>
        </details>
      `;
    }
  },
);
