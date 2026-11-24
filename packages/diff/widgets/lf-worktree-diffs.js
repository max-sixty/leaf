/* Lit redraws the collection's authored member attributes after a revision. */
import { render } from "./worktree-diffs-view.js";
import { LeafElement } from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree-diffs",
  class extends LeafElement {
    static lfPatch = "members";
    static shadow = true;
    render() {
      return render(this);
    }
  },
);
