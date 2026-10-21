/* An anonymous report consumer keeps clock and report identity tests independent
 * of the Atlas example's composition. */
import {
  ago,
  html,
  createView,
  Show,
  keeps,
  LeafElement,
  quietSince,
  saidAt,
  reportSequence,
  reportsReady,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-test-worker",
  class extends LeafElement {
    #drawing = null;
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
      if (!reportsReady(this)) return;
      const reports = reportSequence(this).filter(
        (row) => row.source === "report" && row.action === "state",
      );
      const heard = reports.at(-1)?.ts ?? saidAt(this);
      const current = reports.findLast((row) => row.disposition === "effective");
      const props = {
        state,
        doing: current?.text ?? "",
        quiet: ["working", "waiting"].includes(state) && quietSince(heard),
        heard: ago(heard),
      };
      if (this.#drawing) this.#drawing.update(props);
      else
        this.#drawing = createView(
          this.renderRoot,
          (read) =>
            html` <span class="lf-state">${() => read().state}</span>
              ${Show({
          get when() {
            return read().doing;
          },
          children: (_visible) =>
            html`<span class="lf-doing">${() => read().doing}</span>`,
        })}
              ${Show({
          get when() {
            return read().quiet;
          },
          children: (_visible) => html`<span class="lf-cold">quiet</span>`,
        })}
              <span class="lf-heard">last heard ${() => read().heard}</span>`,
          props,
        );
    }
  },
);
