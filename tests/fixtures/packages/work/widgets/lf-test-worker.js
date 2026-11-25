/* An anonymous report consumer keeps clock and report identity tests independent
 * of the Atlas example's composition. */
import { html, noChange } from "/vendor/lit.js";
import { readReports, readWork } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";
customElements.define(
  "lf-test-worker",
  class extends LeafElement {
    setup() {
      this.line = document.createElement("div");
      keeps(this.line, "data-lf-gen", "1");
      this.append(this.line);
    }
    createRenderRoot() {
      return this.line;
    }
    render() {
      const state = this.state.state.value;
      keeps(this, "state", state);
      const { phase, reports } = readReports(this);
      if (phase !== "ready") return noChange;
      const current = reports.findLast(
        (row) =>
          row.source === "report" &&
          row.action === "state" &&
          row.disposition === "effective",
      );
      const { heard, quiet } = readWork(this).workers.find(
        (row) => row.element === this,
      );
      return html`<span class="lf-state">${state}</span>
        ${current?.text ? html`<span class="lf-doing">${current.text}</span>` : ""}
        ${quiet ? html`<span class="lf-cold">quiet</span>` : ""}
        <span class="lf-heard">last heard <lf-age datetime=${heard}></lf-age></span>`;
    }
  },
);
