/* Atlas owns this dashboard's composition. Shared work readings keep counts,
 * stopped tasks and assignments consistent with the recorded decisions. */
import {
  authoredScope,
  keeps,
  HeldReading,
  html,
  keepsText,
  once,
  readWork,
  render,
  repeat,
  watchOwner,
  watchUpdates,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-plan",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      keeps(this, "role", "group");
      keeps(this, "aria-label", this.getAttribute("label") ?? "Plan");
      this.overview = authoredScope(this).querySelector(
        `#${CSS.escape(this.getAttribute("overview"))}`,
      );
      if (!this.overview) return;
      this.hold = new HeldReading(
        () => [this.overview.querySelector(".atlas-stopped")],
        () => this.paint(),
      );
      watchOwner(this, { disconnect: () => this.hold.dispose() });
      this.button = this.overview.querySelector(".atlas-refresh");
      this.button.addEventListener("click", () => {
        this.hold.release();
        for (const child of this.querySelectorAll("lf-atlas-worker, lf-atlas-tree"))
          child.showUpdates();
        this.paint();
      });
      this.addEventListener("atlas-reading", () => this.paint());
      watchUpdates(this, () => this.paint());
    }
    paint() {
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
      const next = JSON.stringify(
        reading.stopped.map((row) => [row.element.id, row.title]),
      );
      const shown = this.hold.hold(next);
      const pending =
        next !== shown ||
        [...this.querySelectorAll("lf-atlas-worker, lf-atlas-tree")].some(
          (child) => child.pending,
        );
      this.button.toggleAttribute("disabled", !pending);
      render(
        repeat(
          JSON.parse(shown),
          ([id]) => id,
          ([id, title]) => html`<li><a href=${`#${id}`}>${title}</a></li>`,
        ),
        this.overview.querySelector(".atlas-stopped > ul"),
      );
    }
  },
);
