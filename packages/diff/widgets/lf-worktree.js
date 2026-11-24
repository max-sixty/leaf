/* The native disclosure owns its open state. Lit updates the snapshot's labels
 * and totals; authored evidence remains in the host through revisions. */
import { render } from "./worktree-view.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";

customElements.define(
  "lf-worktree",
  class extends LeafElement {
    static lfPatch = "members";
    static shadow = true;
    render() {
      return render(this);
    }
  },
);
