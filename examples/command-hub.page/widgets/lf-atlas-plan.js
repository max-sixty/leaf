/* Atlas owns this dashboard's composition. It counts the work its tasks and workers
 * hold from each one's `state`, which Leaf sets as their recorded state moves, and
 * each tells the plan to count again as it draws (`atlas-reading`). A task is stopped
 * while its status says so or a question standing in it, under no task inside it,
 * waits on the user; a worker is quiet while it claims work it hasn't reported on
 * for a quarter of an hour (lf-atlas-worker.js). */
import { html, noChange, render, repeat } from "/vendor/lit.js";
import { elementById, obligations } from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";

const STOPPED = new Set(["blocked", "review", "stalled"]);
const RETIRED = new Set(["reaped", "done"]);
const status = (task) => task.state?.status.value ?? task.getAttribute("status");
const workerState = (worker) =>
  worker.state?.state.value ?? worker.getAttribute("state");
const stopped = (task) =>
  STOPPED.has(status(task)) ||
  obligations
    .read(task)
    .user.some(
      (item) =>
        item.source.kind === "widget" &&
        document
          .getElementById(item.source.id)
          ?.parentElement?.closest("lf-atlas-task") === task,
    );
const stoppedAt = (task) =>
  Date.parse(task.getAttribute("stopped-at") ?? "") || Infinity;

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
      const list = this.overview.querySelector(".atlas-stopped > ul");
      keeps(list, "data-lf-gen", "1");
      list.toggleAttribute("data-lf-echo", true);
      this.addEventListener("atlas-reading", () => this.requestUpdate());
    }
    render() {
      if (!this.overview) return noChange;
      const tasks = [...this.querySelectorAll("lf-atlas-task")];
      const leaves = tasks.filter((task) => !task.querySelector("lf-atlas-task"));
      const live = [...this.querySelectorAll("lf-atlas-worker")].filter(
        (worker) => !RETIRED.has(workerState(worker)),
      );
      const halted = tasks.filter(stopped).sort((a, b) => stoppedAt(a) - stoppedAt(b));
      const done = leaves.filter((task) => status(task) === "done").length;
      const counts = {
        progress: `${done} / ${leaves.length} complete`,
        running: live.filter(
          (worker) => workerState(worker) === "working" && !worker.quiet,
        ).length,
        workers: live.length,
        quiet: live.filter((worker) => worker.quiet).length,
        stopped: halted.length,
      };
      for (const [name, value] of Object.entries(counts))
        keepsText(
          this.overview.querySelector(`[data-atlas-count="${name}"]`),
          String(value),
        );
      render(
        repeat(
          halted,
          (task) => task.id,
          (task) =>
            html`<li>
              <a href=${`#${task.id}`}>${task.getAttribute("label") || task.id}</a>
            </li>`,
        ),
        this.overview.querySelector(".atlas-stopped > ul"),
      );
      return noChange;
    }
  },
);
