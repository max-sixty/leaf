/* Atlas owns roster composition. A worker's latest report draws as it arrives, while
 * identity and state come from the public projection. */
import { html, noChange } from "/vendor/lit.js";
import { readReports, readWork } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
customElements.define(
  "lf-atlas-worker",
  class extends LeafElement {
    setup() {
      if (!this.querySelector("details")) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.append(
          this.querySelector(":scope > strong"),
          Object.assign(document.createElement("span"), {
            className: "atlas-worker-state",
            role: "status",
          }),
        );
        const body = document.createElement("div");
        body.className = "atlas-worker-body";
        body.append(
          Object.assign(document.createElement("p"), {
            className: "atlas-worker-report",
          }),
          ...this.childNodes,
        );
        details.append(summary, body);
        this.append(details);
      }
      // The worker's state word and its latest report are this widget's words.
      for (const words of [
        this.querySelector(".atlas-worker-state"),
        this.querySelector(".atlas-worker-report"),
      ]) {
        keeps(words, "data-lf-gen", "1");
        words.toggleAttribute("data-lf-said", true);
      }
    }
    createRenderRoot() {
      return this.querySelector(".atlas-worker-report");
    }
    render() {
      keeps(this, "state", this.state.state.value);
      const worker = readWork(this).workers.find((row) => row.element === this);
      keepsText(
        this.querySelector(".atlas-worker-state"),
        `${worker.state}${worker.quiet ? " · quiet" : ""}`,
      );
      const { phase, reports } = readReports(this);
      if (phase !== "ready") return noChange;
      const report = reports.findLast(
        (row) => row.source === "report" && row.disposition === "effective",
      );
      return html`${report?.text ?? "No report yet."}${
        worker.heard
          ? html` Last heard <lf-age datetime=${worker.heard}></lf-age>`
          : ""
      }`;
    }
  },
);
