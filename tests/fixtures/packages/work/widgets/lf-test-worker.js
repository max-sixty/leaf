/* An anonymous report consumer keeps clock and report identity tests independent
 * of the Atlas example's composition. The report in force is the worker's `state`;
 * when it last reported is its newest report in the page's history, else the note of
 * the version that asserted its state. A
 * worker claiming work it hasn't reported on for a quarter of an hour is quiet. */
import { html, noChange } from "/vendor/lit.js";
import { history } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps } from "/runtime/lib/keeps.js";

const RUNNING = new Set(["working", "waiting"]);
const QUIET_MS = 15 * 60 * 1000;
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
      const { value: state, detail } = this.state.state;
      keeps(this, "state", state);
      const { phase, events } = history.read();
      if (phase !== "ready") return noChange;
      const heard =
        events.find((row) => row.kind === "report" && row.widget === this.id)?.ts ??
        events.find((row) => row.kind === "note")?.ts;
      const quiet =
        RUNNING.has(state) && heard && Date.now() - Date.parse(heard) >= QUIET_MS;
      return html`<span class="lf-state">${state}</span>
        ${detail.text ? html`<span class="lf-doing">${detail.text}</span>` : ""}
        ${quiet ? html`<span class="lf-cold">quiet</span>` : ""}
        ${
          heard
            ? html`<span class="lf-heard"
                >last heard <lf-age datetime=${heard}></lf-age
              ></span>`
            : ""
        }`;
    }
  },
);
