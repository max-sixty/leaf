/* Adopt the native disclosure the initial drawing built around the authored body.
 * Revision patching edits inside that body, retaining nested readers while changing
 * the prose around them. */
import { LeafElement, initialRender } from "/runtime/widget-api.js";

customElements.define(
  "lf-worktree",
  class extends LeafElement {
    #view;
    setup() {
      this.#view = initialRender(this);
    }

    render() {
      return this.#view.render();
    }
  },
);
