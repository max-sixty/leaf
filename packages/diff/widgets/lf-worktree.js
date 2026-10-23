/* Decorate a native disclosure without moving its authored evidence. Revision
 * patching retains nested readers while changing the prose around them. */
import { LeafElement, initialRender } from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree",
  class extends LeafElement {
    setup() {
      initialRender(this);
    }

    render() {
      return;
    }
  },
);
