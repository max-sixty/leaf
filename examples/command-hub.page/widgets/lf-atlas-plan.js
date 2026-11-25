/* Atlas owns this dashboard's composition. Shared work readings keep counts,
 * stopped tasks and assignments consistent with the recorded decisions. */
import { html, noChange, render, repeat } from "/vendor/lit.js";
import { elementById, readWork } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";
customElements.define(
  "lf-atlas-plan",
  class extends LeafElement {
    setup() {
      keeps(this, "role", "group");
      keeps(this, "aria-label", this.getAttribute("label") ?? "Plan");
      this.overview = elementById(this.getAttribute("overview"), this);
      if (!this.overview) return;
      // The counts are this plan's words; the stopped list repeats task titles the
      // page says in the tree.
      for (const count of this.overview.querySelectorAll("[data-atlas-count]")) {
        keeps(count, "data-lf-gen", "1");
        count.toggleAttribute("data-lf-said", true);
      }
      const stopped = this.overview.querySelector(".atlas-stopped > ul");
      keeps(stopped, "data-lf-gen", "1");
      stopped.toggleAttribute("data-lf-echo", true);
    }
    render() {
      if (!this.overview) return noChange;
      const reading = readWork(this);
      const counts = {
        progress: `${reading.done} / ${reading.leaves.length} complete`,
        running: reading.running.length,
        workers: reading.liveWorkers.length,
        quiet: reading.quiet.length,
        stopped: reading.stopped.length,
      };
      for (const [name, value] of Object.entries(counts))
        keepsText(
          this.overview.querySelector(`[data-atlas-count="${name}"]`),
          String(value),
        );
      render(
        repeat(
          reading.stopped,
          (row) => row.element.id,
          (row) => html`<li><a href=${`#${row.element.id}`}>${row.title}</a></li>`,
        ),
        this.overview.querySelector(".atlas-stopped > ul"),
      );
      return noChange;
    }
  },
);
