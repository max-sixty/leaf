/* Atlas owns roster composition. A worker's latest report draws as it arrives. Its
 * state is its own `state`; what it last said, and when, is its newest report in the
 * page's history, which the hub's record has the server send, else the note of the
 * version that asserted its state. A worker that claims work it hasn't reported on for
 * a quarter of an hour is quiet. */
import { html, noChange } from "/vendor/lit.js";
import { readHistory } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";

const QUIET_MS = 15 * 60 * 1000;
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
      const state = this.state.state.value;
      keeps(this, "state", state);
      const { phase, events } = readHistory();
      const report = events.find(
        (row) => row.kind === "report" && row.widget === this.id,
      );
      const heard = report?.ts ?? events.find((row) => row.kind === "note")?.ts;
      this.quiet =
        state === "working" &&
        Boolean(heard) &&
        Date.now() - Date.parse(heard) > QUIET_MS;
      keepsText(
        this.querySelector(".atlas-worker-state"),
        `${state}${this.quiet ? " · quiet" : ""}`,
      );
      // The plan counts this worker again.
      this.dispatchEvent(new CustomEvent("atlas-reading", { bubbles: true }));
      if (phase !== "ready") return noChange;
      return html`${report?.excerpt ?? "No report yet."}${
        heard ? html` Last heard <lf-age datetime=${heard}></lf-age>` : ""
      }`;
    }
  },
);
