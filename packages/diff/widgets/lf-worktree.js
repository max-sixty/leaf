/* The native disclosure owns its open state. Lit updates the snapshot's labels
 * and totals; authored evidence remains in the host through revisions. */
import { render } from "./worktree-view.js";
import { LeafElement } from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree",
  class extends LeafElement {
    render() {
      return render(this);
    }
  },
);
