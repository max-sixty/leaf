/* Atlas task rows keep their authored hierarchy and report identity. A row marked
 * `talk` shows the conversations about it at its foot, where its Comment control opens
 * the box that starts one. */
import {
  keeps,
  keepsHidden,
  keepsText,
  LeafElement,
  nothing,
  offer,
  offerAction,
  threadSurface,
} from "/runtime/widget-api.js";
customElements.define(
  "lf-atlas-task",
  class extends LeafElement {
    setup() {
      keeps(this, "role", "group");
      this.ariaLabelledByElements = [this.querySelector(":scope > strong")];
      const status =
        this.querySelector(':scope > [data-lf-said="status"]') ??
        document.createElement("p");
      status.className = "atlas-task-state";
      status.dataset.lfGen = "1";
      status.dataset.lfSaid = "status";
      this.prepend(status);
      this.statusLine = status;
      if (!this.hasAttribute("talk")) return;
      // The second send of the comment box standing here holds this task while the
      // thread it starts is open.
      this.threads = offer("div", "atlas-task-threads");
      this.threads.lfHold = "Send & pause";
      this.comment = offerAction("symbol", "atlas-task-comment", undefined, {
        action: "comment",
      });
      this.comment.addEventListener("click", () => threadSurface(this).open?.(this));
      this.append(this.threads, this.comment);
    }
    // Every target is this row, which projects no data. The comment box takes the
    // Comment control's place while it stands here.
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
      const status = this.state.status.value;
      keeps(this, "status", status);
      keepsText(this.statusLine, status);
      keepsHidden(this.comment, this.writing || !threadSurface(this).open);
      return nothing;
    }
  },
);
