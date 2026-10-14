/* An anonymous report consumer keeps clock and report identity tests independent
 * of the Atlas example's composition. */
import {
  ago,
  html,
  keeps,
  LeafElement,
  noChange,
  quietSince,
  saidAt,
  reportSequence,
  reportsReady,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-test-worker",
  class extends LeafElement {
    setup() {
      this.line = document.createElement("div");
      this.line.dataset.lfGen = "1";
      this.append(this.line);
    }
    createRenderRoot() {
      return this.line;
    }
    render() {
      const state = this.state.state.value;
      keeps(this, "state", state);
      if (!reportsReady(this)) return noChange;
      const reports = reportSequence(this).filter(
        (row) => row.source === "report" && row.action === "state",
      );
      const heard = reports.at(-1)?.ts ?? saidAt(this);
      const current = reports.findLast((row) => row.disposition === "effective");
      return html`<span class="lf-state">${state}</span>
        ${current?.text ? html`<span class="lf-doing">${current.text}</span>` : ""}
        ${["working", "waiting"].includes(state) && quietSince(heard) ? html`<span class="lf-cold">quiet</span>` : ""}
        <span class="lf-heard">last heard ${ago(heard)}</span>`;
    }
  },
);
