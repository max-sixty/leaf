/* A local consumer exercises declaration-driven reports without shipping a task UI. */
import { nothing } from "/vendor/lit.js";
import {
  generatedElement,
  keeps,
  keepsText,
  LeafElement,
  offer,
  offerAction,
  readWork,
  threadSurface,
  workAncestor,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-test-task",
  class extends LeafElement {
    setup() {
      keeps(this, "role", "group");
      this.ariaLabelledByElements = [this.querySelector(":scope > strong")].filter(
        Boolean,
      );
      this.statusLine =
        this.querySelector(":scope > .work-state[data-lf-gen]") ??
        document.createElement("span");
      this.statusLine.className = "work-state";
      generatedElement(this.statusLine, { says: true });
      this.append(this.statusLine);
      this.progress = document.createElement("output");
      this.progress.className = "work-progress";
      generatedElement(this.progress, { says: false });
      this.append(this.progress);
      if (!this.hasAttribute("talk")) return;
      // A task marked `talk` seats the threads about it, and the comment box that
      // starts one, whose second send holds the task.
      this.threads = offer("div", "lf-test-threads");
      this.threads.lfHold = "Send & pause";
      this.comment = offerAction("symbol", "lf-test-comment", undefined, {
        action: "comment",
      });
      this.comment.addEventListener("click", () => threadSurface(this).open?.(this));
      this.append(this.threads, this.comment);
    }
    threadOutlets(targets, { onCommit }) {
      if (!this.threads) return targets.map(() => null);
      const writing = targets.some(({ thread }) => !thread);
      onCommit(() => {
        this.writing = writing;
        this.requestUpdate();
      });
      return targets.map(() => this.threads);
    }
    render() {
      keeps(this, "status", this.state.status.value);
      keepsText(this.statusLine, this.state.status.value ?? "");
      const row = readWork(
        workAncestor(this, "scope") ?? this.parentElement,
      ).goals.find((row) => row.element === this);
      keepsText(this.progress, `${row.finished}/${row.leaves.length} done`);
      this.comment?.toggleAttribute(
        "hidden",
        this.writing || !threadSurface(this).open,
      );
      return nothing;
    }
  },
);
