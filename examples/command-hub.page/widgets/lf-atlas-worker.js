/* Atlas owns roster composition. A visible report keeps its reading until the
 * user asks for the latest, while identity and state come from the public projection. */
import {
  ago,
  generatedElement,
  HeldReading,
  html,
  keeps,
  keepsText,
  LeafElement,
  noChange,
  readWork,
  reportSequence,
  reportsReady,
  workAncestor,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-worker",
  class extends LeafElement {
    pending = false;
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
      generatedElement(this.querySelector(".atlas-worker-state"), { says: true });
      generatedElement(this.querySelector(".atlas-worker-report"), { says: true });
      this.held = new HeldReading(
        this,
        () => [this.querySelector(".atlas-worker-body")],
        () => this.requestUpdate(),
      );
    }
    createRenderRoot() {
      return this.querySelector(".atlas-worker-report");
    }
    render() {
      keeps(this, "state", this.state.state.value);
      const worker = readWork(workAncestor(this, "scope")).workers.find(
        (row) => row.element === this,
      );
      keepsText(
        this.querySelector(".atlas-worker-state"),
        `${worker.state}${worker.quiet ? " · quiet" : ""}`,
      );
      if (!reportsReady(this)) return noChange;
      const report = reportSequence(this).findLast(
        (row) => row.source === "report" && row.disposition === "effective",
      );
      const next = JSON.stringify({
        heard: worker.heard,
        text: report?.text ?? "No report yet.",
      });
      const shown = this.held.hold(next);
      const reading = JSON.parse(shown);
      if (this.pending !== (next !== shown)) {
        this.pending = next !== shown;
        this.dispatchEvent(new CustomEvent("atlas-reading", { bubbles: true }));
      }
      return html`${reading.text}${
        reading.heard
          ? html` Last heard
              <time datetime=${reading.heard} title=${reading.heard}
                >${ago(reading.heard)}</time
              >`
          : ""
      }`;
    }
    showLatest() {
      this.held.show();
    }
  },
);
