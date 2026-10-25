/* Adopt the native disclosure the initial drawing built around the authored body.
 * Revision patching edits inside that body, retaining nested readers while changing
 * the prose around them. */
import { LeafElement, initialRender, noChange } from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree",
  class extends LeafElement {
    setup() {
      initialRender(this);
    }

    render() {
      return noChange;
    }
  },
);
